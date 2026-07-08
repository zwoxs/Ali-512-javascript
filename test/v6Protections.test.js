import { test } from "node:test";
import assert from "node:assert/strict";
import { RiskManager } from "../src/core/riskManager.js";
import { Portfolio } from "../src/core/portfolio.js";
import { Engine } from "../src/core/engine.js";
import { PaperBroker } from "../src/exchange/brokers.js";
import { validateConfig } from "../src/config.js";

const mkCandles = (prices, spreadPct = 0.2) =>
  prices.map((p, i) => ({
    openTime: i * 60000,
    open: p, high: p * (1 + spreadPct / 100), low: p * (1 - spreadPct / 100), close: p,
    volume: 1, closeTime: (i + 1) * 60000 - 1,
  }));

const baseCfg = {
  tradeMode: "paper", symbols: ["T"], interval: "1h",
  sizingMode: "percent", positionPct: 25, riskPerTradePct: 1,
  stopMode: "percent", stopLossPct: 10, takeProfitPct: 30,
  trailingStopPct: 0, trailingMode: "percent", chandelierMult: 3,
  breakevenTriggerPct: 0, maxHoldCandles: 0, minRr: 0,
  atrPeriod: 14, atrStopMult: 2, atrTpMult: 3, partialTpPct: 0, partialTpSize: 50,
  htfFilter: false, htfMultiple: 4, htfEmaPeriod: 20,
  adxFilter: false, adxPeriod: 14, adxMinimum: 20,
  pyramidMaxAddons: 0, pyramidTriggerPct: 2, pyramidSizeFactor: 0.5,
  maxOpenPositions: 0, maxExposurePct: 0, maxTotalDrawdownPct: 0,
  maxEntryAtrPct: 0, minOrderNotional: 0,
  maxDailyLossPct: 90, maxConsecutiveLosses: 99, cooldownMinutes: 1,
  feePct: 0, slippagePct: 0, paperBalance: 10000,
  emaFast: 9, emaSlow: 21, rsiPeriod: 14, rsiOverbought: 70, rsiOversold: 30,
  macdFast: 12, macdSlow: 26, macdSignal: 9, bbPeriod: 20, bbStdDev: 2,
  donchianEntry: 20, donchianExit: 10, supertrendPeriod: 10, supertrendMult: 3,
};

const holdStrategy = { name: "hold", warmup: () => 1, evaluate: () => ({ signal: "HOLD", reason: "-", snapshot: {} }) };
const buyStrategy = { name: "buy", warmup: () => 1, evaluate: () => ({ signal: "BUY", reason: "test", snapshot: {} }) };

// --- Chandelier stop ---

test("chandelier stop: zirveden N x ATR dususte kari kilitler", () => {
  const rm = new RiskManager({ ...baseCfg, trailingMode: "atr", chandelierMult: 2 });
  const pos = { entryPrice: 100, highWater: 120, entryAtr: 5 }; // stop = 120 - 10 = 110
  assert.ok(rm.checkExit(pos, 109.9)?.includes("Chandelier"));
  assert.equal(rm.checkExit(pos, 111), null);
});

// --- Erken basabas ---

test("erken basabas: kar esigi goruldukten sonra girise donus pozisyonu kapatir", () => {
  const rm = new RiskManager({ ...baseCfg, breakevenTriggerPct: 1.5 });
  const seen = { entryPrice: 100, highWater: 102, entryAtr: 0 };   // %2 gordu
  const unseen = { entryPrice: 100, highWater: 101, entryAtr: 0 }; // %1 gordu, esik %1.5
  assert.ok(rm.checkExit(seen, 100)?.includes("Basabas"));
  assert.equal(rm.checkExit(unseen, 100), null);
});

// --- Acil fren (kill switch) ---

test("acil fren: zirveden asiri dususte devreye girer ve kalicidir", () => {
  const rm = new RiskManager({ ...baseCfg, maxTotalDrawdownPct: 10 });
  rm.updateEquity(10000);
  assert.equal(rm.canOpen(), null);
  assert.equal(rm.updateEquity(9500), false);       // %5 dusus - sorun yok
  assert.equal(rm.updateEquity(8900), true);        // %11 dusus - fren!
  assert.ok(rm.canOpen()?.includes("ACIL FREN"));
  assert.equal(rm.updateEquity(9900), false);       // toparlasa bile fren kalici
  assert.ok(rm.canOpen()?.includes("ACIL FREN"));
});

// --- Zaman asimi cikisi ---

test("zaman asimi: karsiz bekleyen pozisyon kapanir, kardaki pozisyon kalir", async () => {
  const cfg = { ...baseCfg, maxHoldCandles: 3 };
  const portfolio = new Portfolio(10000);
  const risk = new RiskManager(cfg, () => 0);
  const broker = new PaperBroker(cfg);
  const engine = new Engine({ symbol: "T", strategy: holdStrategy, cfg, portfolio, risk, broker });

  const fill = await broker.buy("T", 10, 100); fill.ts = 0;
  portfolio.recordBuy("T", fill);

  // 3 yeni mum, fiyat girisin altinda -> zaman asimi
  for (let i = 1; i <= 3; i++) {
    await engine.step(mkCandles(Array(10 + i).fill(100)), 99.5, i);
  }
  assert.ok(!portfolio.inPosition("T"), "karsiz pozisyon zaman asimindan kapanmali");

  // Kardaki pozisyon zaman asimindan KAPANMAZ
  const fill2 = await broker.buy("T", 10, 100); fill2.ts = 10;
  portfolio.recordBuy("T", fill2);
  const engine2 = new Engine({ symbol: "T", strategy: holdStrategy, cfg, portfolio, risk, broker });
  for (let i = 1; i <= 5; i++) {
    await engine2.step(mkCandles(Array(10 + i).fill(100)), 105, 20 + i);
  }
  assert.ok(portfolio.inPosition("T"), "kardaki pozisyon zaman asimindan kapanmamali");
});

// --- Volatilite bekcisi ---

test("volatilite bekcisi: asiri ATR'de giris engellenir", async () => {
  const cfg = { ...baseCfg, maxEntryAtrPct: 1 };
  const portfolio = new Portfolio(10000);
  const risk = new RiskManager(cfg, () => 0);
  const engine = new Engine({
    symbol: "T", strategy: buyStrategy, cfg, portfolio, risk,
    broker: new PaperBroker(cfg), silent: true,
  });
  // %5 spread'li mumlar: ATR/fiyat ~%10 > %1 limit
  const wild = mkCandles(Array(30).fill(100), 5);
  await engine.step(wild, 100, 1);
  assert.ok(!portfolio.inPosition("T"), "asiri volatilitede pozisyon acilmamali");

  // Sakin piyasada ayni sinyal gecer
  const cfg2 = { ...baseCfg, maxEntryAtrPct: 5 };
  const engine2 = new Engine({
    symbol: "T", strategy: buyStrategy, cfg: cfg2, portfolio, risk,
    broker: new PaperBroker(cfg2), silent: true,
  });
  await engine2.step(mkCandles(Array(30).fill(100), 0.2), 100, 2);
  assert.ok(portfolio.inPosition("T"), "sakin piyasada pozisyon acilmali");
});

// --- Minimum emir tutari ---

test("minimum emir tutari: kucuk emir atlanir", async () => {
  const cfg = { ...baseCfg, positionPct: 1, minOrderNotional: 500 }; // %1 x 10000 = 100 < 500
  const portfolio = new Portfolio(10000);
  const risk = new RiskManager(cfg, () => 0);
  const engine = new Engine({
    symbol: "T", strategy: buyStrategy, cfg, portfolio, risk,
    broker: new PaperBroker(cfg), silent: true,
  });
  await engine.step(mkCandles(Array(30).fill(100)), 100, 1);
  assert.ok(!portfolio.inPosition("T"), "minimum tutarin altindaki emir acilmamali");
});

// --- MIN_RR dogrulamasi ---

test("MIN_RR: dusuk odul/risk oraniyla bot baslamaz", () => {
  const bad = validateConfig({ ...baseCfg, minRr: 2, stopLossPct: 2, takeProfitPct: 3 }); // rr=1.5 < 2
  assert.ok(bad.some((e) => e.includes("MIN_RR")));
  const good = validateConfig({ ...baseCfg, minRr: 1.5, stopLossPct: 2, takeProfitPct: 4 }); // rr=2
  assert.ok(!good.some((e) => e.includes("MIN_RR")));
});
