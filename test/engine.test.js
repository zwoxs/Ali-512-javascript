// Uctan uca: sentetik veriyle Engine + Portfolio + RiskManager + PaperBroker
import { test } from "node:test";
import assert from "node:assert/strict";
import { Engine } from "../src/core/engine.js";
import { Portfolio } from "../src/core/portfolio.js";
import { RiskManager } from "../src/core/riskManager.js";
import { PaperBroker, roundToStep } from "../src/exchange/brokers.js";
import { getStrategy, strategyNames } from "../src/strategies/index.js";

const cfg = {
  tradeMode: "paper",
  sizingMode: "percent",
  positionPct: 25,
  riskPerTradePct: 1,
  stopLossPct: 2,
  takeProfitPct: 4,
  trailingStopPct: 0,
  maxDailyLossPct: 50,
  maxConsecutiveLosses: 10,
  cooldownMinutes: 1,
  feePct: 0.1,
  slippagePct: 0,
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
  donchianEntry: 20,
  donchianExit: 10,
  supertrendPeriod: 10,
  supertrendMult: 3,
};

function makeCandles(prices) {
  return prices.map((p, i) => ({
    openTime: i * 60000,
    open: p, high: p * 1.001, low: p * 0.999, close: p,
    volume: 1, closeTime: (i + 1) * 60000 - 1,
  }));
}

function wavePrices() {
  const prices = [];
  let p = 1000;
  for (let i = 0; i < 60; i++) { p *= 0.997; prices.push(p); }
  for (let i = 0; i < 60; i++) { p *= 1.006; prices.push(p); }
  for (let i = 0; i < 60; i++) { p *= 0.995; prices.push(p); }
  return prices;
}

test("roundToStep asagi yuvarlar ve artik birakmaz", () => {
  assert.equal(roundToStep(1.23456789, 0.001), 1.234);
  assert.equal(roundToStep(0.0009, 0.001), 0);
});

test("ema_rsi stratejisi dalgali veride islem uretir ve pozisyonu kapatir", async () => {
  const portfolio = new Portfolio(10000);
  let simTime = 0;
  const risk = new RiskManager(cfg, () => simTime);
  const engine = new Engine({
    symbol: "TESTTRY",
    strategy: getStrategy("ema_rsi"),
    cfg, portfolio, risk,
    broker: new PaperBroker(cfg),
  });

  const candles = makeCandles(wavePrices());
  for (let i = 30; i < candles.length; i++) {
    simTime = candles[i].closeTime;
    await engine.step(candles.slice(0, i + 1), candles[i].close, simTime);
  }
  assert.ok(portfolio.trades > 0, "en az bir islem tamamlanmali");
  // Muhasebe tutarliligi: bakiye + K/Z defteri celiskisiz
  const ledgerPnl = portfolio.tradeLog.reduce((a, t) => a + t.pnl, 0);
  assert.ok(Math.abs(ledgerPnl - portfolio.realizedPnl) < 1e-6);
});

test("stop-loss tetiklendiginde pozisyon kapanir", async () => {
  const portfolio = new Portfolio(10000);
  const risk = new RiskManager(cfg, () => 0);
  const broker = new PaperBroker(cfg);
  const engine = new Engine({
    symbol: "TESTTRY", strategy: getStrategy("ema_rsi"), cfg, portfolio, risk, broker,
  });

  // Manuel pozisyon ac, sonra fiyati stop seviyesinin altina dusur
  const fill = await broker.buy("TESTTRY", 1, 100);
  fill.ts = 0;
  portfolio.recordBuy("TESTTRY", fill);
  assert.ok(portfolio.inPosition("TESTTRY"));

  const candles = makeCandles(Array(30).fill(100));
  await engine.step(candles, 97, 1); // %3 dusus > %2 stop
  assert.ok(!portfolio.inPosition("TESTTRY"), "stop-loss pozisyonu kapatmali");
  assert.ok(portfolio.realizedPnl < 0);
});

test("tum stratejiler sozlesmeye uyar (HOLD yetersiz veride, gecerli sinyal tipleri)", () => {
  const candles = makeCandles(wavePrices());
  for (const name of strategyNames) {
    const s = getStrategy(name);
    assert.ok(s.warmup(cfg) > 0);
    const short = s.evaluate(candles.slice(0, 3), cfg);
    assert.equal(short.signal, "HOLD");
    const full = s.evaluate(candles, cfg);
    assert.ok(["BUY", "SELL", "HOLD"].includes(full.signal));
    assert.ok(typeof full.reason === "string");
  }
});
