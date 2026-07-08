import { test } from "node:test";
import assert from "node:assert/strict";
import { maxDrawdown, profitFactor, computeMetrics } from "../src/core/metrics.js";

test("maxDrawdown: 100->120->90 egrisinde %25", () => {
  assert.equal(maxDrawdown([100, 120, 90, 110]), 25);
});

test("maxDrawdown: surekli yukselen egride 0", () => {
  assert.equal(maxDrawdown([100, 110, 120, 130]), 0);
});

test("profitFactor: brut kar / brut zarar", () => {
  const trades = [{ pnl: 100 }, { pnl: 50 }, { pnl: -50 }];
  assert.equal(profitFactor(trades), 3);
  assert.equal(profitFactor([{ pnl: 10 }]), Infinity);
});

test("computeMetrics tutarli ozet uretir", () => {
  const m = computeMetrics({
    equityCurve: [1000, 1050, 1020, 1100],
    trades: [{ pnl: 50 }, { pnl: -30 }, { pnl: 80 }],
    initialBalance: 1000,
    barsPerYear: 8760,
  });
  assert.equal(m.tradeCount, 3);
  assert.equal(m.winCount, 2);
  assert.ok(Math.abs(m.totalReturnPct - 10) < 1e-9);
  assert.ok(Math.abs(m.winRatePct - 66.666) < 0.01);
  assert.ok(m.maxDrawdownPct > 0);
});
