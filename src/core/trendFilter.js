import { ema, adx } from "../indicators.js";

/**
 * Ust zaman dilimi (HTF) trend filtresi.
 * Taban mumlardan HTF mumlari turetir (or. 15m x4 = 1h) ve HTF EMA'sina gore
 * trend yonunu belirler. Dusus trendinde AL sinyalleri engellenerek
 * "dusen bicagi tutma" islemleri onlenir.
 */

/** Taban mumlari groupSize'lik gruplara toplayip HTF kapanislarini dondurur (sondan hizali). */
export function aggregateCloses(candles, groupSize) {
  const complete = Math.floor(candles.length / groupSize);
  if (complete === 0) return [];
  const start = candles.length - complete * groupSize;
  const closes = [];
  for (let i = 0; i < complete; i++) {
    closes.push(candles[start + (i + 1) * groupSize - 1].close);
  }
  return closes;
}

/**
 * HTF trend yukari mi? Veri filtre icin yetersizse true dondurur (filtre uygulanmaz).
 */
export function isUptrend(candles, cfg) {
  const htfCloses = aggregateCloses(candles, cfg.htfMultiple);
  if (htfCloses.length < cfg.htfEmaPeriod + 1) return true;
  const e = ema(htfCloses, cfg.htfEmaPeriod);
  return htfCloses[htfCloses.length - 1] > e[e.length - 1];
}

/**
 * ADX rejim filtresi: piyasa trendli mi? Trendsiz/testere piyasada (dusuk ADX)
 * trend takip stratejileri arka arkaya kucuk zararlar uretir - girisleri engelle.
 * Veri yetersizse true dondurur (filtre uygulanmaz).
 */
export function isTrendingMarket(candles, cfg) {
  const values = adx(candles, cfg.adxPeriod);
  if (!values.length) return true;
  return values[values.length - 1] >= cfg.adxMinimum;
}
