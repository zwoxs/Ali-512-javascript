// Bollinger bandi ortalamaya donus (mean reversion)
// AL : Kapanis alt bandin altinda VE RSI asiri satim bolgesinde
// SAT: Kapanis ust bandin ustunde VEYA orta banda (SMA) geri donus

import { bollinger, rsi, last } from "../indicators.js";

export const name = "Bollinger Ortalamaya Donus";

export function warmup(cfg) {
  return Math.max(cfg.bbPeriod, cfg.rsiPeriod) + 2;
}

export function evaluate(candles, cfg) {
  const closes = candles.map((c) => c.close);
  if (closes.length < warmup(cfg)) {
    return { signal: "HOLD", reason: `Yetersiz veri (${closes.length}/${warmup(cfg)})`, snapshot: {} };
  }

  const { middle, upper, lower } = bollinger(closes, cfg.bbPeriod, cfg.bbStdDev);
  const rsiArr = rsi(closes, cfg.rsiPeriod);
  const price = last(closes);

  const snapshot = {
    price,
    bbUpper: +last(upper).toFixed(4),
    bbMiddle: +last(middle).toFixed(4),
    bbLower: +last(lower).toFixed(4),
    rsi: +last(rsiArr).toFixed(1),
  };

  if (price < snapshot.bbLower && snapshot.rsi <= cfg.rsiOversold) {
    return { signal: "BUY", reason: `Fiyat alt bandin altinda, RSI=${snapshot.rsi} asiri satim`, snapshot };
  }
  if (price > snapshot.bbUpper) {
    return { signal: "SELL", reason: `Fiyat ust bandin ustunde (${price} > ${snapshot.bbUpper})`, snapshot };
  }
  if (price >= snapshot.bbMiddle && snapshot.rsi >= 55) {
    return { signal: "SELL", reason: `Orta banda donus tamamlandi (RSI=${snapshot.rsi})`, snapshot };
  }
  return { signal: "HOLD", reason: "Sinyal yok", snapshot };
}
