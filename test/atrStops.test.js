import { test } from "node:test";
import assert from "node:assert/strict";
import { RiskManager } from "../src/core/riskManager.js";

const atrCfg = {
  sizingMode: "risk",
  positionPct: 25,
  riskPerTradePct: 1,
  stopMode: "atr",
  stopLossPct: 2,
  takeProfitPct: 4,
  trailingStopPct: 0,
  atrPeriod: 14,
  atrStopMult: 2,
  atrTpMult: 3,
  maxDailyLossPct: 5,
  maxConsecutiveLosses: 3,
  cooldownMinutes: 60,
  feePct: 0.1,
};

test("ATR stop: giris - 2xATR altinda tetiklenir, ustunde tetiklenmez", () => {
  const rm = new RiskManager(atrCfg);
  const pos = { entryPrice: 100, highWater: 100, entryAtr: 3 }; // stop = 94, tp = 109
  assert.ok(rm.checkExit(pos, 93.9)?.includes("ATR zarar durdur"));
  assert.equal(rm.checkExit(pos, 94.5), null);
  assert.ok(rm.checkExit(pos, 109.1)?.includes("ATR kar al"));
  assert.equal(rm.checkExit(pos, 108), null);
});

test("ATR modu: entryAtr yoksa yuzde stoplara geri duser", () => {
  const rm = new RiskManager(atrCfg);
  const pos = { entryPrice: 100, highWater: 100 };
  assert.ok(rm.checkExit(pos, 97.9)?.includes("Zarar durdur"));
});

test("risk boyutlama ATR ile: volatilite artinca pozisyon kuculur", () => {
  const rm = new RiskManager(atrCfg);
  const calm = rm.positionSize(100000, 100000, 100, 1);   // stop mesafesi 2
  const wild = rm.positionSize(100000, 100000, 100, 5);   // stop mesafesi 10
  assert.ok(calm > wild, "sakin piyasada daha buyuk pozisyon alinabilmeli");
});

test("stopDistance: ATR modunda carpan, yoksa yuzde", () => {
  const rm = new RiskManager(atrCfg);
  assert.equal(rm.stopDistance(100, 3), 6);       // 3 ATR x 2
  assert.equal(rm.stopDistance(100, null), 2);    // %2 fallback
  const pctRm = new RiskManager({ ...atrCfg, stopMode: "percent" });
  assert.equal(pctRm.stopDistance(100, 3), 2);    // percent modda ATR yok sayilir
});
