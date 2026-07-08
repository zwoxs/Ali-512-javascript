import { log } from "../logger.js";
import { atr } from "../indicators.js";
import { isUptrend, isTrendingMarket } from "./trendFilter.js";

/**
 * Islem motoru - tek sembol icin karar dongusu.
 * Backtest ve canli calisma AYNI step() yolunu kullanir; boylece
 * backtest'te olculen davranis canlida calisan davranisin birebir aynisidir.
 */
export class Engine {
  /**
   * @param {object} deps
   * @param {string} deps.symbol
   * @param {object} deps.strategy   - { evaluate, warmup } sozlesmesi
   * @param {object} deps.cfg
   * @param {import('./portfolio.js').Portfolio} deps.portfolio
   * @param {import('./riskManager.js').RiskManager} deps.risk
   * @param {object} deps.broker     - { buy(symbol, qty, price), sell(symbol, qty, price) }
   * @param {function} [deps.onTrade] - islem sonrasi bildirim callback'i
   * @param {boolean} [deps.silent]  - true ise islem loglari yazilmaz (optimizasyon kosulari)
   */
  constructor({ symbol, strategy, cfg, portfolio, risk, broker, onTrade, silent = false }) {
    this.symbol = symbol;
    this.strategy = strategy;
    this.cfg = cfg;
    this.portfolio = portfolio;
    this.risk = risk;
    this.broker = broker;
    this.onTrade = onTrade || (() => {});
    this.silent = silent;
    this.lastCandleTime = 0;
    this.lastSignal = null; // izleme paneli icin
  }

  _logTrade(record) {
    if (!this.silent) log.trade(record);
  }

  /** Guncel ATR degeri; hicbir tuketici yoksa hesaplanmaz (null). */
  _currentAtr(candles) {
    const needed =
      this.cfg.stopMode === "atr" ||
      this.cfg.trailingMode === "atr" ||
      this.cfg.maxEntryAtrPct > 0;
    if (!needed) return null;
    const values = atr(candles, this.cfg.atrPeriod);
    return values.length ? values[values.length - 1] : null;
  }

  /**
   * Tek karar adimi.
   * @param {Array} closedCandles - kapanmis mumlar (eski -> yeni)
   * @param {number} currentPrice - anlik fiyat
   * @param {number} ts           - bu adimin zaman damgasi (ms)
   */
  async step(closedCandles, currentPrice, ts) {
    const pos = this.portfolio.getPosition(this.symbol);

    // 1) Acik pozisyon: zirve takibi + tam cikis / kismi kar alma (her adimda)
    if (pos) {
      this.portfolio.updateHighWater(this.symbol, currentPrice);
      const exitReason = this.risk.checkExit(pos, currentPrice);
      if (exitReason) {
        await this._sell(currentPrice, exitReason, ts);
        return;
      }
      const partialReason = this.risk.checkPartial(pos, currentPrice);
      if (partialReason) {
        await this._partialSell(currentPrice, partialReason, ts);
      }
    }

    // 2) Strateji sinyali: ayni kapanan mumu iki kez isleme
    const lastClosed = closedCandles[closedCandles.length - 1];
    if (!lastClosed || lastClosed.closeTime === this.lastCandleTime) return;
    this.lastCandleTime = lastClosed.closeTime;

    // 2a) Zaman asimi cikisi: uzun suredir KARSIZ bekleyen "olu" pozisyonu kapat.
    // Sermayeyi bagli tutan ve stop riskini tasiyan pozisyon, firsata donusmuyorsa cikilir.
    if (pos && this.cfg.maxHoldCandles > 0) {
      pos.candlesHeld = (pos.candlesHeld || 0) + 1;
      const fromEntry = ((currentPrice - pos.entryPrice) / pos.entryPrice) * 100;
      if (pos.candlesHeld >= this.cfg.maxHoldCandles && fromEntry <= 0) {
        await this._sell(currentPrice, `Zaman asimi: ${pos.candlesHeld} mumdur karsiz pozisyon`, ts);
        return;
      }
    }

    // 2b) Piramitleme: kazanan pozisyona kademeli ekleme (mum basina en fazla bir kez)
    if (pos && this.cfg.pyramidMaxAddons > 0 && (pos.addons || 0) < this.cfg.pyramidMaxAddons) {
      const lastAdd = pos.lastAddPrice || pos.entryPrice;
      if (currentPrice >= lastAdd * (1 + this.cfg.pyramidTriggerPct / 100)) {
        await this._addOn(currentPrice, ts);
      }
    }

    const { signal, reason, snapshot } = this.strategy.evaluate(closedCandles, this.cfg);
    this.lastSignal = { signal, reason, snapshot, ts };
    log.debug(`${this.symbol} | ${JSON.stringify(snapshot)} | Sinyal: ${signal}`);

    // Sinyal modu: islem acilmaz, sadece bildirim gonderilir
    if (this.cfg.tradeMode === "signal") {
      if (signal !== "HOLD") {
        const record = {
          side: signal === "BUY" ? "SINYAL-AL" : "SINYAL-SAT",
          symbol: this.symbol, qty: 0, price: currentPrice, reason, mode: "signal",
        };
        this._logTrade(record);
        await this.onTrade(record);
      }
      return;
    }

    if (signal === "BUY" && !this.portfolio.inPosition(this.symbol)) {
      const blocked = this.risk.canOpen() ||
        this.risk.checkPortfolioLimits(this.portfolio, { [this.symbol]: currentPrice });
      if (blocked) {
        if (!this.silent) log.warn(`${this.symbol} AL sinyali engellendi: ${blocked}`);
        return;
      }
      if (this.cfg.htfFilter && !isUptrend(closedCandles, this.cfg)) {
        log.debug(`${this.symbol} AL sinyali HTF filtresine takildi: ust zaman dilimi dusus trendinde.`);
        return;
      }
      if (this.cfg.adxFilter && !isTrendingMarket(closedCandles, this.cfg)) {
        log.debug(`${this.symbol} AL sinyali ADX filtresine takildi: piyasa trendsiz.`);
        return;
      }
      // Volatilite bekcisi: asiri oynak piyasada stoplar anlamsizlasir - girme
      if (this.cfg.maxEntryAtrPct > 0) {
        const atrValue = this._currentAtr(closedCandles);
        if (atrValue && (atrValue / currentPrice) * 100 > this.cfg.maxEntryAtrPct) {
          if (!this.silent) log.warn(
            `${this.symbol} AL sinyali volatilite bekcisine takildi: ` +
            `ATR %${((atrValue / currentPrice) * 100).toFixed(2)} > %${this.cfg.maxEntryAtrPct}`
          );
          return;
        }
      }
      await this._buy(currentPrice, reason, ts, closedCandles);
    } else if (signal === "SELL" && this.portfolio.inPosition(this.symbol)) {
      await this._sell(currentPrice, reason, ts);
    }
  }

  /** Piramit kademesi: ilk giris boyutunun kuculen kati kadar ekleme yapar. */
  async _addOn(price, ts) {
    const pos = this.portfolio.getPosition(this.symbol);
    if (!pos) return;
    const nextAddon = (pos.addons || 0) + 1;
    const qty = (pos.initialQty ?? pos.qty) * this.cfg.pyramidSizeFactor ** nextAddon;
    const cost = qty * price;
    if (qty <= 0 || cost > this.portfolio.quote) {
      log.debug(`${this.symbol}: piramit kademesi icin yeterli bakiye yok.`);
      return;
    }
    const fill = await this.broker.buy(this.symbol, qty, price);
    if (!fill) return;
    fill.ts = ts;
    this.portfolio.recordAddOn(this.symbol, fill);
    const record = {
      side: "KADEME-AL", symbol: this.symbol, qty: fill.qty, price: fill.price,
      reason: `Piramit kademe ${nextAddon}/${this.cfg.pyramidMaxAddons} (+%${this.cfg.pyramidTriggerPct} hareket)`,
      mode: this.cfg.tradeMode,
    };
    this._logTrade(record);
    await this.onTrade(record);
  }

  async _buy(price, reason, ts, candles) {
    const atrValue = this._currentAtr(candles);
    const qty = this.risk.positionSize(
      this.portfolio.quote,
      this.portfolio.equity({ [this.symbol]: price }),
      price,
      atrValue
    );
    if (qty <= 0) {
      if (!this.silent) log.warn(`${this.symbol}: alim icin yeterli bakiye yok.`);
      return;
    }
    // Minimum emir tutari: komisyonun kari yedigi kucuk emirleri engelle
    if (this.cfg.minOrderNotional > 0 && qty * price < this.cfg.minOrderNotional) {
      if (!this.silent) log.warn(
        `${this.symbol}: emir tutari ${(qty * price).toFixed(2)} TRY < minimum ${this.cfg.minOrderNotional} TRY - atlandi.`
      );
      return;
    }
    const fill = await this.broker.buy(this.symbol, qty, price);
    if (!fill) return;
    fill.ts = ts;
    this.portfolio.recordBuy(this.symbol, fill);
    if (atrValue) this.portfolio.getPosition(this.symbol).entryAtr = atrValue;
    const record = { side: "AL", symbol: this.symbol, qty: fill.qty, price: fill.price, reason, mode: this.cfg.tradeMode };
    this._logTrade(record);
    await this.onTrade(record);
  }

  async _partialSell(price, reason, ts) {
    const pos = this.portfolio.getPosition(this.symbol);
    if (!pos) return;
    const sellQty = pos.qty * (this.cfg.partialTpSize / 100);
    const fill = await this.broker.sell(this.symbol, sellQty, price);
    if (!fill || fill.qty >= pos.qty) return; // yuvarlama tum pozisyonu kapatacaksa vazgec
    fill.ts = ts;
    const pnl = this.portfolio.recordPartialSell(this.symbol, fill);
    this.risk.onTradeClosed(pnl, this.portfolio.initialQuote, { partial: true });
    const record = { side: "KISMI-SAT", symbol: this.symbol, qty: fill.qty, price: fill.price, pnl, reason, mode: this.cfg.tradeMode };
    this._logTrade(record);
    await this.onTrade(record);
  }

  async _sell(price, reason, ts) {
    const pos = this.portfolio.getPosition(this.symbol);
    if (!pos) return;
    const fill = await this.broker.sell(this.symbol, pos.qty, price);
    if (!fill) return;
    fill.ts = ts;
    const pnl = this.portfolio.recordSell(this.symbol, fill);
    const breakers = this.risk.onTradeClosed(pnl, this.portfolio.initialQuote);
    const record = { side: "SAT", symbol: this.symbol, qty: fill.qty, price: fill.price, pnl, reason, mode: this.cfg.tradeMode };
    this._logTrade(record);
    await this.onTrade(record);
    if (breakers.dailyLimitHit && !this.silent) {
      log.warn(`DEVRE KESICI: Gunluk zarar limiti asildi - bugun yeni pozisyon acilmayacak.`);
      await this.onTrade({ side: "UYARI", symbol: this.symbol, qty: 0, price, reason: "Gunluk zarar limiti asildi", mode: this.cfg.tradeMode });
    }
  }
}
