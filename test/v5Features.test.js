import { test } from "node:test";
import assert from "node:assert/strict";
import { adx } from "../src/indicators.js";
import { isTrendingMarket } from "../src/core/trendFilter.js";
import { RiskManager } from "../src/core/riskManager.js";
import { Portfolio } from "../src/core/portfolio.js";
import { Engine } from "../src/core/engine.js";
import { PaperBroker } from "../src/exchange/brokers.js";

const mkCandles = (prices, spreadPct = 0.2) =>
  prices.map((p, i) => ({
    openTime: i * 60000,
    open: p, high: p * (1 + spreadPct / 100), low: p * (1 - spreadPct / 100), close: p,
    volume: 1, closeTime: (i + 1) * 60000 - 1,
  }));

const baseCfg = {
  tradeMode: "paper", sizingMode: "percent", positionPct: 25, riskPerTradePct: 1,
  stopMode: "percent", stopLossPct: 50, takeProfitPct: 100, trailingStopPct: 0,
  atrPeriod: 14, atrStopMult: 2, atrTpMult: 3, partialTpPct: 0, partialTpSize: 50,
  htfFilter: false, htfMultiple: 4, htfEmaPeriod: 20,
  adxFilter: false, adxPeriod: 14, adxMinimum: 20,
  pyramidMaxAddons: 0, pyramidTriggerPct: 2, pyramidSizeFactor: 0.5,
  maxOpenPositions: 0, maxExposurePct: 0,
  maxDailyLossPct: 90, maxConsecutiveLosses: 99, cooldownMinutes: 1,
  feePct: 0, slippagePct: 0,
  emaFast: 9, emaSlow: 21, rsiPeriod: 14, rsiOverbought: 70, rsiOversold: 30,
};

// Strateji degerlendirmesini kontrol edebilmek icin sahte strateji
const holdStrategy = { name: "hold", warmup: () => 1, evaluate: () => ({ signal: "HOLD", reason: "-", snapshot: {} }) };
const buyStrategy = { name: "buy", warmup: () => 1, evaluate: () => ({ signal: "BUY", reason: "test", snapshot: {} }) };

// --- ADX ---

test("adx: guclu trendde yuksek, testere piyasada dusuk", () => {
  const trending = mkCandles(Array.from({ length: 80 }, (_, i) => 100 + i * 2));
  const choppy = mkCandles(Array.from({ length: 80 }, (_, i) => 100 + (i % 2 === 0 ? 1 : -1)));
  const adxTrend = adx(trending, 14).pop();
  const adxChop = adx(choppy, 14).pop();
  assert.ok(adxTrend > 40, `trend ADX yuksek olmali (${adxTrend})`);
  assert.ok(adxChop < 20, `testere ADX dusuk olmali (${adxChop})`);
});

test("isTrendingMarket: filtre dogru yonde calisir, yetersiz veride uygulanmaz", () => {
  const cfg = { adxPeriod: 14, adxMinimum: 20 };
  const trending = mkCandles(Array.from({ length: 80 }, (_, i) => 100 + i * 2));
  const choppy = mkCandles(Array.from({ length: 80 }, (_, i) => 100 + (i % 2 === 0 ? 1 : -1)));
  assert.equal(isTrendingMarket(trending, cfg), true);
  assert.equal(isTrendingMarket(choppy, cfg), false);
  assert.equal(isTrendingMarket(mkCandles([1, 2, 3]), cfg), true);
});

// --- Piramitleme ---

test("piramitleme: fiyat lehte gidince kademeli ekler, limiti asamaz", async () => {
  const cfg = { ...baseCfg, pyramidMaxAddons: 2, pyramidTriggerPct: 2, pyramidSizeFactor: 0.5 };
  const portfolio = new Portfolio(100000);
  const risk = new RiskManager(cfg, () => 0);
  const broker = new PaperBroker(cfg);
  const engine = new Engine({ symbol: "T", strategy: holdStrategy, cfg, portfolio, risk, broker });

  const fill = await broker.buy("T", 10, 100);
  fill.ts = 0;
  portfolio.recordBuy("T", fill);

  // +%2.5 -> 1. kademe (5 adet), yeni mumla
  await engine.step(mkCandles([100, 101, 102.5]), 102.5, 1);
  let pos = portfolio.getPosition("T");
  assert.equal(pos.addons, 1);
  assert.ok(Math.abs(pos.qty - 15) < 1e-6, `qty 15 olmali (${pos.qty})`);
  assert.ok(pos.entryPrice > 100 && pos.entryPrice < 102.5, "giris agirlikli ortalama olmali");

  // ayni mumda tekrar eklenmez; yeni mum + tekrar +%2 -> 2. kademe (2.5 adet)
  await engine.step(mkCandles([100, 101, 102.5, 105]), 105, 2);
  pos = portfolio.getPosition("T");
  assert.equal(pos.addons, 2);
  assert.ok(Math.abs(pos.qty - 17.5) < 1e-6);

  // limit doldu: bir daha eklemez
  await engine.step(mkCandles([100, 101, 102.5, 105, 110]), 110, 3);
  assert.equal(portfolio.getPosition("T").addons, 2);
});

test("recordAddOn: agirlikli ortalama giris dogru hesaplanir", async () => {
  const portfolio = new Portfolio(100000);
  const broker = new PaperBroker(baseCfg);
  const f1 = await broker.buy("T", 10, 100); f1.ts = 0;
  portfolio.recordBuy("T", f1);
  const f2 = await broker.buy("T", 10, 110); f2.ts = 1;
  portfolio.recordAddOn("T", f2);
  const pos = portfolio.getPosition("T");
  assert.ok(Math.abs(pos.entryPrice - 105) < 1e-9);
  assert.ok(Math.abs(pos.qty - 20) < 1e-9);
});

// --- Portfoy limitleri ---

test("checkPortfolioLimits: maks pozisyon ve maruziyet limitleri", () => {
  const rm = new RiskManager({ ...baseCfg, maxOpenPositions: 1, maxExposurePct: 50 });
  const portfolio = new Portfolio(10000);
  assert.equal(rm.checkPortfolioLimits(portfolio), null);

  portfolio.positions.set("BTCTRY", { qty: 1, entryPrice: 3000 });
  portfolio.quote = 7000;
  assert.ok(rm.checkPortfolioLimits(portfolio)?.includes("Maksimum acik pozisyon"));

  const rm2 = new RiskManager({ ...baseCfg, maxOpenPositions: 0, maxExposurePct: 25 });
  // maruziyet = 3000/10000 = %30 >= %25
  assert.ok(rm2.checkPortfolioLimits(portfolio, { BTCTRY: 3000 })?.includes("maruziyet"));
});

// --- Sinyal modu ---

test("sinyal modu: islem acilmaz, bildirim kaydi olusur", async () => {
  const cfg = { ...baseCfg, tradeMode: "signal" };
  const portfolio = new Portfolio(10000);
  const risk = new RiskManager(cfg, () => 0);
  const events = [];
  const engine = new Engine({
    symbol: "T", strategy: buyStrategy, cfg, portfolio, risk,
    broker: new PaperBroker(cfg), silent: true,
    onTrade: (r) => events.push(r),
  });
  await engine.step(mkCandles([100, 101, 102]), 102, 1);
  assert.ok(!portfolio.inPosition("T"), "sinyal modunda pozisyon acilmamali");
  assert.equal(events.length, 1);
  assert.equal(events[0].side, "SINYAL-AL");
});
