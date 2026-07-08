import { test } from "node:test";
import assert from "node:assert/strict";
import { runBacktest } from "../src/core/backtester.js";
import { expandGrid, optimize, score } from "../src/core/optimizer.js";
import { getStrategy } from "../src/strategies/index.js";

const cfg = {
  tradeMode: "paper",
  interval: "1h",
  sizingMode: "percent",
  positionPct: 25,
  riskPerTradePct: 1,
  stopMode: "percent",
  stopLossPct: 2,
  takeProfitPct: 4,
  trailingStopPct: 0,
  atrPeriod: 14,
  atrStopMult: 2,
  atrTpMult: 3,
  htfFilter: false,
  htfMultiple: 4,
  htfEmaPeriod: 20,
  maxDailyLossPct: 50,
  maxConsecutiveLosses: 99,
  cooldownMinutes: 1,
  feePct: 0.1,
  slippagePct: 0,
  paperBalance: 10000,
  emaFast: 9,
  emaSlow: 21,
  rsiPeriod: 14,
  rsiOverbought: 70,
  rsiOversold: 30,
  macdFast: 12,
  macdSlow: 26,
  macdSignal: 9,
  bbPeriod: 20,
  bbStdDev: 2,
};

function syntheticKlines(n = 600) {
  const klines = [];
  let p = 1000;
  for (let i = 0; i < n; i++) {
    // trend + dalga + gurultu: islem uretmeye yetecek kadar hareketli
    p *= 1 + Math.sin(i / 15) * 0.004 + (((i * 7919) % 13) - 6) * 0.0004;
    klines.push({
      openTime: i * 3_600_000,
      open: p, high: p * 1.004, low: p * 0.996, close: p,
      volume: 10,
      closeTime: (i + 1) * 3_600_000 - 1,
    });
  }
  return klines;
}

test("runBacktest: muhasebe tutarli, pozisyon acik kalmaz, egri dolu", async () => {
  const klines = syntheticKlines();
  const { metrics, tradeLog, equityCurve } = await runBacktest({
    klines, cfg, strategy: getStrategy("ema_rsi"), silent: true,
  });
  assert.ok(equityCurve.length > 0);
  assert.ok(metrics.tradeCount === tradeLog.length);
  // Bitis ozsermayesi = baslangic + islem K/Z'lari (acik pozisyon kalmadigina gore)
  const ledger = tradeLog.reduce((a, t) => a + t.pnl, 0);
  assert.ok(Math.abs(metrics.finalEquity - (cfg.paperBalance + ledger)) < 0.01);
});

test("expandGrid kartezyen carpimi dogru boyutta", () => {
  const combos = expandGrid({ a: [1, 2], b: [3, 4, 5] });
  assert.equal(combos.length, 6);
  assert.deepEqual(combos[0], { a: 1, b: 3 });
});

test("optimize: walk-forward egitim/test ayirir ve top adaylara test metrigi ekler", async () => {
  const klines = syntheticKlines(700);
  const { top, results, trainBars, testBars } = await optimize({
    klines,
    cfg,
    strategyName: "ema_rsi",
    grid: { emaFast: [5, 9], emaSlow: [21, 34] }, // kucuk izgara: hizli test
    topN: 2,
  });
  assert.equal(results.length, 4);
  assert.equal(top.length, 2);
  assert.ok(trainBars > testBars);
  for (const r of top) {
    assert.ok(r.train && r.test, "top adaylarin hem egitim hem test metrigi olmali");
  }
  // Siralama skora gore azalan olmali
  assert.ok(score(results[0].train) >= score(results[1].train));
});
