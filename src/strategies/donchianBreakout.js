// Donchian kanal kirilimi (Turtle Traders klasigi - trend takip)
// AL : Kapanis, onceki DONCHIAN_ENTRY mumun en yuksegini kirar
// SAT: Kapanis, onceki DONCHIAN_EXIT mumun en dusugunu kirar

import { donchian, last } from "../indicators.js";

export const name = "Donchian Kanal Kirilimi";

export function warmup(cfg) {
  return cfg.donchianEntry + 2;
}

export function evaluate(candles, cfg) {
  if (candles.length < warmup(cfg)) {
    return { signal: "HOLD", reason: `Yetersiz veri (${candles.length}/${warmup(cfg)})`, snapshot: {} };
  }

  const entry = donchian(candles, cfg.donchianEntry);
  const exit = donchian(candles, cfg.donchianExit);
  const price = last(candles).close;

  const snapshot = {
    price,
    entryHigh: +last(entry.upper).toFixed(4),
    exitLow: +last(exit.lower).toFixed(4),
  };

  if (price > snapshot.entryHigh) {
    return { signal: "BUY", reason: `${cfg.donchianEntry} mumluk zirve kirildi (${price} > ${snapshot.entryHigh})`, snapshot };
  }
  if (price < snapshot.exitLow) {
    return { signal: "SELL", reason: `${cfg.donchianExit} mumluk dip kirildi (${price} < ${snapshot.exitLow})`, snapshot };
  }
  return { signal: "HOLD", reason: "Kanal icinde", snapshot };
}
