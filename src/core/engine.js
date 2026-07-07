import { log } from "../logger.js";

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
   * @param {object} deps.broker     - { buy(symbol, quoteBudgetQty, price), sell(symbol, qty, price) }
   * @param {function} [deps.onTrade] - islem sonrasi bildirim callback'i
   */
  constructor({ symbol, strategy, cfg, portfolio, risk, broker, onTrade }) {
    this.symbol = symbol;
    this.strategy = strategy;
    this.cfg = cfg;
    this.portfolio = portfolio;
    this.risk = risk;
    this.broker = broker;
    this.onTrade = onTrade || (() => {});
    this.lastCandleTime = 0;
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
    log.debug(`${this.symbol} | ${JSON.stringify(snapshot)} | Sinyal: ${signal}`);

    if (signal === "BUY" && !this.portfolio.inPosition(this.symbol)) {
      const blocked = this.risk.canOpen();
      if (blocked) {
        log.warn(`${this.symbol} AL sinyali engellendi: ${blocked}`);
        return;
      }
      await this._buy(currentPrice, reason, ts);
    } else if (signal === "SELL" && this.portfolio.inPosition(this.symbol)) {
      await this._sell(currentPrice, reason, ts);
    }
  }

  async _buy(price, reason, ts) {
    const qty = this.risk.positionSize(
      this.portfolio.quote,
      this.portfolio.equity({ [this.symbol]: price }),
      price
    );
    if (qty <= 0) {
      log.warn(`${this.symbol}: alim icin yeterli bakiye yok.`);
      return;
    }
    const fill = await this.broker.buy(this.symbol, qty, price);
    if (!fill) return;
    fill.ts = ts;
    this.portfolio.recordBuy(this.symbol, fill);
    const record = { side: "AL", symbol: this.symbol, qty: fill.qty, price: fill.price, reason, mode: this.cfg.tradeMode };
    log.trade(record);
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
    log.trade(record);
    await this.onTrade(record);
    if (breakers.dailyLimitHit) {
      log.warn(`DEVRE KESICI: Gunluk zarar limiti asildi - bugun yeni pozisyon acilmayacak.`);
      await this.onTrade({ side: "UYARI", symbol: this.symbol, qty: 0, price, reason: "Gunluk zarar limiti asildi", mode: this.cfg.tradeMode });
    }
  }
}
