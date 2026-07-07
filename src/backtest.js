// Stratejiyi gecmis veriyle test eder: npm run backtest
// Kullanim: node src/backtest.js [SEMBOL] [ARALIK] [MUM_SAYISI]
// Ornek:    node src/backtest.js BTCTRY 1h 500

import { config } from "./config.js";
import { fetchKlines } from "./exchange/binanceTr.js";
import { evaluate } from "./strategy.js";
import { Portfolio } from "./portfolio.js";

const symbol = (process.argv[2] || config.symbol).toUpperCase();
const interval = process.argv[3] || config.interval;
const limit = Math.min(parseInt(process.argv[4] || "500", 10), 1000);

async function main() {
  console.log(`Backtest: ${symbol} ${interval}, ${limit} mum, ${config.paperBalance} TRY baslangic\n`);
  const klines = await fetchKlines(symbol, interval, limit);
  const closes = klines.map((k) => k.close);

  // Backtest her zaman paper mantigiyla calisir
  config.tradeMode = "paper";
  const portfolio = new Portfolio();
  const warmup = Math.max(config.emaSlow, config.rsiPeriod) + 2;

  for (let i = warmup; i < closes.length; i++) {
    const price = closes[i];

    const exitReason = portfolio.checkExits(price);
    if (exitReason) await portfolio.sell(price, exitReason);

    const { signal, reason } = evaluate(closes.slice(0, i + 1));
    if (signal === "BUY" && !portfolio.inPosition) await portfolio.buy(price, reason);
    else if (signal === "SELL" && portfolio.inPosition) await portfolio.sell(price, reason);
  }

  // Acik pozisyonu son fiyattan kapat
  const lastPrice = closes[closes.length - 1];
  if (portfolio.inPosition) await portfolio.sell(lastPrice, "Backtest sonu - pozisyon kapatildi");

  const finalEquity = portfolio.quote;
  const returnPct = ((finalEquity - config.paperBalance) / config.paperBalance) * 100;
  const start = new Date(klines[0].openTime).toISOString().slice(0, 16);
  const end = new Date(klines[klines.length - 1].closeTime).toISOString().slice(0, 16);

  console.log("\n===================== SONUC =====================");
  console.log(`Donem           : ${start} -> ${end}`);
  console.log(`Islem sayisi    : ${portfolio.trades} (kazanan: ${portfolio.wins})`);
  console.log(`Kazanma orani   : ${portfolio.trades ? ((portfolio.wins / portfolio.trades) * 100).toFixed(1) : 0}%`);
  console.log(`Baslangic       : ${config.paperBalance.toFixed(2)} TRY`);
  console.log(`Bitis           : ${finalEquity.toFixed(2)} TRY`);
  console.log(`Getiri          : %${returnPct.toFixed(2)}`);
  const buyHold = ((lastPrice - closes[warmup]) / closes[warmup]) * 100;
  console.log(`Al-ve-tut getiri: %${buyHold.toFixed(2)} (karsilastirma)`);
}

main().catch((err) => {
  console.error("Backtest hatasi:", err.message);
  process.exit(1);
});
