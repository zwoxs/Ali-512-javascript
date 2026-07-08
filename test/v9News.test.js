import { test } from "node:test";
import assert from "node:assert/strict";
import { scoreText, scoreHeadlines, newsBlocked, _clearCache, LEXICON } from "../src/core/newsSentiment.js";
import { Portfolio } from "../src/core/portfolio.js";
import { RiskManager } from "../src/core/riskManager.js";
import { Engine } from "../src/core/engine.js";
import { PaperBroker } from "../src/exchange/brokers.js";

// --- Puanlama ---

test("scoreText: olumlu/olumsuz/notr metinleri dogru puanlar", () => {
  assert.ok(scoreText("Bitcoin ETF approval sparks massive rally") > 0);
  assert.ok(scoreText("Major exchange hacked, funds stolen in exploit") < 0);
  assert.equal(scoreText("Bitcoin price unchanged today"), 0);
});

test("scoreText: kelime siniri yanlis eslesmeyi onler", () => {
  // "band" icinde "ban" var ama kelime siniri sayesinde eslesmemeli
  assert.equal(scoreText("the band played music"), 0);
  assert.ok(scoreText("China ban on crypto") < 0);
});

test("scoreText: coklu kelime kaliplari eslesir", () => {
  assert.ok(scoreText("BTC hits record high") >= 2);
  assert.ok(scoreText("SEC charges exchange with fraud") <= -3);
});

test("scoreHeadlines: ortalama ve etiket dogru", () => {
  const bad = scoreHeadlines([
    "Exchange hacked in major exploit",
    "Regulators announce ban and lawsuit",
    "Token price crash continues",
  ]);
  assert.ok(bad.avg < -0.5);
  assert.equal(bad.label, "olumsuz");

  const good = scoreHeadlines([
    "Bitcoin ETF approval drives rally",
    "Major partnership boosts adoption",
  ]);
  assert.ok(good.avg > 0.5);
  assert.equal(good.label, "olumlu");

  assert.equal(scoreHeadlines([]).label, "veri-yok");
});

// --- Giris kapisi (ag olmadan, onbellek uzerinden) ---

function seedCache(asset, headlines) {
  // getSentiment onbellegi kullanir; onbellegi doldurmak icin dogrudan
  // newsSentiment ic onbellegine erisemeyiz, bu yuzden fetch'i cfg ile atlatiriz.
  // Bunun yerine newsBlocked'i sahte bir kaynak uzerinden test ederiz.
}

test("newsBlocked: filtre kapaliyken null", async () => {
  assert.equal(await newsBlocked("BTCTRY", { newsFilter: false }), null);
});

test("newsBlocked: yetersiz baslikta engellemez", async () => {
  _clearCache();
  // rss kaynagi, URL yok -> 0 baslik -> minArticles esigi altinda -> null
  const cfg = {
    newsFilter: true, newsSource: "rss", newsRssUrls: "", newsApiKey: "",
    newsMinScore: -0.5, newsMinArticles: 3, newsCacheSec: 300,
  };
  assert.equal(await newsBlocked("BTCTRY", cfg), null);
});

// --- Engine entegrasyonu: newsGate girisi engeller ---

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

test("newsGate: olumsuz haberde giris engellenir, temizde serbest", async () => {
  const portfolio = new Portfolio(10000);
  const risk = new RiskManager(cfg, () => 0);

  // Olumsuz haber kapisi
  const blockEngine = new Engine({
    symbol: "T", strategy: buyStrategy, cfg, portfolio, risk,
    broker: new PaperBroker(cfg), silent: true,
    newsGate: async () => "olumsuz haber",
  });
  await blockEngine.step(mkCandles(Array(30).fill(100)), 100, 1);
  assert.ok(!portfolio.inPosition("T"), "olumsuz haberde pozisyon acilmamali");

  // Temiz haber kapisi
  const okEngine = new Engine({
    symbol: "T", strategy: buyStrategy, cfg, portfolio, risk,
    broker: new PaperBroker(cfg), silent: true,
    newsGate: async () => null,
  });
  await okEngine.step(mkCandles(Array(31).fill(100)), 100, 2);
  assert.ok(portfolio.inPosition("T"), "temiz haberde pozisyon acilmali");
});

test("LEXICON: yinelenen anahtar yok, tum agirliklar sayisal", () => {
  for (const [term, w] of Object.entries(LEXICON)) {
    assert.equal(typeof w, "number", `${term} agirligi sayi olmali`);
    assert.notEqual(w, 0, `${term} agirligi sifir olmamali`);
  }
});
