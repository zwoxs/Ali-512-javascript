// Backtest - canli motorla AYNI Engine/RiskManager/Portfolio kod yolunu kullanir.
// Kullanim: node src/backtest.js [SEMBOL] [ARALIK] [MUM_SAYISI] [STRATEJI]
// Ornek:    node src/backtest.js BTCTRY 1h 1000 macd

import { config, validateConfig, INTERVAL_MS } from "./config.js";
import { fetchKlines } from "./exchange/market.js";
import { PaperBroker } from "./exchange/brokers.js";
import { getStrategy, strategyNames } from "./strategies/index.js";
import { Portfolio } from "./core/portfolio.js";
import { RiskManager } from "./core/riskManager.js";
import { Engine } from "./core/engine.js";
import { computeMetrics } from "./core/metrics.js";

const symbol = (process.argv[2] || config.symbols[0]).toUpperCase();
const interval = process.argv[3] || config.interval;
const limit = Math.min(parseInt(process.argv[4] || "1000", 10), 1000);
const strategyName = (process.argv[5] || config.strategy).toLowerCase();

async function main() {
  config.tradeMode = "paper"; // backtest asla canli emir gondermez
  config.interval = interval;
  const errors = validateConfig();
  if (errors.length) {
    errors.forEach((e) => console.error("HATA:", e));
    process.exit(1);
  }
  const strategy = getStrategy(strategyName);

  console.log(`\nBacktest: ${symbol} ${interval} x${limit} mum | Strateji: ${strategy.name}`);
  console.log(`Sermaye: ${config.paperBalance} TRY | SL %${config.stopLossPct} | TP %${config.takeProfitPct} | Komisyon %${config.feePct} | Kayma %${config.slippagePct}\n`);

  const klines = await fetchKlines(symbol, interval, limit);
  const portfolio = new Portfolio(config.paperBalance);

  // Backtest'te mum zamanini kullanan sanal saat - devre kesiciler dogru calisir
  let simTime = klines[0].closeTime;
  const risk = new RiskManager(config, () => simTime);
  const broker = new PaperBroker(config);
  const engine = new Engine({ symbol, strategy, cfg: config, portfolio, risk, broker });

  const warmupBars = strategy.warmup(config);
  const equityCurve = [];

  for (let i = warmupBars; i < klines.length; i++) {
    const candle = klines[i];
    simTime = candle.closeTime;
    // Canli akisla ayni sozlesme: kapanmis mumlar + "anlik" fiyat (mumun kapanisi)
    await engine.step(klines.slice(0, i + 1), candle.close, simTime);
    equityCurve.push(portfolio.equity({ [symbol]: candle.close }));
  }

  // Acik pozisyonu son fiyattan kapat
  const lastCandle = klines[klines.length - 1];
  if (portfolio.inPosition(symbol)) {
    const fill = await broker.sell(symbol, portfolio.getPosition(symbol).qty, lastCandle.close);
    fill.ts = lastCandle.closeTime;
    portfolio.recordSell(symbol, fill);
    equityCurve.push(portfolio.quote);
  }

  const barsPerYear = (365 * 24 * 3600 * 1000) / INTERVAL_MS[interval];
  const m = computeMetrics({
    equityCurve,
    trades: portfolio.tradeLog,
    initialBalance: config.paperBalance,
    barsPerYear,
  });

  const start = new Date(klines[0].openTime).toISOString().slice(0, 16);
  const end = new Date(lastCandle.closeTime).toISOString().slice(0, 16);
  const buyHold = ((lastCandle.close - klines[warmupBars].close) / klines[warmupBars].close) * 100;

  console.log("========================= SONUC =========================");
  console.log(`Donem              : ${start} -> ${end}`);
  console.log(`Islem sayisi       : ${m.tradeCount} (kazanan: ${m.winCount})`);
  console.log(`Kazanma orani      : %${m.winRatePct.toFixed(1)}`);
  console.log(`Ort. kazanc/kayip  : +${m.avgWin.toFixed(2)} / ${m.avgLoss.toFixed(2)} TRY`);
  console.log(`Kar faktoru        : ${m.profitFactor === Infinity ? "∞" : m.profitFactor.toFixed(2)}`);
  console.log(`Maks. dusus        : %${m.maxDrawdownPct.toFixed(2)}`);
  console.log(`Sharpe orani       : ${m.sharpe.toFixed(2)}`);
  console.log(`Baslangic -> Bitis : ${config.paperBalance.toFixed(2)} -> ${m.finalEquity.toFixed(2)} TRY`);
  console.log(`Strateji getirisi  : %${m.totalReturnPct.toFixed(2)}`);
  console.log(`Al-ve-tut getirisi : %${buyHold.toFixed(2)} (karsilastirma)`);
  console.log(`\nDiger stratejiler icin: node src/backtest.js ${symbol} ${interval} ${limit} [${strategyNames.join("|")}]`);
}

main().catch((err) => {
  console.error("Backtest hatasi:", err.message);
  process.exit(1);
});
