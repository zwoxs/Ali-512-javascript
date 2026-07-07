// Strateji kayit defteri.
// Her strateji ayni sozlesmeyi uygular:
//   warmup(cfg)            -> sinyal uretmek icin gereken minimum mum sayisi
//   evaluate(candles, cfg) -> { signal: 'BUY'|'SELL'|'HOLD', reason, snapshot }
// Yeni strateji eklemek icin: dosyayi yaz, buraya kaydet, .env'de STRATEGY ayarla.

import * as emaRsi from "./emaRsi.js";
import * as macdCross from "./macdCross.js";
import * as bollingerRevert from "./bollingerRevert.js";
import * as donchianBreakout from "./donchianBreakout.js";
import * as supertrendFlip from "./supertrendFlip.js";

const REGISTRY = {
  ema_rsi: emaRsi,
  macd: macdCross,
  bollinger: bollingerRevert,
  donchian: donchianBreakout,
  supertrend: supertrendFlip,
};

export function getStrategy(name) {
  const strategy = REGISTRY[name];
  if (!strategy) {
    throw new Error(`Bilinmeyen strateji: '${name}'. Gecerli: ${Object.keys(REGISTRY).join(", ")}`);
  }
  return strategy;
}

export const strategyNames = Object.keys(REGISTRY);
