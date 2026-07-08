// SuperTrend yon degisimi (ATR tabanli trend takip)
// AL : Trend asagidan yukariya doner (-1 -> 1)
// SAT: Trend yukaridan asagiya doner (1 -> -1)

import { supertrend, last, prevLast } from "../indicators.js";

export const name = "SuperTrend Yon Degisimi";

export function warmup(cfg) {
  return cfg.supertrendPeriod + 3;
}

export function evaluate(candles, cfg) {
  if (candles.length < warmup(cfg)) {
    return { signal: "HOLD", reason: `Yetersiz veri (${candles.length}/${warmup(cfg)})`, snapshot: {} };
  }

  const { trend, line } = supertrend(candles, cfg.supertrendPeriod, cfg.supertrendMult);
  if (trend.length < 2) {
    return { signal: "HOLD", reason: "Yetersiz SuperTrend verisi", snapshot: {} };
  }

  const snapshot = {
    price: last(candles).close,
    trend: last(trend),
    line: +last(line).toFixed(4),
  };

  if (prevLast(trend) === -1 && last(trend) === 1) {
    return { signal: "BUY", reason: `SuperTrend yukari dondu (cizgi: ${snapshot.line})`, snapshot };
  }
  if (prevLast(trend) === 1 && last(trend) === -1) {
    return { signal: "SELL", reason: `SuperTrend asagi dondu (cizgi: ${snapshot.line})`, snapshot };
  }
  return { signal: "HOLD", reason: `Trend ${snapshot.trend === 1 ? "yukari" : "asagi"}, degisim yok`, snapshot };
}
