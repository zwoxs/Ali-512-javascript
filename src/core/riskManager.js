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
   * Alinacak miktari hesaplar.
   * percent modu: bakiyenin sabit yuzdesi.
   * risk modu   : islem basina riske edilen sermaye / stop mesafesi
   *               (profesyonel boyutlama - stop genisse pozisyon kuculur).
   */
  positionSize(quoteBalance, equity, price, atrValue = null) {
    let budget;
    if (this.cfg.sizingMode === "risk") {
      const riskAmount = equity * (this.cfg.riskPerTradePct / 100);
      budget = (riskAmount / this.stopDistance(price, atrValue)) * price;
    } else {
      budget = quoteBalance * (this.cfg.positionPct / 100);
    }
    budget = Math.min(budget, quoteBalance); // asla bakiyeden fazlasi degil
    const fee = budget * (this.cfg.feePct / 100);
    return Math.max((budget - fee) / price, 0);
  }

  /**
   * Acik pozisyon icin cikis kontrolu. Cikis gerekiyorsa neden dondurur.
   * ATR modunda stop/hedef giris anindaki volatiliteye gore sabitlenir.
   * @param {{entryPrice: number, highWater: number, entryAtr?: number}} pos
   */
  checkExit(pos, price) {
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
    if (this.cfg.trailingStopPct > 0) {
      const fromHigh = ((price - pos.highWater) / pos.highWater) * 100;
      if (fromHigh <= -this.cfg.trailingStopPct && price > pos.entryPrice) {
        return `Iz suren stop: zirveden %${(-fromHigh).toFixed(2)} geri cekilme (kar kilitlendi)`;
      }
    }
    return null;
  }

  /** Kapanan islemin sonucunu isler; devre kesicileri gunceller. */
  onTradeClosed(pnl, initialEquity) {
    this._rollDay();
    this.dailyPnl += pnl;
    if (pnl < 0) {
      this.consecutiveLosses++;
      if (this.consecutiveLosses >= this.cfg.maxConsecutiveLosses) {
        this.cooldownUntil = this.now() + this.cfg.cooldownMinutes * 60_000;
      }
    } else {
      this.consecutiveLosses = 0;
    }
    const dailyLossPct = (-this.dailyPnl / initialEquity) * 100;
    if (dailyLossPct >= this.cfg.maxDailyLossPct) {
      this.dailyLimitHit = true;
    }
    return { dailyLimitHit: this.dailyLimitHit, cooldownActive: this.now() < this.cooldownUntil };
  }
}
