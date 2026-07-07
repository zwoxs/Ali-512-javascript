// Backtest CLI - canli motorla AYNI kod yolunu kullanan backtester cekirdegini kosar.
// Kullanim: node src/backtest.js [SEMBOL] [ARALIK] [MUM_SAYISI] [STRATEJI]
// Ornek:    node src/backtest.js BTCTRY 1h 1000 macd

import { writeFileSync, mkdirSync, existsSync } from "node:fs";
import path from "node:path";
import { config, validateConfig } from "./config.js";
import { fetchKlinesCached } from "./exchange/market.js";
import { getStrategy, strategyNames } from "./strategies/index.js";
import { runBacktest } from "./core/backtester.js";
import { monteCarlo } from "./core/monteCarlo.js";

const symbol = (process.argv[2] || config.symbols[0]).toUpperCase();
const interval = process.argv[3] || config.interval;
const limit = Math.min(parseInt(process.argv[4] || "1000", 10), 1000);
const strategyName = (process.argv[5] || config.strategy).toLowerCase();

async function main() {
  config.tradeMode = "paper";
  config.interval = interval;
  const errors = validateConfig();
  if (errors.length) {
    errors.forEach((e) => console.error("HATA:", e));
    process.exit(1);
  }
  const strategy = getStrategy(strategyName);

  console.log(`\nBacktest: ${symbol} ${interval} x${limit} mum | Strateji: ${strategy.name}`);
  console.log(
    `Sermaye: ${config.paperBalance} TRY | stop=${config.stopMode} | Komisyon %${config.feePct} | Kayma %${config.slippagePct}` +
    (config.htfFilter ? ` | HTF filtresi x${config.htfMultiple}` : "") + "\n"
  );

  const klines = await fetchKlinesCached(symbol, interval, limit);
  const { metrics: m, tradeLog, equityCurve } = await runBacktest({
    klines, cfg: config, strategy, symbol, silent: true,
  });

  const warmupBars = strategy.warmup(config);
  const lastCandle = klines[klines.length - 1];
  const start = new Date(klines[0].openTime).toISOString().slice(0, 16);
  const end = new Date(lastCandle.closeTime).toISOString().slice(0, 16);
  const buyHold = ((lastCandle.close - klines[warmupBars].close) / klines[warmupBars].close) * 100;

  console.log("========================= SONUC =========================");
  console.log(`Donem              : ${start} -> ${end}`);
  console.log(`Islem sayisi       : ${m.tradeCount} (kazanan: ${m.winCount})`);
  console.log(`Kazanma orani      : %${m.winRatePct.toFixed(1)}`);
  console.log(`Ort. kazanc/kayip  : +${m.avgWin.toFixed(2)} / ${m.avgLoss.toFixed(2)} TRY`);
  console.log(`Kar faktoru        : ${m.profitFactor === Infinity ? "∞" : m.profitFactor.toFixed(2)}`);
  console.log(`En uzun zarar seri : ${m.longestLossStreak} islem`);
  console.log(`Piyasada kalma     : %${m.exposurePct?.toFixed(1) ?? "-"}`);
  console.log(`Maks. dusus        : %${m.maxDrawdownPct.toFixed(2)}`);
  console.log(`Sharpe / Sortino   : ${m.sharpe.toFixed(2)} / ${m.sortino === Infinity ? "∞" : m.sortino.toFixed(2)}`);
  console.log(`CAGR (yillik)      : %${m.cagrPct.toFixed(2)} | Calmar: ${m.calmar.toFixed(2)}`);
  console.log(`Baslangic -> Bitis : ${config.paperBalance.toFixed(2)} -> ${m.finalEquity.toFixed(2)} TRY`);
  console.log(`Strateji getirisi  : %${m.totalReturnPct.toFixed(2)}`);
  console.log(`Al-ve-tut getirisi : %${buyHold.toFixed(2)} (karsilastirma)`);

  // Monte Carlo saglamlik analizi: islem sirasi 1000 kez karistirilir
  const mc = monteCarlo({ trades: tradeLog, initialBalance: config.paperBalance });
  if (mc) {
    console.log("\n============== MONTE CARLO (1000 karistirma) ==============");
    console.log(`Getiri dagilimi    : p5 %${mc.p5ReturnPct.toFixed(1)} | medyan %${mc.p50ReturnPct.toFixed(1)} | p95 %${mc.p95ReturnPct.toFixed(1)}`);
    console.log(`Dusus dagilimi     : medyan %${mc.p50DrawdownPct.toFixed(1)} | p95 %${mc.p95DrawdownPct.toFixed(1)}`);
    console.log(`Iflas olasiligi    : %${mc.ruinProbabilityPct.toFixed(1)} (sermayenin %${mc.ruinThresholdPct}'ine dusme)`);
    if (mc.p5ReturnPct < 0 && m.totalReturnPct > 0) {
      console.log("⚠️  Karli gorunen backtest, kotu siralamada zarara donusebiliyor - temkinli olun.");
    }
  } else {
    console.log("\n(Monte Carlo icin en az 5 islem gerekir - atlandi.)");
  }

  // Ozsermaye egrisi ve islem listesi CSV olarak disari aktarilir (analiz icin)
  if (!existsSync(config.logDir)) mkdirSync(config.logDir, { recursive: true });
  const equityCsv = "bar,equity\n" + equityCurve.map((e, i) => `${i},${e.toFixed(2)}`).join("\n");
  const tradesCsv =
    "openedAt,closedAt,symbol,qty,entryPrice,exitPrice,pnl\n" +
    tradeLog.map((t) =>
      `${new Date(t.openedAt).toISOString()},${new Date(t.closedAt).toISOString()},${t.symbol},${t.qty},${t.entryPrice},${t.exitPrice},${t.pnl.toFixed(2)}`
    ).join("\n");
  const eqPath = path.join(config.logDir, `backtest-${symbol}-${interval}-equity.csv`);
  const trPath = path.join(config.logDir, `backtest-${symbol}-${interval}-trades.csv`);
  writeFileSync(eqPath, equityCsv);
  writeFileSync(trPath, tradesCsv);
  console.log(`\nCSV cikti: ${eqPath}`);
  console.log(`           ${trPath}`);
  console.log(`\nDiger stratejiler: node src/backtest.js ${symbol} ${interval} ${limit} [${strategyNames.join("|")}]`);
  console.log(`Optimizasyon     : node src/optimize.js ${symbol} ${interval} ${limit} ${strategyName}`);
}

main().catch((err) => {
  console.error("Backtest hatasi:", err.message);
  process.exit(1);
});
