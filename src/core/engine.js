import { log } from "../logger.js";
import { atr } from "../indicators.js";
import { isUptrend } from "./trendFilter.js";

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

  /** ATR modunda gecerli volatiliteyi hesaplar; gerek yoksa null. */
  _currentAtr(candles) {
    if (this.cfg.stopMode !== "atr") return null;
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

    // 1) Acik pozisyon: iz suren stop icin zirve takibi + cikis kontrolu (her adimda)
    if (pos) {
      this.portfolio.updateHighWater(this.symbol, currentPrice);
      const exitReason = this.risk.checkExit(pos, currentPrice);
      if (exitReason) {
        await this._sell(currentPrice, exitReason, ts);
        return;
      }
    }

    // 2) Strateji sinyali: ayni kapanan mumu iki kez isleme
    const lastClosed = closedCandles[closedCandles.length - 1];
    if (!lastClosed || lastClosed.closeTime === this.lastCandleTime) return;
    this.lastCandleTime = lastClosed.closeTime;

    const { signal, reason, snapshot } = this.strategy.evaluate(closedCandles, this.cfg);
    this.lastSignal = { signal, reason, snapshot, ts };
    log.debug(`${this.symbol} | ${JSON.stringify(snapshot)} | Sinyal: ${signal}`);

    if (signal === "BUY" && !this.portfolio.inPosition(this.symbol)) {
      const blocked = this.risk.canOpen();
      if (blocked) {
        if (!this.silent) log.warn(`${this.symbol} AL sinyali engellendi: ${blocked}`);
        return;
      }
      if (this.cfg.htfFilter && !isUptrend(closedCandles, this.cfg)) {
        log.debug(`${this.symbol} AL sinyali HTF filtresine takildi: ust zaman dilimi dusus trendinde.`);
        return;
      }
      await this._buy(currentPrice, reason, ts, closedCandles);
    } else if (signal === "SELL" && this.portfolio.inPosition(this.symbol)) {
      await this._sell(currentPrice, reason, ts);
    }
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
    const fill = await this.broker.buy(this.symbol, qty, price);
    if (!fill) return;
    fill.ts = ts;
    this.portfolio.recordBuy(this.symbol, fill);
    if (atrValue) this.portfolio.getPosition(this.symbol).entryAtr = atrValue;
    const record = { side: "AL", symbol: this.symbol, qty: fill.qty, price: fill.price, reason, mode: this.cfg.tradeMode };
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
