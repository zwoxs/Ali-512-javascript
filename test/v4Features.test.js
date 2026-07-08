import { test } from "node:test";
import assert from "node:assert/strict";
import { donchian, supertrend } from "../src/indicators.js";
import { monteCarlo, makeLcg } from "../src/core/monteCarlo.js";
import { computeMetrics, sortinoRatio, longestLossStreak } from "../src/core/metrics.js";
import { parseSymbolEntries } from "../src/config.js";
import { RiskManager } from "../src/core/riskManager.js";
import { Portfolio } from "../src/core/portfolio.js";
import { Engine } from "../src/core/engine.js";
import { PaperBroker } from "../src/exchange/brokers.js";
import { getStrategy } from "../src/strategies/index.js";

const mkCandles = (prices) =>
  prices.map((p, i) => ({
    openTime: i * 60000,
    open: p, high: p * 1.002, low: p * 0.998, close: p,
    volume: 1, closeTime: (i + 1) * 60000 - 1,
  }));

// --- Gostergeler ---

test("donchian: onceki N mumun en yuksek/dusugu (mevcut mum haric)", () => {
  const candles = mkCandles([10, 20, 30, 40, 50]);
  const { upper, lower } = donchian(candles, 3);
  // i=3: mum 0-2 (high: 30*1.002), i=4: mum 1-3 (high: 40*1.002)
  assert.equal(upper.length, 2);
  assert.ok(Math.abs(upper[0] - 30 * 1.002) < 1e-9);
  assert.ok(Math.abs(lower[1] - 20 * 0.998) < 1e-9);
});

test("supertrend: guclu yukseliste trend 1, dususte -1", () => {
  const up = mkCandles(Array.from({ length: 60 }, (_, i) => 100 * 1.01 ** i));
  const down = mkCandles(Array.from({ length: 60 }, (_, i) => 300 * 0.99 ** i));
  const stUp = supertrend(up, 10, 3);
  const stDown = supertrend(down, 10, 3);
  assert.equal(stUp.trend[stUp.trend.length - 1], 1);
  assert.equal(stDown.trend[stDown.trend.length - 1], -1);
  // Cizgi her zaman trend yonunun dogru tarafinda
  const i = stUp.trend.length - 1;
  assert.ok(stUp.line[i] < up[up.length - 1].close);
});

// --- Kismi kar alma ---

const partialCfg = {
  tradeMode: "paper", sizingMode: "percent", positionPct: 50, riskPerTradePct: 1,
  stopMode: "percent", stopLossPct: 5, takeProfitPct: 20, trailingStopPct: 0,
  atrPeriod: 14, atrStopMult: 2, atrTpMult: 3,
  partialTpPct: 2, partialTpSize: 50,
  htfFilter: false, htfMultiple: 4, htfEmaPeriod: 20,
  maxDailyLossPct: 50, maxConsecutiveLosses: 99, cooldownMinutes: 1,
  feePct: 0, slippagePct: 0,
  emaFast: 9, emaSlow: 21, rsiPeriod: 14, rsiOverbought: 70, rsiOversold: 30,
};

test("kismi kar alma: %2 karda yarim pozisyon kapanir, basabas stop devreye girer", async () => {
  const portfolio = new Portfolio(10000);
  const risk = new RiskManager(partialCfg, () => 0);
  const broker = new PaperBroker(partialCfg);
  const engine = new Engine({
    symbol: "TESTTRY", strategy: getStrategy("ema_rsi"), cfg: partialCfg, portfolio, risk, broker,
  });

  const fill = await broker.buy("TESTTRY", 10, 100);
  fill.ts = 0;
  portfolio.recordBuy("TESTTRY", fill);
  const startQty = portfolio.getPosition("TESTTRY").qty;

  // %2.5 kar: kismi satis tetiklenmeli.
  // Sadece risk katmanini test ediyoruz: strateji degerlendirmesini atlamak icin
  // son mum "zaten islendi" olarak isaretlenir (duz seri RSI=100 -> SELL uretirdi).
  const candles = mkCandles(Array(30).fill(100));
  engine.lastCandleTime = candles[candles.length - 1].closeTime;
  await engine.step(candles, 102.5, 1);
  const pos = portfolio.getPosition("TESTTRY");
  assert.ok(pos, "pozisyon tamamen kapanmamali");
  assert.ok(pos.partialDone, "partialDone isaretlenmeli");
  assert.ok(Math.abs(pos.qty - startQty / 2) < 1e-6, "pozisyonun yarisi kalmali");
  assert.ok(portfolio.realizedPnl > 0, "kismi kar gerceklesmis olmali");

  // Fiyat girise donerse basabas stop kalan pozisyonu kapatmali
  await engine.step(candles, 99.9, 2);
  assert.ok(!portfolio.inPosition("TESTTRY"), "basabas stop kalani kapatmali");
});

test("checkPartial: partialDone sonrasi tekrar tetiklenmez", () => {
  const rm = new RiskManager(partialCfg);
  assert.ok(rm.checkPartial({ entryPrice: 100, partialDone: false }, 103));
  assert.equal(rm.checkPartial({ entryPrice: 100, partialDone: true }, 110), null);
  assert.equal(rm.checkPartial({ entryPrice: 100, partialDone: false }, 101), null);
});

// --- Monte Carlo ---

test("monteCarlo: deterministik rng ile tutarli dagilim, p5 <= p50 <= p95", () => {
  const trades = [50, -30, 80, -20, 60, -40, 90, 30, -10, 70].map((pnl) => ({ pnl }));
  const mc = monteCarlo({ trades, initialBalance: 1000, runs: 500, rng: makeLcg(7) });
  assert.ok(mc.p5ReturnPct <= mc.p50ReturnPct && mc.p50ReturnPct <= mc.p95ReturnPct);
  assert.ok(mc.p50DrawdownPct <= mc.p95DrawdownPct);
  // Toplam pnl siralamadan bagimsizdir: tum yollar ayni yerde biter
  const totalPnl = trades.reduce((a, t) => a + t.pnl, 0);
  assert.ok(Math.abs(mc.p50ReturnPct - (totalPnl / 1000) * 100) < 1e-9);
  // Ayni seed ayni sonucu vermeli (tekrarlanabilirlik)
  const mc2 = monteCarlo({ trades, initialBalance: 1000, runs: 500, rng: makeLcg(7) });
  assert.equal(mc.p95DrawdownPct, mc2.p95DrawdownPct);
});

test("monteCarlo: 5'ten az islemde null", () => {
  assert.equal(monteCarlo({ trades: [{ pnl: 1 }], initialBalance: 1000 }), null);
});

// --- Metrikler ---

test("sortino: sadece asagi oynakligi cezalandirir", () => {
  const steady = [100, 102, 104, 106, 108];       // hic dusus yok
  assert.equal(sortinoRatio(steady, 8760), Infinity);
  const volatile = [100, 90, 105, 85, 110];
  assert.ok(Number.isFinite(sortinoRatio(volatile, 8760)));
});

test("longestLossStreak: kismi satislar sayilmaz", () => {
  const trades = [
    { pnl: -1 }, { pnl: -1 }, { pnl: -5, partial: true }, { pnl: -1 }, { pnl: 10 }, { pnl: -1 },
  ];
  assert.equal(longestLossStreak(trades), 3);
});

test("computeMetrics: CAGR, Calmar ve piyasada kalma orani hesaplanir", () => {
  const m = computeMetrics({
    equityCurve: Array.from({ length: 8760 }, (_, i) => 1000 * (1 + (i / 8759) * 0.2)), // 1 yilda %20
    trades: [{ pnl: 200 }],
    initialBalance: 1000,
    barsPerYear: 8760,
    exposureBars: 4380,
  });
  assert.ok(Math.abs(m.cagrPct - 20) < 0.5);
  assert.ok(Math.abs(m.exposurePct - 50) < 0.1);
  assert.ok(m.calmar >= 0);
});

// --- Sembol ayristirma ---

test("parseSymbolEntries: sembol basina strateji atamasi", () => {
  const { symbols, symbolStrategies } = parseSymbolEntries("btctry:ema_rsi, ETHTRY:SuperTrend ,XRPTRY");
  assert.deepEqual(symbols, ["BTCTRY", "ETHTRY", "XRPTRY"]);
  assert.equal(symbolStrategies.BTCTRY, "ema_rsi");
  assert.equal(symbolStrategies.ETHTRY, "supertrend");
  assert.equal(symbolStrategies.XRPTRY, undefined);
});
