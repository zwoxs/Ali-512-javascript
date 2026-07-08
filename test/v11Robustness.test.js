import { test } from "node:test";
import assert from "node:assert/strict";
import { parseFilters, floorToStep, validateOrder } from "../src/exchange/filters.js";
import { validateState } from "../src/state.js";
import { RiskManager } from "../src/core/riskManager.js";

// --- Borsa filtre uyumu ---

test("parseFilters: exchangeInfo'dan LOT_SIZE / MIN_NOTIONAL / PRICE cikarir", () => {
  const info = { filters: [
    { filterType: "LOT_SIZE", stepSize: "0.00001000", minQty: "0.00010000" },
    { filterType: "MIN_NOTIONAL", minNotional: "10.00000000" },
    { filterType: "PRICE_FILTER", tickSize: "0.01000000" },
  ] };
  const f = parseFilters(info);
  assert.ok(Math.abs(f.stepSize - 0.00001) < 1e-12);
  assert.ok(Math.abs(f.minQty - 0.0001) < 1e-12);
  assert.equal(f.minNotional, 10);
  assert.equal(f.tickSize, 0.01);
});

test("parseFilters: NOTIONAL (alternatif ad) da taninir, eksikte guvenli varsayilan", () => {
  const alt = parseFilters({ filters: [{ filterType: "NOTIONAL", minNotional: "5" }] });
  assert.equal(alt.minNotional, 5);
  const empty = parseFilters({ filters: [] });
  assert.ok(empty.stepSize > 0 && empty.minNotional === 0);
});

test("floorToStep: adima yuvarlar, artik birakmaz", () => {
  assert.equal(floorToStep(1.23456789, 0.001), 1.234);
  assert.equal(floorToStep(0.00009, 0.0001), 0);
  assert.equal(floorToStep(5, 0), 5); // step yoksa degismez
});

test("validateOrder: MIN_NOTIONAL ve minQty ihlallerini yakalar", () => {
  const filters = { stepSize: 0.0001, minQty: 0.001, minNotional: 10 };
  // Yeterli: 0.5 * 100 = 50 >= 10
  const okOrder = validateOrder({ qty: 0.5, price: 100, filters });
  assert.ok(okOrder.ok && okOrder.qty === 0.5);
  // MIN_NOTIONAL alti: 0.05 * 100 = 5 < 10
  const small = validateOrder({ qty: 0.05, price: 100, filters });
  assert.ok(!small.ok && small.reason.includes("MIN_NOTIONAL"));
  // minQty alti: 0.0005 < 0.001
  const tiny = validateOrder({ qty: 0.0005, price: 100000, filters });
  assert.ok(!tiny.ok && tiny.reason.includes("minQty"));
});

// --- Durum dogrulamasi ---

test("validateState: gecerli durumu kabul, bozuk durumu reddeder", () => {
  const good = { quote: 1000, positions: { BTCTRY: { qty: 0.01, entryPrice: 100000 } }, risk: { equityPeak: 1000 } };
  assert.ok(validateState(good).ok);

  assert.ok(!validateState({ quote: NaN }).ok);
  assert.ok(!validateState({ quote: -5 }).ok);
  assert.ok(!validateState({ quote: undefined }).ok);
  assert.ok(!validateState({ quote: 1000, positions: { X: { qty: 0, entryPrice: 5 } } }).ok);
  assert.ok(!validateState({ quote: 1000, positions: { X: { qty: 1, entryPrice: NaN } } }).ok);
  assert.ok(!validateState({ quote: 1000, risk: { equityPeak: "bozuk" } }).ok);
});

// --- Anti-martingale dinamik risk ---

const rmCfg = {
  sizingMode: "percent", positionPct: 25, riskPerTradePct: 1, stopLossPct: 2,
  stopMode: "percent", atrStopMult: 2, atrTpMult: 3, feePct: 0.1, slippagePct: 0.05,
  dynamicRisk: true, dynamicRiskRefDd: 10, dynamicRiskFloor: 0.5,
};

test("riskMultiplier: zirvede 1, referans dususte tabana, arada lineer", () => {
  const rm = new RiskManager(rmCfg, () => 0);
  rm.equityPeak = 10000;
  assert.equal(rm.riskMultiplier(10000), 1);            // zirve
  assert.ok(Math.abs(rm.riskMultiplier(9500) - 0.75) < 1e-9); // %5 dusus -> 0.75
  assert.ok(Math.abs(rm.riskMultiplier(9000) - 0.5) < 1e-9);  // %10 dusus -> taban
  assert.equal(rm.riskMultiplier(8000), 0.5);           // referans otesi taban
});

test("riskMultiplier: kapaliyken her zaman 1", () => {
  const rm = new RiskManager({ ...rmCfg, dynamicRisk: false }, () => 0);
  rm.equityPeak = 10000;
  assert.equal(rm.riskMultiplier(5000), 1);
});

test("dinamik risk: dususte pozisyon boyutu kuculur", () => {
  const rm = new RiskManager(rmCfg, () => 0);
  rm.equityPeak = 10000;
  const full = rm.positionSize(10000, 10000, 100);   // zirve
  const reduced = rm.positionSize(9000, 9000, 100);  // %10 dusus
  // reduced ~ full * 0.5 * (9000/10000 butce farki degil - percent modda budget=quote*pct)
  // percent modda budget = quote*pct*multiplier; quote=9000 => 9000*0.25*0.5 vs 10000*0.25*1
  assert.ok(reduced < full);
});
