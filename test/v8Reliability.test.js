import { test } from "node:test";
import assert from "node:assert/strict";
import { inRange, parseRange, inSession } from "../src/core/sessionFilter.js";
import { hasSufficientVolume } from "../src/core/liquidity.js";
import { ApiHealth } from "../src/core/apiHealth.js";
import { parseBalances, splitSymbol, reconcile, formatDrift } from "../src/core/reconciler.js";
import { makeClientOrderId } from "../src/exchange/binanceTr.js";
import { Portfolio } from "../src/core/portfolio.js";
import { RiskManager } from "../src/core/riskManager.js";
import { Engine } from "../src/core/engine.js";
import { PaperBroker } from "../src/exchange/brokers.js";

// --- Seans filtresi ---

test("parseRange / inRange: normal ve gece devri araliklari", () => {
  assert.deepEqual(parseRange("6-22"), { start: 6, end: 22 });
  assert.ok(inRange(10, { start: 6, end: 22 }));
  assert.ok(!inRange(23, { start: 6, end: 22 }));
  // Gece devri: 22-04
  assert.ok(inRange(23, { start: 22, end: 4 }));
  assert.ok(inRange(2, { start: 22, end: 4 }));
  assert.ok(!inRange(12, { start: 22, end: 4 }));
});

test("inSession: filtre kapaliyken her zaman true, acikken saate uyar", () => {
  const off = { sessionFilter: false };
  assert.ok(inSession(Date.parse("2026-01-01T03:00:00Z"), off));

  const cfg = { sessionFilter: true, sessionHours: "6-22", sessionDays: "0-6" };
  assert.ok(inSession(Date.parse("2026-01-01T10:00:00Z"), cfg));
  assert.ok(!inSession(Date.parse("2026-01-01T03:00:00Z"), cfg));

  // Hafta ici filtresi: Pazar (0) haric
  const weekdays = { sessionFilter: true, sessionHours: "0-23", sessionDays: "1-5" };
  assert.ok(!inSession(Date.parse("2026-01-04T10:00:00Z"), weekdays)); // 2026-01-04 Pazar
  assert.ok(inSession(Date.parse("2026-01-05T10:00:00Z"), weekdays));  // Pazartesi
});

// --- Hacim filtresi ---

test("hasSufficientVolume: dusuk hacimde false, yeterli hacimde true", () => {
  const cfg = { volumeFilter: true, volumeMinRatio: 0.5, volumeAvgPeriod: 5 };
  const mk = (vols) => vols.map((v) => ({ volume: v }));
  // ortalama 100, son mum 30 -> 30 < 50 -> yetersiz
  assert.ok(!hasSufficientVolume(mk([100, 100, 100, 100, 100, 30]), cfg));
  // son mum 80 -> yeterli
  assert.ok(hasSufficientVolume(mk([100, 100, 100, 100, 100, 80]), cfg));
  // veri yetersiz -> filtre uygulanmaz
  assert.ok(hasSufficientVolume(mk([100, 100]), cfg));
  // kapali -> her zaman true
  assert.ok(hasSufficientVolume(mk([1, 1, 1, 1, 1, 0]), { volumeFilter: false }));
});

// --- API devre kesici ---

test("ApiHealth: art arda hatada acilir, basari sifirlar, sogurma biter", () => {
  let now = 0;
  const h = new ApiHealth({ apiMaxConsecutiveErrors: 3, apiCircuitCooldownMin: 5 }, () => now);
  assert.ok(!h.isOpen());
  assert.equal(h.recordError(), false);
  assert.equal(h.recordError(), false);
  assert.equal(h.recordError(), true); // 3. hata devreyi acar
  assert.ok(h.isOpen());
  assert.ok(h.remainingSec() > 0);

  now += 5 * 60_000 + 1; // sogurma bitti
  assert.ok(!h.isOpen());

  // Basarili istek sayaci sifirlar
  h.recordSuccess();
  assert.equal(h.recordError(), false);
});

// --- Idempotent emir kimligi ---

test("makeClientOrderId: 36 karakter siniri, benzersiz, side/sembol izli", () => {
  const id1 = makeClientOrderId("BTCTRY", "BUY");
  const id2 = makeClientOrderId("BTCTRY", "BUY");
  assert.ok(id1.length <= 36 && id1.length > 0);
  assert.notEqual(id1, id2); // rastgele bilesen benzersizlik saglar
  assert.ok(/^[A-Za-z0-9]+$/.test(id1)); // borsa uyumlu karakterler
});

// --- Mutabakat ---

test("parseBalances / splitSymbol: farkli sema alanlarina toleransli", () => {
  const acc = { data: { accountAssets: [
    { asset: "TRY", free: "1000", locked: "50" },
    { asset: "BTC", free: "0.01", freeze: "0" },
  ] } };
  const bal = parseBalances(acc);
  assert.equal(bal.TRY, 1050);
  assert.ok(Math.abs(bal.BTC - 0.01) < 1e-9);

  assert.deepEqual(splitSymbol("BTCTRY"), { base: "BTC", quote: "TRY" });
  assert.deepEqual(splitSymbol("ETHUSDT"), { base: "ETH", quote: "USDT" });
});

test("reconcile: uyumlu durumda temiz, sapmada tespit eder", () => {
  const portfolio = new Portfolio(1000);
  portfolio.quote = 1000;
  portfolio.positions.set("BTCTRY", { qty: 0.01, entryPrice: 100000 });

  // Borsa birebir uyumlu
  const clean = reconcile(portfolio, { TRY: 1000, BTC: 0.01 }, { tolerancePct: 2 });
  assert.ok(clean.ok);
  assert.equal(clean.drifts.length, 0);

  // Nakit %10 sapmis
  const drift = reconcile(portfolio, { TRY: 900, BTC: 0.01 }, { tolerancePct: 2 });
  assert.ok(!drift.ok);
  assert.equal(drift.drifts[0].asset, "TRY");
  assert.ok(drift.drifts[0].diffPct > 2);
  assert.ok(formatDrift(drift.drifts).includes("TRY"));
});

// --- Engine entegrasyonu: haltGate ve seans/hacim girisleri engeller ---

const cfg = {
  tradeMode: "paper", sizingMode: "percent", positionPct: 25, riskPerTradePct: 1,
  stopMode: "percent", stopLossPct: 2, takeProfitPct: 4, trailingStopPct: 0,
  trailingMode: "percent", chandelierMult: 3, breakevenTriggerPct: 0,
  maxHoldCandles: 0, minRr: 0, atrPeriod: 14, atrStopMult: 2, atrTpMult: 3,
  partialTpPct: 0, partialTpSize: 50, htfFilter: false, htfMultiple: 4, htfEmaPeriod: 20,
  adxFilter: false, adxPeriod: 14, adxMinimum: 20,
  sessionFilter: false, sessionHours: "0-23", sessionDays: "0-6",
  volumeFilter: false, volumeMinRatio: 0.5, volumeAvgPeriod: 20,
  pyramidMaxAddons: 0, pyramidTriggerPct: 2, pyramidSizeFactor: 0.5,
  maxOpenPositions: 0, maxExposurePct: 0, maxTotalDrawdownPct: 0,
  maxEntryAtrPct: 0, minOrderNotional: 0, correlationMax: 0, correlationWindow: 50,
  maxDailyLossPct: 90, maxConsecutiveLosses: 99, cooldownMinutes: 1,
  feePct: 0, slippagePct: 0, paperBalance: 10000,
  emaFast: 9, emaSlow: 21, rsiPeriod: 14, rsiOverbought: 70, rsiOversold: 30,
};
const buyStrategy = { name: "buy", warmup: () => 1, evaluate: () => ({ signal: "BUY", reason: "t", snapshot: {} }) };
const mkCandles = (prices) => prices.map((p, i) => ({
  openTime: i * 60000, open: p, high: p * 1.002, low: p * 0.998, close: p,
  volume: 100, closeTime: (i + 1) * 60000 - 1,
}));

test("haltGate: aktifken yeni giris engellenir", async () => {
  const portfolio = new Portfolio(10000);
  const risk = new RiskManager(cfg, () => 0);
  const engine = new Engine({
    symbol: "T", strategy: buyStrategy, cfg, portfolio, risk,
    broker: new PaperBroker(cfg), silent: true,
    haltGate: () => "devre kesici acik",
  });
  await engine.step(mkCandles(Array(30).fill(100)), 100, 1);
  assert.ok(!portfolio.inPosition("T"), "haltGate aktifken pozisyon acilmamali");
});

test("seans filtresi: seans disinda giris engellenir", async () => {
  const sessionCfg = { ...cfg, sessionFilter: true, sessionHours: "6-22", sessionDays: "0-6" };
  const portfolio = new Portfolio(10000);
  const risk = new RiskManager(sessionCfg, () => 0);
  const engine = new Engine({
    symbol: "T", strategy: buyStrategy, cfg: sessionCfg, portfolio, risk,
    broker: new PaperBroker(sessionCfg), silent: true,
  });
  // 03:00 UTC - seans disi
  await engine.step(mkCandles(Array(30).fill(100)), 100, Date.parse("2026-01-01T03:00:00Z"));
  assert.ok(!portfolio.inPosition("T"), "seans disinda pozisyon acilmamali");
  // 10:00 UTC - seans ici
  await engine.step(mkCandles(Array(31).fill(100)), 100, Date.parse("2026-01-01T10:00:00Z"));
  assert.ok(portfolio.inPosition("T"), "seans icinde pozisyon acilmali");
});
