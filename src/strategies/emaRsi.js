// EMA kesisimi + RSI filtresi (trend takip)
// AL : Hizli EMA yavas EMA'yi yukari keser VE RSI asiri alimda degil
// SAT: Asagi kesisim VEYA RSI asiri alim bolgesi

import { ema, rsi, last, prevLast } from "../indicators.js";

export const name = "EMA Kesisimi + RSI Filtresi";

export function warmup(cfg) {
  return Math.max(cfg.emaSlow, cfg.rsiPeriod) + 2;
}

export function evaluate(candles, cfg) {
  const closes = candles.map((c) => c.close);
  if (closes.length < warmup(cfg)) {
    return { signal: "HOLD", reason: `Yetersiz veri (${closes.length}/${warmup(cfg)})`, snapshot: {} };
  }

  const fast = ema(closes, cfg.emaFast);
  const slow = ema(closes, cfg.emaSlow);
  const rsiArr = rsi(closes, cfg.rsiPeriod);

  const snapshot = {
    price: last(closes),
    emaFast: +last(fast).toFixed(4),
    emaSlow: +last(slow).toFixed(4),
    rsi: +last(rsiArr).toFixed(1),
  };

  const crossedUp = prevLast(fast) <= prevLast(slow) && last(fast) > last(slow);
  const crossedDown = prevLast(fast) >= prevLast(slow) && last(fast) < last(slow);

  if (crossedUp && snapshot.rsi < cfg.rsiOverbought) {
    return { signal: "BUY", reason: `EMA${cfg.emaFast}>EMA${cfg.emaSlow} yukari kesisim, RSI=${snapshot.rsi}`, snapshot };
  }
  if (crossedDown) {
    return { signal: "SELL", reason: `EMA${cfg.emaFast}<EMA${cfg.emaSlow} asagi kesisim, RSI=${snapshot.rsi}`, snapshot };
  }
  if (snapshot.rsi >= cfg.rsiOverbought) {
    return { signal: "SELL", reason: `RSI asiri alim (${snapshot.rsi}>=${cfg.rsiOverbought})`, snapshot };
  }
  return { signal: "HOLD", reason: "Sinyal yok", snapshot };
}
