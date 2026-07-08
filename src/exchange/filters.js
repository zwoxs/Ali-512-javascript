/**
 * Borsa emir filtresi uyumu (saf mantik - ag yok, test edilebilir).
 *
 * Binance emirleri su filtrelere tabidir; ihlal eden emir borsada REDDEDILIR:
 *  - LOT_SIZE     : miktar stepSize'in kati olmali, minQty'den buyuk olmali
 *  - MIN_NOTIONAL : emir degeri (miktar * fiyat) minNotional'den buyuk olmali
 *  - PRICE_FILTER : (limit emirler icin) fiyat tickSize'in kati olmali
 *
 * Bu filtreleri emir GONDERMEDEN once uygulamak, borsa reddini (ve onun
 * gereksiz devre kesici tetiklemesini) onler.
 */

/** exchangeInfo sembol nesnesinden filtre degerlerini cikarir. */
export function parseFilters(symbolInfo) {
  const filters = symbolInfo?.filters || [];
  const find = (type) => filters.find((f) => f.filterType === type) || {};
  const lot = find("LOT_SIZE");
  const notional = find("MIN_NOTIONAL");
  const notional2 = find("NOTIONAL"); // bazi pariteler bu adi kullanir
  const price = find("PRICE_FILTER");
  return {
    stepSize: parseFloat(lot.stepSize) || 0.000001,
    minQty: parseFloat(lot.minQty) || 0,
    minNotional: parseFloat(notional.minNotional ?? notional2.minNotional) || 0,
    tickSize: parseFloat(price.tickSize) || 0,
  };
}

/** Degeri adim buyuklugune asagi yuvarlar (kayan nokta artigini temizler). */
export function floorToStep(value, step) {
  if (!step || step <= 0) return value;
  const rounded = Math.floor(value / step) * step;
  const decimals = Math.max(0, Math.ceil(-Math.log10(step)));
  return parseFloat(rounded.toFixed(decimals));
}

/**
 * Emri filtrelere gore dogrular ve miktari uyumlu hale getirir.
 * @param {object} opts - { qty, price, filters }
 * @returns {{ok: boolean, qty: number, reason?: string}}
 */
export function validateOrder({ qty, price, filters }) {
  const f = filters || {};
  const adjustedQty = floorToStep(qty, f.stepSize);

  if (adjustedQty <= 0) {
    return { ok: false, qty: 0, reason: "yuvarlama sonrasi miktar sifir" };
  }
  if (f.minQty && adjustedQty < f.minQty) {
    return { ok: false, qty: adjustedQty, reason: `miktar ${adjustedQty} < minQty ${f.minQty}` };
  }
  if (f.minNotional && adjustedQty * price < f.minNotional) {
    return {
      ok: false, qty: adjustedQty,
      reason: `emir degeri ${(adjustedQty * price).toFixed(2)} < MIN_NOTIONAL ${f.minNotional}`,
    };
  }
  return { ok: true, qty: adjustedQty };
}
