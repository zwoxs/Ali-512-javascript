/**
 * Islem seansi filtresi.
 * Kripto 7/24 acik olsa da dusuk likidite saatlerinde (gece yarisi UTC, hafta
 * sonu) spread genisler ve dolumlar kotu olur. Bu filtre girisleri sadece
 * belirtilen UTC saat ve gun araligiyla sinirlar. Cikislari ETKILEMEZ -
 * acik pozisyon her zaman korunur/kapatilir.
 */

/** "6-22" -> {start:6, end:22}. Gece devri destegi: "22-4" (22:00-04:00). */
export function parseRange(str) {
  const [a, b] = str.split("-").map((n) => parseInt(n, 10));
  return { start: a, end: b };
}

/** Deger araligin icinde mi? Gece devrini (start > end) destekler. */
export function inRange(value, { start, end }) {
  if (start <= end) return value >= start && value <= end;
  return value >= start || value <= end; // devir: or. 22-4
}

/**
 * Verilen zaman (ms) islem seansi icinde mi?
 * @param {number} ts - epoch ms
 * @param {object} cfg - { sessionFilter, sessionHours, sessionDays }
 * @returns {boolean}
 */
export function inSession(ts, cfg) {
  if (!cfg.sessionFilter) return true;
  const d = new Date(ts);
  const hour = d.getUTCHours();
  const day = d.getUTCDay(); // 0=Pazar..6=Cumartesi
  return inRange(hour, parseRange(cfg.sessionHours)) && inRange(day, parseRange(cfg.sessionDays));
}
