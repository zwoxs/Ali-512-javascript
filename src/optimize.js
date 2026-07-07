// Walk-forward parametre optimizasyonu CLI.
// Kullanim: node src/optimize.js [SEMBOL] [ARALIK] [MUM_SAYISI] [STRATEJI]
// Ornek:    node src/optimize.js BTCTRY 1h 1000 ema_rsi
//
// Veri egitim/test olarak bolunur (70/30). Parametreler egitimde aranir,
// en iyi 5 aday hic gorulmemis test diliminde dogrulanir. Egitimde parlayip
// testte coken kombinasyon = asiri uyum; ona guvenmeyin.

import { config, validateConfig } from "./config.js";
import { fetchKlinesCached } from "./exchange/market.js";
import { optimize, score } from "./core/optimizer.js";

const symbol = (process.argv[2] || config.symbols[0]).toUpperCase();
const interval = process.argv[3] || config.interval;
const limit = Math.min(parseInt(process.argv[4] || "1000", 10), 1000);
const strategyName = (process.argv[5] || config.strategy).toLowerCase();

const fmtParams = (p) => Object.entries(p).map(([k, v]) => `${k}=${v}`).join(" ");
const fmtM = (m) =>
  `getiri %${m.totalReturnPct.toFixed(1).padStart(6)} | dusus %${m.maxDrawdownPct.toFixed(1).padStart(5)} | ` +
  `sharpe ${m.sharpe.toFixed(2).padStart(5)} | islem ${String(m.tradeCount).padStart(3)}`;

async function main() {
  config.tradeMode = "paper";
  config.interval = interval;
  const errors = validateConfig();
  if (errors.length) {
    errors.forEach((e) => console.error("HATA:", e));
    process.exit(1);
  }

  console.log(`\nWalk-forward optimizasyon: ${symbol} ${interval} x${limit} mum | Strateji: ${strategyName}\n`);
  const klines = await fetchKlinesCached(symbol, interval, limit);

  const { top, results, trainBars, testBars } = await optimize({
    klines,
    cfg: config,
    strategyName,
    onProgress: (done, total) => {
      if (done % 10 === 0 || done === total) {
        process.stdout.write(`\rEgitim kosulari: ${done}/${total}`);
      }
    },
  });
  console.log(`\n\nEgitim: ${trainBars} mum | Test: ${testBars} mum | Denenen kombinasyon: ${results.length}\n`);

  console.log("=================== EN IYI 5 (egitim -> test dogrulamasi) ===================");
  top.forEach((r, i) => {
    console.log(`\n#${i + 1} ${fmtParams(r.params)}`);
    console.log(`   Egitim: ${fmtM(r.train)}`);
    console.log(`   Test  : ${fmtM(r.test)}`);
    const overfit = score(r.train) > 0 && score(r.test) < 0;
    if (overfit) console.log("   ⚠️  ASIRI UYUM SUPHESI: egitimde iyi, testte zayif - bu parametrelere guvenmeyin.");
  });

  const best = top.find((r) => score(r.test) > 0);
  console.log("\n==============================================================================");
  if (best) {
    console.log("Test diliminde de karli en iyi aday (.env icin):\n");
    const ENV_KEYS = { bbStdDev: "BB_STDDEV" }; // camelCase -> ENV istisnalari
    for (const [k, v] of Object.entries(best.params)) {
      const envKey = ENV_KEYS[k] || k.replace(/([A-Z])/g, "_$1").toUpperCase();
      console.log(`  ${envKey}=${v}`);
    }
  } else {
    console.log("Hicbir kombinasyon test diliminde karli degil - bu strateji/donem uyumsuz olabilir.");
    console.log("Farkli strateji, sembol veya zaman araligi deneyin.");
  }
}

main().catch((err) => {
  console.error("Optimizasyon hatasi:", err.message);
  process.exit(1);
});
