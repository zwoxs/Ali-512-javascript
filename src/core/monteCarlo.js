/**
 * Monte Carlo saglamlik analizi.
 *
 * Backtest'teki islem sirasi tek bir tarihsel tesadüftur. Islemlerin sirasi
 * `runs` kez rastgele karistirilarak binlerce alternatif ozsermaye yolu
 * uretilir. Dagilim genisse sonuc "sansli siralamaya" bagimlidir:
 * p95 dusus, tek backtest'in gosterdiginden cok daha buyuk olabilir.
 */

/** Tekrarlanabilir testler icin basit LCG rastgele sayi ureteci. */
export function makeLcg(seed = 42) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

/**
 * @param {object} opts
 * @param {Array}  opts.trades         - backtest islem defteri ({pnl} yeterli)
 * @param {number} opts.initialBalance
 * @param {number} [opts.runs]
 * @param {number} [opts.ruinThresholdPct] - sermayenin bu %'sine dusen yol "iflas" sayilir
 * @param {function} [opts.rng]
 * @returns {object|null} islem sayisi < 5 ise null (anlamli dagilim cikmaz)
 */
export function monteCarlo({ trades, initialBalance, runs = 1000, ruinThresholdPct = 50, rng = Math.random }) {
  const pnls = trades.map((t) => t.pnl);
  if (pnls.length < 5) return null;

  const finals = [];
  const drawdowns = [];
  let ruinCount = 0;
  const ruinLevel = initialBalance * (ruinThresholdPct / 100);

  for (let r = 0; r < runs; r++) {
    // Fisher-Yates karistirma
    const shuffled = [...pnls];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }

    let equity = initialBalance, peak = initialBalance, maxDd = 0, ruined = false;
    for (const pnl of shuffled) {
      equity += pnl;
      if (equity > peak) peak = equity;
      const dd = ((peak - equity) / peak) * 100;
      if (dd > maxDd) maxDd = dd;
      if (equity <= ruinLevel) ruined = true;
    }
    finals.push(equity);
    drawdowns.push(maxDd);
    if (ruined) ruinCount++;
  }

  finals.sort((a, b) => a - b);
  drawdowns.sort((a, b) => a - b);
  const pct = (arr, p) => arr[Math.min(arr.length - 1, Math.floor(p * arr.length))];
  const toReturnPct = (eq) => ((eq - initialBalance) / initialBalance) * 100;

  return {
    runs,
    p5ReturnPct: toReturnPct(pct(finals, 0.05)),
    p50ReturnPct: toReturnPct(pct(finals, 0.5)),
    p95ReturnPct: toReturnPct(pct(finals, 0.95)),
    p50DrawdownPct: pct(drawdowns, 0.5),
    p95DrawdownPct: pct(drawdowns, 0.95),
    ruinThresholdPct,
    ruinProbabilityPct: (ruinCount / runs) * 100,
  };
}
