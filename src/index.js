import { config, validateConfig } from "./config.js";
import { log } from "./logger.js";
import { fetchKlines } from "./exchange/market.js";
import { createBroker } from "./exchange/brokers.js";
import { getStrategy } from "./strategies/index.js";
import { Portfolio } from "./core/portfolio.js";
import { RiskManager } from "./core/riskManager.js";
import { Engine } from "./core/engine.js";
import { saveState, loadState } from "./state.js";
import { notify, formatTradeMessage } from "./notifier.js";

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
  log.info(`Strateji: ${strategy.name}`);
  log.info(
    `Risk: boyutlama=${config.sizingMode}, SL %${config.stopLossPct}, TP %${config.takeProfitPct}` +
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
    const prices = {};
    for (const engine of engines) {
      try {
        const klines = await fetchKlines(engine.symbol, config.interval, 300);
        const closedCandles = klines.slice(0, -1); // son mum henuz kapanmadi
        const currentPrice = klines[klines.length - 1].close;
        prices[engine.symbol] = currentPrice;
        await engine.step(closedCandles, currentPrice, Date.now());
      } catch (err) {
        log.error(`${engine.symbol}: ${err.message}`);
      }
    }
    // Her 10 turda bir ozet yaz (log kirliligini onle)
    if (tick % 10 === 0 && Object.keys(prices).length) {
      log.info(portfolio.summary(prices));
    }
    tick++;
    await sleep(config.pollSeconds * 1000);
  }

  saveState(portfolio, risk);
  log.info("Durum kaydedildi. " + portfolio.summary());
  await notify("🛑 Bot durduruldu. " + portfolio.summary());
}

main().catch((err) => {
  log.error(`Beklenmeyen hata: ${err.stack || err.message}`);
  process.exit(1);
});
