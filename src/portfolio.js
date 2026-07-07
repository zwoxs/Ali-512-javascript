import { config } from "./config.js";
import { log } from "./logger.js";
import { placeMarketOrder } from "./exchange/binanceTr.js";

/**
 * Pozisyon ve bakiye yonetimi.
 * - paper modda tamamen sanal bakiye ile calisir.
 * - live modda ayni risk kurallarini uygular ama emirleri Binance TR'ye gonderir.
 */
export class Portfolio {
  constructor() {
    this.quote = config.paperBalance; // TRY bakiyesi
    this.base = 0;                    // Coin miktari
    this.entryPrice = null;           // Acik pozisyonun giris fiyati
    this.trades = 0;
    this.wins = 0;
    this.realizedPnl = 0;
  }

  get inPosition() {
    return this.base > 0;
  }

  /** Zarar-durdur / kar-al kontrolu. Tetiklenirse satis nedeni dondurur. */
  checkExits(price) {
    if (!this.inPosition || this.entryPrice == null) return null;
    const changePct = ((price - this.entryPrice) / this.entryPrice) * 100;
    if (changePct <= -config.stopLossPct)
      return `Zarar durdur tetiklendi (%${changePct.toFixed(2)})`;
    if (changePct >= config.takeProfitPct)
      return `Kar al tetiklendi (%${changePct.toFixed(2)})`;
    return null;
  }

  async buy(price, reason) {
    if (this.inPosition) return;
    const budget = this.quote * (config.positionPct / 100);
    if (budget <= 0) {
      log.warn("Alim icin yeterli bakiye yok.");
      return;
    }
    const fee = budget * (config.feePct / 100);
    const qty = +((budget - fee) / price).toFixed(6);
    if (qty <= 0) return;

    if (config.tradeMode === "live") {
      await placeMarketOrder(config.symbol, "BUY", qty);
    }
    this.quote -= budget;
    this.base += qty;
    this.entryPrice = price;
    log.trade({ side: "AL", symbol: config.symbol, qty, price, reason, mode: config.tradeMode });
  }

  async sell(price, reason) {
    if (!this.inPosition) return;
    const qty = this.base;

    if (config.tradeMode === "live") {
      await placeMarketOrder(config.symbol, "SELL", qty);
    }
    const gross = qty * price;
    const fee = gross * (config.feePct / 100);
    const proceeds = gross - fee;
    const cost = qty * this.entryPrice;
    const pnl = proceeds - cost;

    this.quote += proceeds;
    this.base = 0;
    this.entryPrice = null;
    this.trades++;
    if (pnl > 0) this.wins++;
    this.realizedPnl += pnl;

    log.trade({
      side: "SAT", symbol: config.symbol, qty, price, reason,
      pnl: +pnl.toFixed(2), mode: config.tradeMode,
    });
  }

  summary(price) {
    const equity = this.quote + this.base * price;
    return (
      `Bakiye: ${this.quote.toFixed(2)} TRY | Coin: ${this.base} | ` +
      `Toplam deger: ${equity.toFixed(2)} TRY | ` +
      `Islem: ${this.trades} (kazanan: ${this.wins}) | ` +
      `Gerceklesen K/Z: ${this.realizedPnl.toFixed(2)} TRY`
    );
  }
}
