import { Portfolio } from "./portfolio.js";
import { RiskManager } from "./riskManager.js";
import { Engine } from "./engine.js";
import { PaperBroker } from "../exchange/brokers.js";
import { computeMetrics } from "./metrics.js";
import { INTERVAL_MS } from "../config.js";

/**
 * Yeniden kullanilabilir backtest cekirdegi.
 * backtest.js (tekil kosum) ve optimizer (yuzlerce kosum) ayni fonksiyonu kullanir.
 * Canli motorla AYNI Engine/RiskManager/Portfolio kod yolundan gecer.
 *
 * @returns {Promise<{metrics: object, tradeLog: Array, equityCurve: number[]}>}
 */
export async function runBacktest({ klines, cfg, strategy, symbol = "BACKTEST", silent = true }) {
  const btCfg = { ...cfg, tradeMode: "paper" }; // backtest asla canli emir gondermez
  const portfolio = new Portfolio(btCfg.paperBalance);

  // Mum zamanini kullanan sanal saat - devre kesiciler tarihsel olarak dogru calisir
  let simTime = klines[0].closeTime;
  const risk = new RiskManager(btCfg, () => simTime);
  const broker = new PaperBroker(btCfg);
  const engine = new Engine({ symbol, strategy, cfg: btCfg, portfolio, risk, broker, silent });

  const warmupBars = strategy.warmup(btCfg);
  const equityCurve = [];
  let exposureBars = 0; // piyasada (pozisyonda) gecirilen bar sayisi

  for (let i = warmupBars; i < klines.length; i++) {
    const candle = klines[i];
    simTime = candle.closeTime;
    // Canli akisla ayni sozlesme: kapanmis mumlar + "anlik" fiyat (mumun kapanisi)
    await engine.step(klines.slice(0, i + 1), candle.close, simTime);
    equityCurve.push(portfolio.equity({ [symbol]: candle.close }));
    if (portfolio.inPosition(symbol)) exposureBars++;
  }

  // Acik pozisyonu son fiyattan kapat
  const lastCandle = klines[klines.length - 1];
  if (portfolio.inPosition(symbol)) {
    const fill = await broker.sell(symbol, portfolio.getPosition(symbol).qty, lastCandle.close);
    fill.ts = lastCandle.closeTime;
    portfolio.recordSell(symbol, fill);
    equityCurve.push(portfolio.quote);
  }

  const barsPerYear = (365 * 24 * 3600 * 1000) / INTERVAL_MS[cfg.interval];
  const metrics = computeMetrics({
    equityCurve,
    trades: portfolio.tradeLog,
    initialBalance: btCfg.paperBalance,
    barsPerYear,
    exposureBars,
  });

  return { metrics, tradeLog: portfolio.tradeLog, equityCurve };
}
