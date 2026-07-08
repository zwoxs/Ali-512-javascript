import { test } from "node:test";
import assert from "node:assert/strict";
import { Portfolio } from "../src/core/portfolio.js";
import { RiskManager } from "../src/core/riskManager.js";
import { Engine } from "../src/core/engine.js";
import { PaperBroker } from "../src/exchange/brokers.js";

const mkCandles = (prices) => prices.map((p, i) => ({
  openTime: i * 60000, open: p, high: p * 1.002, low: p * 0.998, close: p,
  volume: 100, closeTime: (i + 1) * 60000 - 1,
}));

function baseCfg(overrides = {}) {
  return {
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
    feePct: 0.1, slippagePct: 0.5, paperBalance: 10000,
    emaFast: 9, emaSlow: 21, rsiPeriod: 14, rsiOverbought: 70, rsiOversold: 30,
    ...overrides,
  };
}
const buyStrategy = { name: "buy", warmup: () => 1, evaluate: () => ({ signal: "BUY", reason: "t", snapshot: {} }) };

// EN KRITIK INVARYANT: bakiye hicbir kosulda eksiye dusmez.
test("bakiye invaryanti: POSITION_PCT=100 + yuksek kayma ile bile eksiye dusmez", async () => {
  const cfg = baseCfg({ positionPct: 100, slippagePct: 1, feePct: 0.2 });
  const portfolio = new Portfolio(10000);
  const risk = new RiskManager(cfg, () => 0);
  const engine = new Engine({
    symbol: "T", strategy: buyStrategy, cfg, portfolio, risk,
    broker: new PaperBroker(cfg), silent: true,
  });
  await engine.step(mkCandles(Array(30).fill(100)), 100, 1);
  assert.ok(portfolio.inPosition("T"), "pozisyon acilmali");
  assert.ok(portfolio.quote >= -1e-9, `bakiye negatif olmamali: ${portfolio.quote}`);
});

test("bakiye invaryanti: risk modu + dar stop + yuksek riskle de eksiye dusmez", async () => {
  const cfg = baseCfg({ sizingMode: "risk", riskPerTradePct: 10, stopLossPct: 0.3, slippagePct: 1 });
  const portfolio = new Portfolio(5000);
  const risk = new RiskManager(cfg, () => 0);
  const engine = new Engine({
    symbol: "T", strategy: buyStrategy, cfg, portfolio, risk,
    broker: new PaperBroker(cfg), silent: true,
  });
  await engine.step(mkCandles(Array(30).fill(100)), 100, 1);
  assert.ok(portfolio.quote >= -1e-9, `bakiye negatif olmamali: ${portfolio.quote}`);
});

test("bakiye invaryanti: piramitleme kademelerinden sonra da eksiye dusmez", async () => {
  const cfg = baseCfg({ positionPct: 60, pyramidMaxAddons: 3, pyramidTriggerPct: 1, slippagePct: 1 });
  const portfolio = new Portfolio(10000);
  const risk = new RiskManager(cfg, () => 0);
  const engine = new Engine({
    symbol: "T", strategy: buyStrategy, cfg, portfolio, risk,
    broker: new PaperBroker(cfg), silent: true,
  });
  // Yukselen fiyat: her mumda kademe tetiklenebilir
  let price = 100;
  for (let i = 0; i < 10; i++) {
    price *= 1.02;
    await engine.step(mkCandles(Array(30 + i).fill(price)), price, i + 1);
    assert.ok(portfolio.quote >= -1e-9, `adim ${i}: bakiye negatif: ${portfolio.quote}`);
  }
});

test("muhasebe butunlugu: nakit + pozisyon degeri, komisyon+kayma kaybi kadar azalir", async () => {
  const cfg = baseCfg({ positionPct: 50, feePct: 0.1, slippagePct: 0.2 });
  const portfolio = new Portfolio(10000);
  const risk = new RiskManager(cfg, () => 0);
  const engine = new Engine({
    symbol: "T", strategy: buyStrategy, cfg, portfolio, risk,
    broker: new PaperBroker(cfg), silent: true,
  });
  await engine.step(mkCandles(Array(30).fill(100)), 100, 1);
  const pos = portfolio.getPosition("T");
  // Nakit + (pozisyon giris maliyeti) = baslangic - odenen komisyon
  // Pozisyon degeri giris fiyatindan: quote + qty*entryPrice <= 10000 (komisyon+kayma kaybi)
  const bookValue = portfolio.quote + pos.qty * pos.entryPrice;
  assert.ok(bookValue <= 10000 + 1e-6, "kitap degeri baslangici asmamali");
  assert.ok(bookValue > 9900, "makul kayip araligi (komisyon+kayma)");
});

test("worst-case ile PaperBroker gercek maliyeti tutarli (carpimsal tampon)", () => {
  const cfg = baseCfg({ positionPct: 100, feePct: 0.15, slippagePct: 0.6 });
  const risk = new RiskManager(cfg, () => 0);
  const quote = 10000, price = 100;
  const qty = risk.positionSize(quote, quote, price);
  // PaperBroker gercek dolum maliyeti
  const fillPrice = price * (1 + cfg.slippagePct / 100);
  const fee = qty * fillPrice * (cfg.feePct / 100);
  const realCost = qty * fillPrice + fee;
  assert.ok(realCost <= quote + 1e-9, `gercek maliyet ${realCost} <= ${quote}`);
});
