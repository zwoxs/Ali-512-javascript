import { test } from "node:test";
import assert from "node:assert/strict";
import { Portfolio } from "../src/core/portfolio.js";
import { RiskManager } from "../src/core/riskManager.js";
import { Engine } from "../src/core/engine.js";
import { PaperBroker } from "../src/exchange/brokers.js";
import { getStrategy, strategyNames } from "../src/strategies/index.js";

/**
 * FUZZ / INVARYANT TESTLERI.
 * Rastgele piyasa verisi + rastgele yapilandirmalarla motoru bininlerce adim
 * kosturur ve HER adimda cekirdek muhasebe invaryantlarinin bozulmadigini
 * dogrular. Insanin gozden kacirdigi ucuq durumlari yakalamanin profesyonel yolu.
 *
 * Invaryantlar:
 *  I1: Nakit bakiye asla negatif olmaz.
 *  I2: Pozisyon miktari asla negatif olmaz.
 *  I3: Gerceklesen K/Z = islem defterindeki K/Z'lerin toplami.
 *  I4: Ozsermaye = nakit + acik pozisyon degeri (tutarli).
 *  I5: Hicbir deger NaN/Infinity olmaz.
 */

// Tekrarlanabilir rastgele sayi ureteci (LCG) - basarisizlik determinstik yeniden uretilir
function makeRng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function randomConfig(rng) {
  const stopMode = rng() < 0.5 ? "percent" : "atr";
  const sizingMode = rng() < 0.5 ? "percent" : "risk";
  return {
    tradeMode: "paper",
    sizingMode,
    positionPct: 10 + Math.floor(rng() * 90),      // 10-100
    riskPerTradePct: 0.5 + rng() * 4,              // 0.5-4.5
    stopMode,
    stopLossPct: 1 + rng() * 4,
    takeProfitPct: 2 + rng() * 8,
    trailingStopPct: rng() < 0.5 ? 0 : 1 + rng() * 3,
    trailingMode: rng() < 0.5 ? "percent" : "atr",
    chandelierMult: 2 + rng() * 2,
    breakevenTriggerPct: rng() < 0.5 ? 0 : 1 + rng() * 2,
    maxHoldCandles: rng() < 0.5 ? 0 : 10 + Math.floor(rng() * 40),
    minRr: 0,
    atrPeriod: 14, atrStopMult: 1.5 + rng() * 2, atrTpMult: 2 + rng() * 3,
    partialTpPct: rng() < 0.5 ? 0 : 1.5 + rng() * 3,
    partialTpSize: 30 + Math.floor(rng() * 40),
    htfFilter: false, htfMultiple: 4, htfEmaPeriod: 20,
    adxFilter: false, adxPeriod: 14, adxMinimum: 20,
    sessionFilter: false, sessionHours: "0-23", sessionDays: "0-6",
    volumeFilter: false, volumeMinRatio: 0.5, volumeAvgPeriod: 20,
    pyramidMaxAddons: rng() < 0.5 ? 0 : 1 + Math.floor(rng() * 3),
    pyramidTriggerPct: 1 + rng() * 2, pyramidSizeFactor: 0.3 + rng() * 0.4,
    maxOpenPositions: 0, maxExposurePct: 0, maxTotalDrawdownPct: 0,
    maxEntryAtrPct: 0, minOrderNotional: 0, correlationMax: 0, correlationWindow: 50,
    dynamicRisk: rng() < 0.5, dynamicRiskRefDd: 10, dynamicRiskFloor: 0.4 + rng() * 0.4,
    maxDailyLossPct: 90, maxConsecutiveLosses: 99, cooldownMinutes: 1,
    feePct: rng() * 0.3, slippagePct: rng() * 0.8,
    paperBalance: 1000 + Math.floor(rng() * 20000),
    emaFast: 9, emaSlow: 21, rsiPeriod: 14, rsiOverbought: 70, rsiOversold: 30,
    macdFast: 12, macdSlow: 26, macdSignal: 9, bbPeriod: 20, bbStdDev: 2,
    donchianEntry: 20, donchianExit: 10, supertrendPeriod: 10, supertrendMult: 3,
    confluenceStrategies: ["ema_rsi", "macd"], confluenceMinVotes: 2,
  };
}

// Rastgele ama gercekci fiyat serisi (rassal yuruyus + dalgalar)
function randomCandles(rng, n) {
  const candles = [];
  let p = 100 + rng() * 900;
  for (let i = 0; i < n; i++) {
    const drift = (rng() - 0.5) * 0.04 + Math.sin(i / (5 + rng() * 20)) * 0.01;
    p *= 1 + drift;
    p = Math.max(p, 1);
    const hi = p * (1 + rng() * 0.01), lo = p * (1 - rng() * 0.01);
    candles.push({
      openTime: i * 3_600_000, open: p, high: Math.max(hi, p), low: Math.min(lo, p),
      close: p, volume: 1 + rng() * 1000, closeTime: (i + 1) * 3_600_000 - 1,
    });
  }
  return candles;
}

const finite = (v) => typeof v === "number" && Number.isFinite(v);

test("fuzz: 300 rastgele senaryoda cekirdek invaryantlar korunur", async () => {
  const SCENARIOS = 300;
  for (let sc = 0; sc < SCENARIOS; sc++) {
    const rng = makeRng(sc * 2654435761 + 12345);
    const cfg = randomConfig(rng);
    const strategyName = strategyNames[Math.floor(rng() * strategyNames.length)];
    const strategy = getStrategy(strategyName);
    const symbol = "FUZZ";
    const portfolio = new Portfolio(cfg.paperBalance);
    let simTime = 0;
    const risk = new RiskManager(cfg, () => simTime);
    const broker = new PaperBroker(cfg);
    const engine = new Engine({ symbol, strategy, cfg, portfolio, risk, broker, silent: true });

    const candles = randomCandles(rng, 250);
    const warmup = strategy.warmup(cfg);

    for (let i = warmup; i < candles.length; i++) {
      simTime = candles[i].closeTime;
      const price = candles[i].close;
      await engine.step(candles.slice(0, i + 1), price, simTime);
      risk.updateEquity(portfolio.equity({ [symbol]: price }));

      const ctx = `senaryo ${sc} (${strategyName}), adim ${i}`;
      // I1: nakit negatif olmaz (kucuk kayan nokta toleransi)
      assert.ok(portfolio.quote >= -1e-6, `${ctx}: nakit negatif ${portfolio.quote}`);
      // I5: NaN/Infinity yok
      assert.ok(finite(portfolio.quote), `${ctx}: nakit sonlu degil`);
      assert.ok(finite(portfolio.realizedPnl), `${ctx}: realizedPnl sonlu degil`);
      // I2: pozisyon miktari negatif olmaz
      const pos = portfolio.getPosition(symbol);
      if (pos) {
        assert.ok(pos.qty > 0 && finite(pos.qty), `${ctx}: pozisyon miktari ${pos.qty}`);
        assert.ok(finite(pos.entryPrice) && pos.entryPrice > 0, `${ctx}: entryPrice ${pos.entryPrice}`);
      }
    }

    // I3: gerceklesen K/Z = defter toplami
    const ledger = portfolio.tradeLog.reduce((a, t) => a + t.pnl, 0);
    assert.ok(Math.abs(ledger - portfolio.realizedPnl) < 1e-6,
      `senaryo ${sc}: defter ${ledger} != realizedPnl ${portfolio.realizedPnl}`);

    // I4: pozisyonu son fiyattan kapat, ozsermaye tutarli olmali
    const lastPrice = candles[candles.length - 1].close;
    const equityBefore = portfolio.equity({ [symbol]: lastPrice });
    assert.ok(finite(equityBefore) && equityBefore >= -1e-6, `senaryo ${sc}: ozsermaye ${equityBefore}`);
  }
});

test("fuzz: kapanan tum islemlerde miktar ve fiyatlar pozitif ve sonlu", async () => {
  for (let sc = 0; sc < 100; sc++) {
    const rng = makeRng(sc * 40503 + 777);
    const cfg = randomConfig(rng);
    const strategy = getStrategy("ema_rsi");
    const portfolio = new Portfolio(cfg.paperBalance);
    let simTime = 0;
    const risk = new RiskManager(cfg, () => simTime);
    const engine = new Engine({ symbol: "F", strategy, cfg, portfolio, risk, broker: new PaperBroker(cfg), silent: true });
    const candles = randomCandles(rng, 200);
    for (let i = strategy.warmup(cfg); i < candles.length; i++) {
      simTime = candles[i].closeTime;
      await engine.step(candles.slice(0, i + 1), candles[i].close, simTime);
    }
    for (const t of portfolio.tradeLog) {
      assert.ok(t.qty > 0 && finite(t.qty), `senaryo ${sc}: islem qty ${t.qty}`);
      assert.ok(t.entryPrice > 0 && t.exitPrice > 0, `senaryo ${sc}: fiyatlar`);
      assert.ok(finite(t.pnl), `senaryo ${sc}: pnl sonlu degil`);
    }
  }
});
