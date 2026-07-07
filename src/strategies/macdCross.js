// MACD sinyal cizgisi kesisimi (momentum)
// AL : MACD cizgisi sinyal cizgisini yukari keser VE histogram artiyor
// SAT: MACD cizgisi sinyal cizgisini asagi keser

import { macd, last, prevLast } from "../indicators.js";

export const name = "MACD Kesisimi";

export function warmup(cfg) {
  return cfg.macdSlow + cfg.macdSignal + 2;
}

export function evaluate(candles, cfg) {
  const closes = candles.map((c) => c.close);
  if (closes.length < warmup(cfg)) {
    return { signal: "HOLD", reason: `Yetersiz veri (${closes.length}/${warmup(cfg)})`, snapshot: {} };
  }

  const { macd: macdLine, signal: signalLine, histogram } = macd(
    closes, cfg.macdFast, cfg.macdSlow, cfg.macdSignal
  );
  if (macdLine.length < 2) {
    return { signal: "HOLD", reason: "Yetersiz MACD verisi", snapshot: {} };
  }

  const snapshot = {
    price: last(closes),
    macd: +last(macdLine).toFixed(4),
    signal: +last(signalLine).toFixed(4),
    histogram: +last(histogram).toFixed(4),
  };

  const crossedUp = prevLast(macdLine) <= prevLast(signalLine) && last(macdLine) > last(signalLine);
  const crossedDown = prevLast(macdLine) >= prevLast(signalLine) && last(macdLine) < last(signalLine);
  const momentumRising = last(histogram) > prevLast(histogram);

  if (crossedUp && momentumRising) {
    return { signal: "BUY", reason: `MACD yukari kesisim (hist=${snapshot.histogram})`, snapshot };
  }
  if (crossedDown) {
    return { signal: "SELL", reason: `MACD asagi kesisim (hist=${snapshot.histogram})`, snapshot };
  }
  return { signal: "HOLD", reason: "Sinyal yok", snapshot };
}
