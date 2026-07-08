/**
 * Korelasyon korumasi.
 * Kripto pariteleri (ozellikle BTC/ETH gibi) cogu zaman birlikte hareket eder:
 * ikisinde birden pozisyon acmak riski cesitlendirmez, IKIYE KATLAR.
 * Yeni sembolun getiri korelasyonu, acik pozisyonlardan biriyle esigin
 * ustundeyse giris engellenir.
 */

/** Kapanis fiyatlarindan yuzde getiriler. */
export function toReturns(closes) {
  const out = [];
  for (let i = 1; i < closes.length; i++) {
    out.push(closes[i] / closes[i - 1] - 1);
  }
  return out;
}

/** Pearson korelasyon katsayisi (-1..1). Yetersiz/sabit veride 0. */
export function pearson(a, b) {
  const n = Math.min(a.length, b.length);
  if (n < 3) return 0;
  const xs = a.slice(-n), ys = b.slice(-n);
  const mx = xs.reduce((s, v) => s + v, 0) / n;
  const my = ys.reduce((s, v) => s + v, 0) / n;
  let cov = 0, vx = 0, vy = 0;
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - mx, dy = ys[i] - my;
    cov += dx * dy;
    vx += dx * dx;
    vy += dy * dy;
  }
  if (vx === 0 || vy === 0) return 0;
  return cov / Math.sqrt(vx * vy);
}

/**
 * Aday sembol, acik pozisyonlardan biriyle asiri korele mi?
 * @param {object} opts
 * @param {string}   opts.symbol      - aday sembol
 * @param {string[]} opts.openSymbols - acik pozisyonlu semboller
 * @param {function} opts.getCloses   - (symbol) => number[] kapanis dizisi
 * @param {number}   opts.maxCorr     - esik (0-1)
 * @param {number}   opts.window      - getiri penceresi
 * @returns {string|null} engel nedeni veya null
 */
export function correlationBlocked({ symbol, openSymbols, getCloses, maxCorr, window }) {
  if (!(maxCorr > 0)) return null;
  const myReturns = toReturns(getCloses(symbol).slice(-(window + 1)));
  if (myReturns.length < 3) return null;
  for (const other of openSymbols) {
    if (other === symbol) continue;
    const otherReturns = toReturns(getCloses(other).slice(-(window + 1)));
    const corr = pearson(myReturns, otherReturns);
    if (corr >= maxCorr) {
      return `Korelasyon korumasi: ${symbol}, acik ${other} pozisyonuyla %${(corr * 100).toFixed(0)} korele (esik %${(maxCorr * 100).toFixed(0)}) - ayni riske iki kez girilmez.`;
    }
  }
  return null;
}
