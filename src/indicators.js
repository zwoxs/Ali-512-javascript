// Teknik gostergeler - saf fonksiyonlar, yan etkisiz.
// Tum fonksiyonlar sayi dizisi alir (eski -> yeni) ve dizi dondurur.

export function sma(values, period) {
  if (values.length < period) return [];
  const out = [];
  let sum = values.slice(0, period).reduce((a, b) => a + b, 0);
  out.push(sum / period);
  for (let i = period; i < values.length; i++) {
    sum += values[i] - values[i - period];
    out.push(sum / period);
  }
  return out;
}

export function ema(values, period) {
  if (values.length < period) return [];
  const k = 2 / (period + 1);
  const out = [];
  let prev = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  out.push(prev);
  for (let i = period; i < values.length; i++) {
    prev = values[i] * k + prev * (1 - k);
    out.push(prev);
  }
  return out;
}

// Wilder yontemiyle RSI
export function rsi(values, period) {
  if (values.length <= period) return [];
  let gain = 0, loss = 0;
  for (let i = 1; i <= period; i++) {
    const diff = values[i] - values[i - 1];
    if (diff >= 0) gain += diff;
    else loss -= diff;
  }
  let avgGain = gain / period;
  let avgLoss = loss / period;
  const out = [avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss)];
  for (let i = period + 1; i < values.length; i++) {
    const diff = values[i] - values[i - 1];
    avgGain = (avgGain * (period - 1) + Math.max(diff, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-diff, 0)) / period;
    out.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
  }
  return out;
}

/**
 * MACD: { macd, signal, histogram } dizileri; uc dizi ayni hizada biter.
 */
export function macd(values, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
  const fast = ema(values, fastPeriod);
  const slow = ema(values, slowPeriod);
  if (slow.length === 0) return { macd: [], signal: [], histogram: [] };
  const aligned = fast.slice(fast.length - slow.length);
  const macdLine = aligned.map((v, i) => v - slow[i]);
  const signalLine = ema(macdLine, signalPeriod);
  if (signalLine.length === 0) return { macd: [], signal: [], histogram: [] };
  const macdAligned = macdLine.slice(macdLine.length - signalLine.length);
  return {
    macd: macdAligned,
    signal: signalLine,
    histogram: macdAligned.map((v, i) => v - signalLine[i]),
  };
}

/**
 * Bollinger bantlari: { middle, upper, lower } dizileri.
 */
export function bollinger(values, period = 20, stdDevMult = 2) {
  if (values.length < period) return { middle: [], upper: [], lower: [] };
  const middle = sma(values, period);
  const upper = [], lower = [];
  for (let i = 0; i < middle.length; i++) {
    const window = values.slice(i, i + period);
    const mean = middle[i];
    const variance = window.reduce((a, v) => a + (v - mean) ** 2, 0) / period;
    const sd = Math.sqrt(variance) * stdDevMult;
    upper.push(mean + sd);
    lower.push(mean - sd);
  }
  return { middle, upper, lower };
}

/**
 * ATR (Average True Range) - Wilder duzlestirmesi.
 * candles: [{high, low, close}] dizisi.
 */
export function atr(candles, period = 14) {
  if (candles.length <= period) return [];
  const trs = [];
  for (let i = 1; i < candles.length; i++) {
    const c = candles[i], prev = candles[i - 1];
    trs.push(Math.max(
      c.high - c.low,
      Math.abs(c.high - prev.close),
      Math.abs(c.low - prev.close)
    ));
  }
  let prevAtr = trs.slice(0, period).reduce((a, b) => a + b, 0) / period;
  const out = [prevAtr];
  for (let i = period; i < trs.length; i++) {
    prevAtr = (prevAtr * (period - 1) + trs[i]) / period;
    out.push(prevAtr);
  }
  return out;
}

/**
 * Donchian kanali: her nokta icin ONCEKI `period` mumun en yuksek/en dusugu
 * (mevcut mum haric - kirilim tespiti icin dogru referans).
 * Donen diziler candles.length - period uzunlugundadir.
 */
export function donchian(candles, period) {
  const upper = [], lower = [];
  for (let i = period; i < candles.length; i++) {
    let hi = -Infinity, lo = Infinity;
    for (let j = i - period; j < i; j++) {
      if (candles[j].high > hi) hi = candles[j].high;
      if (candles[j].low < lo) lo = candles[j].low;
    }
    upper.push(hi);
    lower.push(lo);
  }
  return { upper, lower };
}

/**
 * SuperTrend: ATR tabanli trend takip cizgisi.
 * @returns {{trend: number[], line: number[]}} trend: 1 (yukari) / -1 (asagi)
 */
export function supertrend(candles, period = 10, mult = 3) {
  const atrs = atr(candles, period);
  const trend = [], line = [];
  let prevUpper = Infinity, prevLower = -Infinity, prevTrend = 1;

  for (let k = 0; k < atrs.length; k++) {
    const i = k + period;
    const c = candles[i];
    const mid = (c.high + c.low) / 2;
    const rawUpper = mid + mult * atrs[k];
    const rawLower = mid - mult * atrs[k];

    let finalUpper = rawUpper, finalLower = rawLower;
    if (k > 0) {
      const prevClose = candles[i - 1].close;
      finalUpper = rawUpper < prevUpper || prevClose > prevUpper ? rawUpper : prevUpper;
      finalLower = rawLower > prevLower || prevClose < prevLower ? rawLower : prevLower;
    }

    let t;
    if (k === 0) t = c.close >= finalLower ? 1 : -1;
    else if (prevTrend === 1) t = c.close < finalLower ? -1 : 1;
    else t = c.close > finalUpper ? 1 : -1;

    trend.push(t);
    line.push(t === 1 ? finalLower : finalUpper);
    prevUpper = finalUpper;
    prevLower = finalLower;
    prevTrend = t;
  }
  return { trend, line };
}

export const last = (arr) => arr[arr.length - 1];
export const prevLast = (arr) => arr[arr.length - 2];
