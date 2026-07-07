import { config, validateConfig } from "./config.js";
import { log } from "./logger.js";
import { fetchKlines } from "./exchange/binanceTr.js";
import { evaluate } from "./strategy.js";
import { Portfolio } from "./portfolio.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const errors = validateConfig();
  if (errors.length) {
    errors.forEach((e) => log.error(e));
    process.exit(1);
  }

  log.info("================= BINANCE TR COIN BOT =================");
  log.info(`Mod: ${config.tradeMode.toUpperCase()} | Parite: ${config.symbol} | Mum: ${config.interval}`);
  log.info(`Strateji: EMA${config.emaFast}/EMA${config.emaSlow} kesisimi + RSI${config.rsiPeriod} filtresi`);
  log.info(`Risk: pozisyon %${config.positionPct}, zarar durdur %${config.stopLossPct}, kar al %${config.takeProfitPct}`);
  if (config.tradeMode === "live") {
    log.warn("LIVE MOD AKTIF - GERCEK PARA ILE ISLEM YAPILACAK!");
    log.warn("Devam etmeden once 10 sn bekliyorum... Iptal icin Ctrl+C");
    await sleep(10_000);
  } else {
    log.info(`Paper mod: ${config.paperBalance} TRY sanal bakiye ile simulasyon.`);
  }

  const portfolio = new Portfolio();
  let lastCandleTime = 0;
  let running = true;
  process.on("SIGINT", () => {
    running = false;
    log.info("Kapatiliyor...");
  });

  while (running) {
    try {
      const klines = await fetchKlines(config.symbol, config.interval, 200);
      // Son mum henuz kapanmadigi icin sinyalleri kapanan mumlar uzerinden uret
      const closedCandles = klines.slice(0, -1);
      const closes = closedCandles.map((k) => k.close);
      const currentPrice = klines[klines.length - 1].close;
      const lastClosed = closedCandles[closedCandles.length - 1];

      // 1) Acik pozisyon icin zarar durdur / kar al kontrolu (her turda, anlik fiyatla)
      const exitReason = portfolio.checkExits(currentPrice);
      if (exitReason) {
        await portfolio.sell(currentPrice, exitReason);
      }

      // 2) Strateji sinyali - ayni kapanan mumu iki kez isleme
      if (lastClosed.closeTime !== lastCandleTime) {
        lastCandleTime = lastClosed.closeTime;
        const { signal, reason, snapshot } = evaluate(closes);
        log.info(
          `Fiyat: ${currentPrice} | EMA${config.emaFast}: ${snapshot.emaFast ?? "-"} | ` +
          `EMA${config.emaSlow}: ${snapshot.emaSlow ?? "-"} | RSI: ${snapshot.rsi ?? "-"} | Sinyal: ${signal}`
        );
        if (signal === "BUY" && !portfolio.inPosition) {
          await portfolio.buy(currentPrice, reason);
        } else if (signal === "SELL" && portfolio.inPosition) {
          await portfolio.sell(currentPrice, reason);
        }
        log.info(portfolio.summary(currentPrice));
      }
    } catch (err) {
      log.error(err.message);
    }
    await sleep(config.pollSeconds * 1000);
  }
}

main().catch((err) => {
  log.error(`Beklenmeyen hata: ${err.stack || err.message}`);
  process.exit(1);
});
