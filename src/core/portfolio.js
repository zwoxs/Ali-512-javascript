/**
 * Portfoy muhasebesi - coklu sembol pozisyon takibi.
 * Emir GONDERMEZ; sadece bakiye/pozisyon/K-Z defteri tutar.
 * Emir yurutme Broker katmaninin, karar verme Engine'in isidir.
 */
export class Portfolio {
  constructor(initialQuote) {
    this.initialQuote = initialQuote;
    this.quote = initialQuote;            // TRY bakiyesi
    this.positions = new Map();           // symbol -> { qty, entryPrice, highWater, openedAt }
    this.trades = 0;
    this.wins = 0;
    this.realizedPnl = 0;
    this.tradeLog = [];                   // backtest metrikleri icin kapali islem listesi
  }

  getPosition(symbol) {
    return this.positions.get(symbol) || null;
  }

  inPosition(symbol) {
    return this.positions.has(symbol);
  }

  /** Broker fill'ini deftere isler (alis). */
  recordBuy(symbol, fill) {
    const cost = fill.qty * fill.price + fill.fee;
    this.quote -= cost;
    this.positions.set(symbol, {
      qty: fill.qty,
      entryPrice: fill.price,
      entryFee: fill.fee, // K/Z tam tur maliyetle hesaplanir (giris + cikis komisyonu)
      highWater: fill.price,
      openedAt: fill.ts,
    });
  }

  /** Broker fill'ini deftere isler (satis); gerceklesen K/Z dondurur. */
  recordSell(symbol, fill) {
    const pos = this.positions.get(symbol);
    if (!pos) throw new Error(`${symbol} icin acik pozisyon yok.`);
    const proceeds = fill.qty * fill.price - fill.fee;
    const cost = fill.qty * pos.entryPrice + (pos.entryFee || 0);
    const pnl = proceeds - cost;

    this.quote += proceeds;
    this.positions.delete(symbol);
    this.trades++;
    if (pnl > 0) this.wins++;
    this.realizedPnl += pnl;
    this.tradeLog.push({
      symbol,
      entryPrice: pos.entryPrice,
      exitPrice: fill.price,
      qty: fill.qty,
      pnl,
      openedAt: pos.openedAt,
      closedAt: fill.ts,
    });
    return pnl;
  }

  /** Iz suren stop icin pozisyonun gordugu en yuksek fiyati gunceller. */
  updateHighWater(symbol, price) {
    const pos = this.positions.get(symbol);
    if (pos && price > pos.highWater) pos.highWater = price;
  }

  /** Toplam varlik degeri (acik pozisyonlar guncel fiyattan). */
  equity(prices = {}) {
    let total = this.quote;
    for (const [symbol, pos] of this.positions) {
      total += pos.qty * (prices[symbol] ?? pos.entryPrice);
    }
    return total;
  }

  summary(prices = {}) {
    const eq = this.equity(prices);
    const openList = [...this.positions.entries()]
      .map(([s, p]) => `${s}:${p.qty}@${p.entryPrice}`)
      .join(", ") || "yok";
    return (
      `Bakiye: ${this.quote.toFixed(2)} TRY | Acik: ${openList} | ` +
      `Toplam: ${eq.toFixed(2)} TRY | Islem: ${this.trades} (kazanan: ${this.wins}) | ` +
      `Gerceklesen K/Z: ${this.realizedPnl.toFixed(2)} TRY`
    );
  }
}
