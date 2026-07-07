import { test } from "node:test";
import assert from "node:assert/strict";
import { RiskManager } from "../src/core/riskManager.js";

const baseCfg = {
  sizingMode: "percent",
  positionPct: 25,
  riskPerTradePct: 1,
  stopLossPct: 2,
  takeProfitPct: 4,
  trailingStopPct: 0,
  maxDailyLossPct: 5,
  maxConsecutiveLosses: 3,
  cooldownMinutes: 60,
  feePct: 0.1,
};

test("percent boyutlama: bakiyenin %25'i kadar (komisyon dusulmus)", () => {
  const rm = new RiskManager(baseCfg);
  const qty = rm.positionSize(10000, 10000, 100);
  // 2500 butce - %0.1 komisyon = 2497.5 / 100 = 24.975
  assert.ok(Math.abs(qty - 24.975) < 1e-9);
});

test("risk boyutlama: stop mesafesi genisledikce pozisyon kuculur", () => {
  const narrow = new RiskManager({ ...baseCfg, sizingMode: "risk", stopLossPct: 1 });
  const wide = new RiskManager({ ...baseCfg, sizingMode: "risk", stopLossPct: 4 });
  assert.ok(narrow.positionSize(100000, 100000, 100) > wide.positionSize(100000, 100000, 100));
});

test("risk boyutlama asla bakiyeyi asamaz", () => {
  const rm = new RiskManager({ ...baseCfg, sizingMode: "risk", riskPerTradePct: 10, stopLossPct: 0.5 });
  const qty = rm.positionSize(1000, 1000, 100);
  assert.ok(qty * 100 <= 1000);
});

test("stop-loss ve take-profit dogru tetiklenir", () => {
  const rm = new RiskManager(baseCfg);
  const pos = { entryPrice: 100, highWater: 100 };
  assert.ok(rm.checkExit(pos, 97.9)?.includes("Zarar durdur"));
  assert.ok(rm.checkExit(pos, 104.1)?.includes("Kar al"));
  assert.equal(rm.checkExit(pos, 100.5), null);
});

test("iz suren stop: zirveden geri cekilmede tetiklenir", () => {
  const rm = new RiskManager({ ...baseCfg, trailingStopPct: 1.5 });
  const pos = { entryPrice: 100, highWater: 103.5 };
  // 103.5 zirveden %1.5+ geri cekilme: 101.9 (hala giris ustu -> kar kilitleme)
  assert.ok(rm.checkExit(pos, 101.9)?.includes("Iz suren stop"));
  assert.equal(rm.checkExit(pos, 103.0), null);
});

test("ust uste zarar sogurma suresi baslatir", () => {
  let now = 1_000_000_000_000;
  const rm = new RiskManager({ ...baseCfg, maxConsecutiveLosses: 2 }, () => now);
  assert.equal(rm.canOpen(), null);
  rm.onTradeClosed(-10, 10000);
  assert.equal(rm.canOpen(), null);
  rm.onTradeClosed(-10, 10000);
  assert.ok(rm.canOpen()?.includes("Sogurma"));
  now += 61 * 60_000; // 61 dakika sonra serbest
  assert.equal(rm.canOpen(), null);
});

test("gunluk zarar limiti devre kesicisi ve gun donusunde sifirlanma", () => {
  let now = Date.parse("2026-01-05T10:00:00Z");
  const rm = new RiskManager(baseCfg, () => now);
  rm.onTradeClosed(-600, 10000); // %6 > %5 limit
  assert.ok(rm.canOpen()?.includes("Gunluk zarar limiti"));
  now = Date.parse("2026-01-06T10:00:00Z"); // ertesi gun
  assert.equal(rm.canOpen(), null);
});

test("kazanc ust uste zarar sayacini sifirlar", () => {
  const rm = new RiskManager(baseCfg);
  rm.onTradeClosed(-10, 10000);
  rm.onTradeClosed(-10, 10000);
  rm.onTradeClosed(50, 10000);
  assert.equal(rm.consecutiveLosses, 0);
});
