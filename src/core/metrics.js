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

/**
 * Sortino orani: Sharpe gibi ama sadece asagi yonlu oynakligi cezalandirir.
 * Yukari volatilite "risk" sayilmaz - kurumsal raporlamada tercih edilir.
 */
export function sortinoRatio(equityCurve, barsPerYear) {
  if (equityCurve.length < 3) return 0;
  const returns = [];
  for (let i = 1; i < equityCurve.length; i++) {
    returns.push(equityCurve[i] / equityCurve[i - 1] - 1);
  }
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const downside = returns.filter((r) => r < 0);
  if (downside.length === 0) return mean > 0 ? Infinity : 0;
  const downsideDev = Math.sqrt(downside.reduce((a, r) => a + r ** 2, 0) / returns.length);
  if (downsideDev === 0) return 0;
  return (mean / downsideDev) * Math.sqrt(barsPerYear);
}

/** En uzun ardisik zarar serisi (kismi satislar haric). */
export function longestLossStreak(trades) {
  let streak = 0, longest = 0;
  for (const t of trades) {
    if (t.partial) continue;
    if (t.pnl < 0) longest = Math.max(longest, ++streak);
    else streak = 0;
  }
  return longest;
}

export function computeMetrics({ equityCurve, trades, initialBalance, barsPerYear, exposureBars = null }) {
  const finalEquity = equityCurve[equityCurve.length - 1] ?? initialBalance;
  const wins = trades.filter((t) => t.pnl > 0);
  const losses = trades.filter((t) => t.pnl <= 0);
  const avg = (arr) => (arr.length ? arr.reduce((a, t) => a + t.pnl, 0) / arr.length : 0);

  const years = equityCurve.length / barsPerYear;
  const cagrPct = years > 0 && finalEquity > 0
    ? ((finalEquity / initialBalance) ** (1 / years) - 1) * 100
    : 0;
  const maxDrawdownPct = maxDrawdown(equityCurve);

  return {
    totalReturnPct: ((finalEquity - initialBalance) / initialBalance) * 100,
    finalEquity,
    tradeCount: trades.length,
    winCount: wins.length,
    winRatePct: trades.length ? (wins.length / trades.length) * 100 : 0,
    avgWin: avg(wins),
    avgLoss: avg(losses),
    profitFactor: profitFactor(trades),
    maxDrawdownPct,
    sharpe: sharpeRatio(equityCurve, barsPerYear),
    sortino: sortinoRatio(equityCurve, barsPerYear),
    cagrPct,
    calmar: maxDrawdownPct > 0 ? cagrPct / maxDrawdownPct : 0,
    exposurePct: exposureBars != null && equityCurve.length
      ? (exposureBars / equityCurve.length) * 100
      : null,
    longestLossStreak: longestLossStreak(trades),
  };
}
