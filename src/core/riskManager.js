/**
 * Risk yoneticisi - sermayeyi koruyan tum kurallar tek yerde:
 *  - Pozisyon boyutlama (sabit % veya stop mesafesine gore risk bazli)
 *  - Zarar durdur / kar al / iz suren stop (trailing)
 *  - Gunluk zarar limiti devre kesicisi
 *  - Ust uste zarar sonrasi sogurma (cooldown) suresi
 */
export class RiskManager {
  constructor(cfg, now = () => Date.now()) {
    this.cfg = cfg;
    this.now = now;
    this.dayKey = null;
    this.dailyPnl = 0;
    this.consecutiveLosses = 0;
    this.cooldownUntil = 0;
    this.dailyLimitHit = false;
    this.equityPeak = 0;      // acil fren icin toplam sermaye zirvesi
    this.killSwitch = false;  // devreye girerse yeni islem acilmaz (kalicidir)
  }

  /**
   * ACIL FREN: toplam sermayeyi izler. Zirveden maxTotalDrawdownPct kadar
   * dususte kill-switch devreye girer ve KALICI olarak yeni islem engellenir
   * (yeniden baslatmada da korunur - manuel inceleme gerektirir).
   * @returns {boolean} bu cagrida yeni tetiklendiyse true
   */
  updateEquity(equity) {
    if (equity > this.equityPeak) this.equityPeak = equity;
    if (this.killSwitch || this.cfg.maxTotalDrawdownPct <= 0 || this.equityPeak <= 0) return false;
    const drawdownPct = ((this.equityPeak - equity) / this.equityPeak) * 100;
    if (drawdownPct >= this.cfg.maxTotalDrawdownPct) {
      this.killSwitch = true;
      return true;
    }
    return false;
  }

  _rollDay() {
    const key = new Date(this.now()).toISOString().slice(0, 10);
    if (key !== this.dayKey) {
      this.dayKey = key;
      this.dailyPnl = 0;
      this.dailyLimitHit = false;
    }
  }

  /** Yeni pozisyon acilabilir mi? Engellenmisse neden dondurur, serbestse null. */
  canOpen() {
    this._rollDay();
    if (this.killSwitch) {
      return `ACIL FREN AKTIF: toplam sermaye zirveden %${this.cfg.maxTotalDrawdownPct} dustu. ` +
             `Stratejinizi gozden gecirin; devam icin data/state.json'daki killSwitch'i sifirlayin.`;
    }
    if (this.dailyLimitHit) {
      return `Gunluk zarar limiti asildi (%${this.cfg.maxDailyLossPct}). Bugun yeni islem yok.`;
    }
    if (this.now() < this.cooldownUntil) {
      const mins = Math.ceil((this.cooldownUntil - this.now()) / 60000);
      return `Sogurma suresi aktif (${this.consecutiveLosses} ust uste zarar). Kalan: ~${mins} dk.`;
    }
    return null;
  }

  /** Stop mesafesi (fiyat birimi): ATR modu volatiliteye uyum saglar. */
  stopDistance(price, atrValue = null) {
    if (this.cfg.stopMode === "atr" && atrValue > 0) {
      return atrValue * this.cfg.atrStopMult;
    }
    return price * (this.cfg.stopLossPct / 100);
  }

  /**
   * Komisyon + kayma maliyet carpani. Emrin GERCEK maliyeti carpimsaldir:
   * kotu fiyat (1+kayma) VE komisyon (1+fee). Dogrusal toplam (fee+slip) ikinci
   * derece terimi kacirdigi icin carpimsal kullanilir - bakiye kesinlikle eksiye
   * dusmez.
   */
  costMultiplier() {
    return (1 + this.cfg.feePct / 100) * (1 + (this.cfg.slippagePct || 0) / 100);
  }

  /**
   * Alinacak miktari hesaplar.
   * percent modu: bakiyenin sabit yuzdesi.
   * risk modu   : islem basina riske edilen sermaye / stop mesafesi
   *               (profesyonel boyutlama - stop genisse pozisyon kuculur).
   *
   * Miktar, komisyon + kayma tamponuyla hesaplanir: emir kotu fiyattan dolsa
   * bile GERCEK maliyet butceyi (dolayisiyla bakiyeyi) asamaz - bakiye eksiye
   * dusmez. Bu, "hata yapma luksu yok" invaryantidir.
   */
  positionSize(quoteBalance, equity, price, atrValue = null) {
    if (!(price > 0) || !(quoteBalance > 0)) return 0;
    let budget;
    if (this.cfg.sizingMode === "risk") {
      const riskAmount = equity * (this.cfg.riskPerTradePct / 100);
      budget = (riskAmount / this.stopDistance(price, atrValue)) * price;
    } else {
      budget = quoteBalance * (this.cfg.positionPct / 100);
    }
    budget = Math.min(budget, quoteBalance); // asla bakiyeden fazlasi degil
    // Tampon: worst-case maliyet = qty * price * costMultiplier <= budget
    const effPrice = price * this.costMultiplier();
    return Math.max(budget / effPrice, 0);
  }

  /**
   * Acik pozisyon icin cikis kontrolu. Cikis gerekiyorsa neden dondurur.
   * ATR modunda stop/hedef giris anindaki volatiliteye gore sabitlenir.
   * @param {{entryPrice: number, highWater: number, entryAtr?: number}} pos
   */
  checkExit(pos, price) {
    // Kismi kar alindiktan sonra stop basabas noktasina cekilir:
    // kalan pozisyon artik zarar edemez.
    if (pos.partialDone && price <= pos.entryPrice) {
      return `Basabas stop (kismi kar sonrasi giris fiyati korundu)`;
    }
    if (this.cfg.stopMode === "atr" && pos.entryAtr > 0) {
      const stopPrice = pos.entryPrice - pos.entryAtr * this.cfg.atrStopMult;
      const tpPrice = pos.entryPrice + pos.entryAtr * this.cfg.atrTpMult;
      if (price <= stopPrice) {
        return `ATR zarar durdur (${price.toFixed(4)} <= ${stopPrice.toFixed(4)}, ${this.cfg.atrStopMult}xATR)`;
      }
      if (price >= tpPrice) {
        return `ATR kar al (${price.toFixed(4)} >= ${tpPrice.toFixed(4)}, ${this.cfg.atrTpMult}xATR)`;
      }
    } else {
      const fromEntry = ((price - pos.entryPrice) / pos.entryPrice) * 100;
      if (fromEntry <= -this.cfg.stopLossPct) {
        return `Zarar durdur (%${fromEntry.toFixed(2)})`;
      }
      if (fromEntry >= this.cfg.takeProfitPct) {
        return `Kar al (%${fromEntry.toFixed(2)})`;
      }
    }
    // Erken basabas: kar esigi bir kez gorulduyse pozisyon artik zarara donemez
    if (
      this.cfg.breakevenTriggerPct > 0 &&
      pos.highWater >= pos.entryPrice * (1 + this.cfg.breakevenTriggerPct / 100) &&
      price <= pos.entryPrice
    ) {
      return `Basabas stop: %${this.cfg.breakevenTriggerPct} kar goruldu, giris fiyati korundu`;
    }
    // Iz suren stop: percent = sabit yuzde | atr = chandelier (zirve - N x ATR)
    if (this.cfg.trailingMode === "atr" && pos.entryAtr > 0) {
      const stopPrice = pos.highWater - pos.entryAtr * this.cfg.chandelierMult;
      if (price <= stopPrice && pos.highWater > pos.entryPrice) {
        return `Chandelier stop: zirve ${pos.highWater.toFixed(4)} - ${this.cfg.chandelierMult}xATR (kar kilitlendi)`;
      }
    } else if (this.cfg.trailingStopPct > 0) {
      const fromHigh = ((price - pos.highWater) / pos.highWater) * 100;
      if (fromHigh <= -this.cfg.trailingStopPct && price > pos.entryPrice) {
        return `Iz suren stop: zirveden %${(-fromHigh).toFixed(2)} geri cekilme (kar kilitlendi)`;
      }
    }
    return null;
  }

  /**
   * Portfoy seviyesi limitler: maksimum acik pozisyon sayisi ve toplam maruziyet.
   * Yeni pozisyon acilmadan once kontrol edilir; engel varsa neden dondurur.
   */
  checkPortfolioLimits(portfolio, prices = {}) {
    if (this.cfg.maxOpenPositions > 0 && portfolio.positions.size >= this.cfg.maxOpenPositions) {
      return `Maksimum acik pozisyon sayisina ulasildi (${this.cfg.maxOpenPositions}).`;
    }
    if (this.cfg.maxExposurePct > 0) {
      const equity = portfolio.equity(prices);
      const exposurePct = equity > 0 ? ((equity - portfolio.quote) / equity) * 100 : 0;
      if (exposurePct >= this.cfg.maxExposurePct) {
        return `Toplam maruziyet limiti asildi (%${exposurePct.toFixed(1)} >= %${this.cfg.maxExposurePct}).`;
      }
    }
    return null;
  }

  /** Kismi kar alma zamani geldi mi? Neden dondurur, degilse null. */
  checkPartial(pos, price) {
    if (!(this.cfg.partialTpPct > 0) || pos.partialDone) return null;
    const fromEntry = ((price - pos.entryPrice) / pos.entryPrice) * 100;
    if (fromEntry >= this.cfg.partialTpPct) {
      return `Kismi kar al (%${fromEntry.toFixed(2)}): pozisyonun %${this.cfg.partialTpSize}'i kapatiliyor, stop basabasa cekildi`;
    }
    return null;
  }

  /**
   * Kapanan islemin sonucunu isler; devre kesicileri gunceller.
   * Kismi satislar gunluk K/Z'ye sayilir ama ardisik zarar sayacini etkilemez
   * (kismi satis her zaman karda tetiklenir; seri, tamamlanan islemlerle olculur).
   */
  onTradeClosed(pnl, initialEquity, { partial = false } = {}) {
    this._rollDay();
    this.dailyPnl += pnl;
    if (!partial) {
      if (pnl < 0) {
        this.consecutiveLosses++;
        if (this.consecutiveLosses >= this.cfg.maxConsecutiveLosses) {
          this.cooldownUntil = this.now() + this.cfg.cooldownMinutes * 60_000;
        }
      } else {
        this.consecutiveLosses = 0;
      }
    }
    const dailyLossPct = (-this.dailyPnl / initialEquity) * 100;
    if (dailyLossPct >= this.cfg.maxDailyLossPct) {
      this.dailyLimitHit = true;
    }
    return { dailyLimitHit: this.dailyLimitHit, cooldownActive: this.now() < this.cooldownUntil };
  }
}
