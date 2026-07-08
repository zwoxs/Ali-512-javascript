import { test } from "node:test";
import assert from "node:assert/strict";
import { getStrategy } from "../src/strategies/index.js";
import { toReturns, pearson, correlationBlocked } from "../src/core/correlation.js";
import { formatMetrics } from "../src/dashboard.js";
import { Portfolio } from "../src/core/portfolio.js";
import { RiskManager } from "../src/core/riskManager.js";
import { Engine } from "../src/core/engine.js";
import { PaperBroker } from "../src/exchange/brokers.js";

const mkCandles = (prices) =>
  prices.map((p, i) => ({
    openTime: i * 60000,
    open: p, high: p * 1.002, low: p * 0.998, close: p,
    volume: 1, closeTime: (i + 1) * 60000 - 1,
  }));

const cfg = {
  tradeMode: "paper", sizingMode: "percent", positionPct: 25, riskPerTradePct: 1,
  stopMode: "percent", stopLossPct: 2, takeProfitPct: 4, trailingStopPct: 0,
  trailingMode: "percent", chandelierMult: 3, breakevenTriggerPct: 0,
  maxHoldCandles: 0, minRr: 0, atrPeriod: 14, atrStopMult: 2, atrTpMult: 3,
  partialTpPct: 0, partialTpSize: 50, htfFilter: false, htfMultiple: 4, htfEmaPeriod: 20,
  adxFilter: false, adxPeriod: 14, adxMinimum: 20,
  pyramidMaxAddons: 0, pyramidTriggerPct: 2, pyramidSizeFactor: 0.5,
  maxOpenPositions: 0, maxExposurePct: 0, maxTotalDrawdownPct: 0,
  maxEntryAtrPct: 0, minOrderNotional: 0, correlationMax: 0, correlationWindow: 50,
  maxDailyLossPct: 90, maxConsecutiveLosses: 99, cooldownMinutes: 1,
  feePct: 0, slippagePct: 0, paperBalance: 10000,
  emaFast: 9, emaSlow: 21, rsiPeriod: 14, rsiOverbought: 70, rsiOversold: 30,
  macdFast: 12, macdSlow: 26, macdSignal: 9, bbPeriod: 20, bbStdDev: 2,
  donchianEntry: 20, donchianExit: 10, supertrendPeriod: 10, supertrendMult: 3,
  confluenceStrategies: ["ema_rsi", "macd", "supertrend"],
  confluenceMinVotes: 2,
};

// --- Konsensus stratejisi ---

test("confluence: sozlesmeye uyar ve oy sayilarini raporlar", () => {
  const s = getStrategy("confluence");
  assert.ok(s.warmup(cfg) > 0);
  const prices = [];
  let p = 1000;
  for (let i = 0; i < 60; i++) { p *= 0.997; prices.push(p); }
  for (let i = 0; i < 60; i++) { p *= 1.006; prices.push(p); }
  const out = s.evaluate(mkCandles(prices), cfg);
  assert.ok(["BUY", "SELL", "HOLD"].includes(out.signal));
  assert.ok(typeof out.snapshot.buyVotes === "number");
  assert.ok(typeof out.snapshot.sellVotes === "number");
});

test("confluence: imkansiz oy esiginde asla islem sinyali uretmez", () => {
  const s = getStrategy("confluence");
  const strict = { ...cfg, confluenceMinVotes: 99 };
  const prices = Array.from({ length: 120 }, (_, i) => 100 + Math.sin(i / 10) * 10);
  const out = s.evaluate(mkCandles(prices), strict);
  assert.equal(out.signal, "HOLD");
});

test("confluence: bilinmeyen uye strateji aninda hata verir", () => {
  const s = getStrategy("confluence");
  assert.throws(() => s.warmup({ ...cfg, confluenceStrategies: ["yok_boyle_strateji"] }));
});

// --- Korelasyon ---

test("pearson: birebir korele +1, ters korele -1", () => {
  const a = [1, 2, 3, 4, 5];
  assert.ok(Math.abs(pearson(a, [2, 4, 6, 8, 10]) - 1) < 1e-9);
  assert.ok(Math.abs(pearson(a, [5, 4, 3, 2, 1]) + 1) < 1e-9);
  assert.equal(pearson([1, 1, 1], [1, 2, 3]), 0); // sabit seri
});

test("correlationBlocked: korele acik pozisyon girisi engeller", () => {
  const btc = Array.from({ length: 60 }, (_, i) => 100 * 1.01 ** i * (1 + Math.sin(i) * 0.001));
  const eth = btc.map((v) => v * 0.1); // birebir korele
  const flat = Array.from({ length: 60 }, (_, i) => 50 + Math.cos(i * 7) * 3); // iliskisiz
  const closes = { BTCTRY: btc, ETHTRY: eth, XRPTRY: flat };
  const getCloses = (s) => closes[s];

  const blockedReason = correlationBlocked({
    symbol: "ETHTRY", openSymbols: ["BTCTRY"], getCloses, maxCorr: 0.85, window: 50,
  });
  assert.ok(blockedReason?.includes("Korelasyon"));

  const freeReason = correlationBlocked({
    symbol: "XRPTRY", openSymbols: ["BTCTRY"], getCloses, maxCorr: 0.85, window: 50,
  });
  assert.equal(freeReason, null);

  // Kapali ozellik hicbir seyi engellemez
  assert.equal(correlationBlocked({
    symbol: "ETHTRY", openSymbols: ["BTCTRY"], getCloses, maxCorr: 0, window: 50,
  }), null);
});

test("toReturns: getiri dizisi dogru", () => {
  const out = toReturns([100, 110, 99]);
  assert.equal(out.length, 2);
  assert.ok(Math.abs(out[0] - 0.1) < 1e-12);
  assert.ok(Math.abs(out[1] - -0.1) < 1e-12);
});

// --- Prometheus metrikleri ---

test("formatMetrics: gecerli Prometheus metin formati uretir", () => {
  const status = {
    equity: 10500, quote: 8000, realizedPnl: 500, trades: 7, wins: 4,
    positions: [{ symbol: "BTCTRY" }],
    risk: { dailyPnl: 50, consecutiveLosses: 1, killSwitch: false, dailyLimitHit: false },
  };
  const health = { uptimeSec: 3600, memoryMb: 55.2, feed: { lastEventAgeSec: 3 } };
  const out = formatMetrics(status, health);
  assert.ok(out.includes("bot_equity_try 10500"));
  assert.ok(out.includes("bot_trades_total 7"));
  assert.ok(out.includes("bot_kill_switch 0"));
  assert.ok(out.includes("# TYPE bot_equity_try gauge"));
  assert.ok(out.includes("bot_uptime_seconds 3600"));
});

// --- Strateji etiketi ---

test("islem kayitlari strateji adini tasir (rapor kirilimi icin)", async () => {
  const buyStrategy = { name: "test-strat", warmup: () => 1, evaluate: () => ({ signal: "BUY", reason: "t", snapshot: {} }) };
  const portfolio = new Portfolio(10000);
  const risk = new RiskManager(cfg, () => 0);
  const events = [];
  const engine = new Engine({
    symbol: "T", strategy: buyStrategy, cfg, portfolio, risk,
    broker: new PaperBroker(cfg), silent: true, onTrade: (r) => events.push(r),
  });
  await engine.step(mkCandles(Array(30).fill(100)), 100, 1);
  assert.equal(events.length, 1);
  assert.equal(events[0].strategy, "test-strat");
});
