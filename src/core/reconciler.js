/**
 * Hesap mutabakati (reconciliation).
 * Botun ic durumu (Portfolio) zamanla borsadaki gercek bakiyeden sapabilir:
 * kismi dolumlar, manuel islemler, yuvarlama, borsa tarafi kesintiler...
 * Gercek parada bu sapmayi FARK ETMEMEK tehlikelidir. Bu modul borsa
 * bakiyeleriyle ic durumu karsilastirir ve tolerans asilirsa uyarir.
 */

/**
 * Binance TR /open/v1/account/spot yanitindaki varliklari
 * { ASSET: serbest+kilitli } haritasina cevirir. Farkli sema alanlarina toleransli.
 */
export function parseBalances(account) {
  const list = account?.data?.accountAssets || account?.data?.balances || account?.balances || [];
  const out = {};
  for (const a of list) {
    const asset = (a.asset || a.symbol || "").toUpperCase();
    if (!asset) continue;
    const free = parseFloat(a.free ?? a.available ?? 0) || 0;
    const locked = parseFloat(a.locked ?? a.freeze ?? 0) || 0;
    out[asset] = free + locked;
  }
  return out;
}

/** SYMBOL sonundaki kote varligi ayirir: BTCTRY -> {base:"BTC", quote:"TRY"}. */
export function splitSymbol(symbol, quoteAssets = ["TRY", "USDT", "BTC", "ETH", "USD"]) {
  const s = symbol.toUpperCase();
  for (const q of quoteAssets) {
    if (s.endsWith(q) && s.length > q.length) return { base: s.slice(0, -q.length), quote: q };
  }
  return { base: s, quote: "" };
}

/**
 * Ic durum ile borsa bakiyelerini karsilastirir.
 * @param {object} portfolio - { positions: Map, quote: number }
 * @param {object} balances  - parseBalances ciktisi (ASSET -> miktar)
 * @param {object} opts - { tolerancePct, quoteAsset }
 * @returns {{ok: boolean, drifts: Array<{asset,internal,exchange,diffPct}>}}
 */
export function reconcile(portfolio, balances, { tolerancePct = 2, quoteAsset = "TRY" } = {}) {
  const drifts = [];
  const check = (asset, internal) => {
    const exchange = balances[asset] ?? 0;
    const denom = Math.max(Math.abs(internal), Math.abs(exchange), 1e-9);
    const diffPct = (Math.abs(internal - exchange) / denom) * 100;
    if (diffPct > tolerancePct) drifts.push({ asset, internal, exchange, diffPct });
  };

  // Kote varlik (nakit) mutabakati
  check(quoteAsset, portfolio.quote);

  // Her acik pozisyonun taban varligi
  for (const [symbol, pos] of portfolio.positions) {
    const { base } = splitSymbol(symbol);
    check(base, pos.qty);
  }

  return { ok: drifts.length === 0, drifts };
}

/** Sapmalari okunur metne cevirir (bildirim/log icin). */
export function formatDrift(drifts) {
  return drifts
    .map((d) => `${d.asset}: ic=${d.internal.toFixed(6)} borsa=${d.exchange.toFixed(6)} (%${d.diffPct.toFixed(1)} sapma)`)
    .join("; ");
}
