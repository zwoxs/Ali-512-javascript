/**
 * Likidite/hacim filtresi.
 * Son kapanmis mumun hacmi, onceki mumlarin ortalamasinin belirli bir katinin
 * altindaysa piyasa "ince" demektir: market emri fiyati kaydirir, kotu dolum
 * olur. Bu durumda giris engellenir.
 */

/**
 * Son mumun hacmi yeterli mi?
 * @param {Array} candles - kapanmis mumlar (volume alani ile)
 * @param {object} cfg - { volumeFilter, volumeMinRatio, volumeAvgPeriod }
 * @returns {boolean} yeterliyse (veya filtre kapali/veri az) true
 */
export function hasSufficientVolume(candles, cfg) {
  if (!cfg.volumeFilter) return true;
  const period = cfg.volumeAvgPeriod;
  if (candles.length < period + 1) return true; // veri yetersiz: filtre uygulanmaz

  const window = candles.slice(-(period + 1), -1); // son mum haric onceki `period` mum
  const avg = window.reduce((s, c) => s + (c.volume || 0), 0) / window.length;
  if (avg <= 0) return true; // hacim verisi yoksa engelleme
  const current = candles[candles.length - 1].volume || 0;
  return current >= avg * cfg.volumeMinRatio;
}
