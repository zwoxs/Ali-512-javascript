import { ema, rsi, last, prevLast } from "./indicators.js";
import { config } from "./config.js";

/**
 * EMA kesisimi + RSI filtresi stratejisi.
 *
 * AL  : Hizli EMA yavas EMA'yi yukari keser VE RSI asiri alim bolgesinde degil
 * SAT : Hizli EMA yavas EMA'yi asagi keser VEYA RSI asiri alim bolgesine girer
 *
 * @param {number[]} closes - kapanis fiyatlari (eski -> yeni)
 * @returns {{signal: 'BUY'|'SELL'|'HOLD', reason: string, snapshot: object}}
 */
export function evaluate(closes) {
  const minBars = Math.max(config.emaSlow, config.rsiPeriod) + 2;
  if (closes.length < minBars) {
    return { signal: "HOLD", reason: `Yetersiz veri (${closes.length}/${minBars} mum)`, snapshot: {} };
  }

  const fast = ema(closes, config.emaFast);
  const slow = ema(closes, config.emaSlow);
  const rsiArr = rsi(closes, config.rsiPeriod);

  const snapshot = {
    price: last(closes),
    emaFast: +last(fast).toFixed(2),
    emaSlow: +last(slow).toFixed(2),
    rsi: +last(rsiArr).toFixed(1),
  };

  const crossedUp = prevLast(fast) <= prevLast(slow) && last(fast) > last(slow);
  const crossedDown = prevLast(fast) >= prevLast(slow) && last(fast) < last(slow);

  if (crossedUp && snapshot.rsi < config.rsiOverbought) {
    return { signal: "BUY", reason: `EMA${config.emaFast} > EMA${config.emaSlow} yukari kesisim, RSI=${snapshot.rsi}`, snapshot };
  }
  if (crossedDown) {
    return { signal: "SELL", reason: `EMA${config.emaFast} < EMA${config.emaSlow} asagi kesisim, RSI=${snapshot.rsi}`, snapshot };
  }
  if (snapshot.rsi >= config.rsiOverbought) {
    return { signal: "SELL", reason: `RSI asiri alim (${snapshot.rsi} >= ${config.rsiOverbought})`, snapshot };
  }
  return { signal: "HOLD", reason: "Sinyal yok", snapshot };
}
