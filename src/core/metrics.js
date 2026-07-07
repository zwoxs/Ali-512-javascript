/**
 * Backtest performans metrikleri - kurumsal degerlendirme olcutleri.
 */

/** Ozsermaye egrisinden maksimum dusus (max drawdown) yuzdesi. */
export function maxDrawdown(equityCurve) {
  let peak = -Infinity;
  let maxDd = 0;
  for (const eq of equityCurve) {
    if (eq > peak) peak = eq;
    const dd = ((peak - eq) / peak) * 100;
    if (dd > maxDd) maxDd = dd;
  }
  return maxDd;
}

/**
 * Yillik Sharpe orani (risksiz faiz 0 varsayimi).
 * @param {number[]} equityCurve - bar basina ozsermaye
 * @param {number} barsPerYear   - yilda kac bar (or. 1h icin 8760)
 */
export function sharpeRatio(equityCurve, barsPerYear) {
  if (equityCurve.length < 3) return 0;
  const returns = [];
  for (let i = 1; i < equityCurve.length; i++) {
    returns.push(equityCurve[i] / equityCurve[i - 1] - 1);
  }
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((a, r) => a + (r - mean) ** 2, 0) / returns.length;
  const sd = Math.sqrt(variance);
  if (sd === 0) return 0;
  return (mean / sd) * Math.sqrt(barsPerYear);
}

/** Kar faktoru: brut kar / brut zarar. >1 karli sistemi gosterir. */
export function profitFactor(trades) {
  let grossProfit = 0, grossLoss = 0;
  for (const t of trades) {
    if (t.pnl >= 0) grossProfit += t.pnl;
    else grossLoss -= t.pnl;
  }
  if (grossLoss === 0) return grossProfit > 0 ? Infinity : 0;
  return grossProfit / grossLoss;
}

export function computeMetrics({ equityCurve, trades, initialBalance, barsPerYear }) {
  const finalEquity = equityCurve[equityCurve.length - 1] ?? initialBalance;
  const wins = trades.filter((t) => t.pnl > 0);
  const losses = trades.filter((t) => t.pnl <= 0);
  const avg = (arr) => (arr.length ? arr.reduce((a, t) => a + t.pnl, 0) / arr.length : 0);

  return {
    totalReturnPct: ((finalEquity - initialBalance) / initialBalance) * 100,
    finalEquity,
    tradeCount: trades.length,
    winCount: wins.length,
    winRatePct: trades.length ? (wins.length / trades.length) * 100 : 0,
    avgWin: avg(wins),
    avgLoss: avg(losses),
    profitFactor: profitFactor(trades),
    maxDrawdownPct: maxDrawdown(equityCurve),
    sharpe: sharpeRatio(equityCurve, barsPerYear),
  };
}
