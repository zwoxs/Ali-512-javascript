import { config, validateConfig } from "./config.js";
import { log } from "./logger.js";
import { MarketFeed } from "./exchange/wsFeed.js";
import { createBroker } from "./exchange/brokers.js";
import { getStrategy } from "./strategies/index.js";
import { Portfolio } from "./core/portfolio.js";
import { RiskManager } from "./core/riskManager.js";
import { Engine } from "./core/engine.js";
import { saveState, loadState } from "./state.js";
import { notify, formatTradeMessage } from "./notifier.js";
import { startDashboard } from "./dashboard.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const errors = validateConfig();
  if (errors.length) {
    errors.forEach((e) => log.error(e));
    process.exit(1);
  }

  const strategy = getStrategy(config.strategy);

  log.info("==================== BINANCE TR COIN BOT ====================");
  log.info(`Mod: ${config.tradeMode.toUpperCase()} | Semboller: ${config.symbols.join(", ")} | Mum: ${config.interval}`);
  log.info(`Strateji: ${strategy.name}${config.htfFilter ? ` + HTF(x${config.htfMultiple}) trend filtresi` : ""}`);
  log.info(
    `Risk: boyutlama=${config.sizingMode}, stop=${config.stopMode}` +
    (config.stopMode === "atr"
      ? ` (${config.atrStopMult}xATR SL / ${config.atrTpMult}xATR TP)`
      : ` (SL %${config.stopLossPct} / TP %${config.takeProfitPct})`) +
    (config.trailingStopPct > 0 ? `, trailing %${config.trailingStopPct}` : "") +
    ` | Gunluk limit %${config.maxDailyLossPct}, ${config.maxConsecutiveLosses} zarar -> ${config.cooldownMinutes}dk sogurma`
  );

  if (config.tradeMode === "live") {
    log.warn("LIVE MOD AKTIF - GERCEK PARA ILE ISLEM YAPILACAK!");
    log.warn("Iptal icin Ctrl+C - 10 saniye bekleniyor...");
    await sleep(10_000);
  } else {
    log.info(`Paper mod: ${config.paperBalance} TRY sanal bakiye ile simulasyon.`);
  }

  const portfolio = new Portfolio(config.paperBalance);
  const risk = new RiskManager(config);
  loadState(portfolio, risk);

  const broker = createBroker(config);
  const onTrade = async (record) => {
    saveState(portfolio, risk);
    await notify(formatTradeMessage(record));
  };

  const engines = config.symbols.map(
    (symbol) => new Engine({ symbol, strategy, cfg: config, portfolio, risk, broker, onTrade })
  );

  const feed = new MarketFeed(config.symbols, config.interval);
  await feed.init();

  // --- Izleme paneli durumu ---
  const equityHistory = [];
  const latestPrices = {};
  const getStatus = () => ({
    mode: config.tradeMode,
    symbols: config.symbols,
    interval: config.interval,
    strategy: strategy.name,
    initialBalance: portfolio.initialQuote,
    equity: portfolio.equity(latestPrices),
    quote: portfolio.quote,
    trades: portfolio.trades,
    wins: portfolio.wins,
    realizedPnl: portfolio.realizedPnl,
    positions: [...portfolio.positions.entries()].map(([symbol, p]) => ({
      symbol,
      qty: p.qty,
      entryPrice: p.entryPrice,
      currentPrice: latestPrices[symbol] ?? p.entryPrice,
    })),
    recentTrades: portfolio.tradeLog.slice(-15).reverse(),
    risk: {
      dailyLimitHit: risk.dailyLimitHit,
      cooldownUntil: risk.cooldownUntil,
      consecutiveLosses: risk.consecutiveLosses,
      dailyPnl: risk.dailyPnl,
    },
    equityHistory,
  });
  const dashboard = startDashboard(config.dashboardPort, getStatus);

  let running = true;
  const shutdown = () => {
    running = false;
    log.info("Kapatma sinyali alindi; durum kaydedilip cikilacak...");
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  await notify(`🤖 Bot basladi [${config.tradeMode}] ${config.symbols.join(", ")} @ ${config.interval} (${strategy.name})`);

  let tick = 0;
  while (running) {
    for (const engine of engines) {
      try {
        const { closedCandles, currentPrice } = await feed.snapshot(engine.symbol);
        latestPrices[engine.symbol] = currentPrice;
        await engine.step(closedCandles, currentPrice, Date.now());
      } catch (err) {
        log.error(`${engine.symbol}: ${err.message}`);
      }
    }
    if (Object.keys(latestPrices).length) {
      equityHistory.push({ t: Date.now(), equity: portfolio.equity(latestPrices) });
      if (equityHistory.length > 1000) equityHistory.shift();
    }
    // Her 10 turda bir ozet yaz (log kirliligini onle)
    if (tick % 10 === 0 && Object.keys(latestPrices).length) {
      log.info(portfolio.summary(latestPrices));
    }
    tick++;
    await sleep(config.pollSeconds * 1000);
  }

  feed.stop();
  dashboard?.close();
  saveState(portfolio, risk);
  log.info("Durum kaydedildi. " + portfolio.summary(latestPrices));
  await notify("🛑 Bot durduruldu. " + portfolio.summary(latestPrices));
}

main().catch((err) => {
  log.error(`Beklenmeyen hata: ${err.stack || err.message}`);
  process.exit(1);
});
