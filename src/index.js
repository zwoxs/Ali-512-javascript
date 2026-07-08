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
import { correlationBlocked } from "./core/correlation.js";
import { ApiHealth } from "./core/apiHealth.js";
import { reconcile, parseBalances, formatDrift } from "./core/reconciler.js";
import { newsBlocked } from "./core/newsSentiment.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const errors = validateConfig();
  if (errors.length) {
    errors.forEach((e) => log.error(e));
    process.exit(1);
  }

  // Sembol basina strateji: SYMBOLS=BTCTRY:ema_rsi,ETHTRY:supertrend
  const strategyBySymbol = Object.fromEntries(
    config.symbols.map((s) => [s, getStrategy(config.symbolStrategies[s] || config.strategy)])
  );
  const strategyDesc = config.symbols
    .map((s) => `${s}=${config.symbolStrategies[s] || config.strategy}`)
    .join(", ");

  log.info("==================== BINANCE TR COIN BOT ====================");
  log.info(`Mod: ${config.tradeMode.toUpperCase()} | Mum: ${config.interval}`);
  log.info(`Stratejiler: ${strategyDesc}${config.htfFilter ? ` + HTF(x${config.htfMultiple}) trend filtresi` : ""}`);
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
    // Baslangic dogrulamasi: API anahtarlari calisiyorsa hesap erisilebilir olmali
    try {
      const { getAccount } = await import("./exchange/binanceTr.js");
      await getAccount();
      log.info("Binance TR hesabi dogrulandi - API anahtarlari calisiyor.");
    } catch (err) {
      log.error(`Hesap dogrulanamadi: ${err.message}`);
      log.error("API anahtarlarinizi ve Binance TR API erisimini kontrol edin. Cikiliyor.");
      process.exit(1);
    }
  } else if (config.tradeMode === "signal") {
    log.info("Sinyal modu: islem ACILMAZ, sadece sinyal bildirimi gonderilir.");
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

  const feed = new MarketFeed(config.symbols, config.interval);
  await feed.init();

  // Korelasyon korumasi: acik pozisyonla asiri korele sembolde yeni giris engellenir
  const correlationGuard = (symbol) =>
    correlationBlocked({
      symbol,
      openSymbols: [...portfolio.positions.keys()],
      getCloses: (s) => feed.getCandles(s, config.correlationWindow + 1).map((c) => c.close),
      maxCorr: config.correlationMax,
      window: config.correlationWindow,
    });

  // API devre kesici: art arda API hatasinda yeni girisleri gecici durdurur
  const apiHealth = new ApiHealth(config);
  let reconcileHalt = false; // mutabakat sapmasi kalici durdurma isteniyorsa
  const haltGate = () => {
    if (apiHealth.isOpen()) return `API devre kesici acik (${apiHealth.remainingSec()}s kaldi) - yeni giris yok.`;
    if (reconcileHalt) return "Hesap mutabakati sapmasi nedeniyle yeni giris durduruldu - kontrol edin.";
    return null;
  };

  // Haber duyarlilik kapisi: coine girmeden guncel haberleri tarar (onbellekli)
  const newsGate = config.newsFilter ? (symbol) => newsBlocked(symbol, config) : null;

  const engines = config.symbols.map(
    (symbol) => new Engine({
      symbol, strategy: strategyBySymbol[symbol], cfg: config,
      portfolio, risk, broker, onTrade, correlationGuard, haltGate, newsGate,
    })
  );

  // --- Izleme paneli durumu ---
  const equityHistory = [];
  const latestPrices = {};
  const startedAt = Date.now();
  const getStatus = () => ({
    mode: config.tradeMode,
    symbols: config.symbols,
    interval: config.interval,
    strategy: strategyDesc,
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
      killSwitch: risk.killSwitch,
    },
    equityHistory,
    signals: Object.fromEntries(
      engines.filter((e) => e.lastSignal).map((e) => [e.symbol, e.lastSignal])
    ),
    charts: Object.fromEntries(
      config.symbols.map((s) => [
        s,
        feed.getCandles(s).map((c) => ({ t: c.openTime, o: c.open, h: c.high, l: c.low, c: c.close })),
      ])
    ),
    markers: portfolio.tradeLog.slice(-40),
  });
  const getHealth = () => ({
    status: apiHealth.isOpen() || reconcileHalt ? "degraded" : "ok",
    uptimeSec: Math.floor((Date.now() - startedAt) / 1000),
    memoryMb: +(process.memoryUsage().rss / 1048576).toFixed(1),
    feed: {
      websocket: feed.wsSupported,
      lastEventAgeSec: feed.lastEvent ? Math.floor((Date.now() - feed.lastEvent) / 1000) : null,
    },
    circuit: { open: apiHealth.isOpen(), remainingSec: apiHealth.remainingSec() },
    reconcileHalt,
    node: process.version,
  });
  const dashboard = startDashboard(config.dashboardPort, getStatus, getHealth);

  let running = true;
  const shutdown = () => {
    running = false;
    log.info("Kapatma sinyali alindi; durum kaydedilip cikilacak...");
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  await notify(`🤖 Bot basladi [${config.tradeMode}] ${config.interval} | ${strategyDesc}`);

  // Ardisik veri hatalarinda tek seferlik Telegram uyarisi (spam yok)
  const errorStreaks = new Map();
  let lastReportDay = new Date().toISOString().slice(0, 10);
  let lastReconcile = 0;

  // Live modda baslangicta hesap mutabakati (durum diskten yuklenmis olabilir)
  const runReconcile = async () => {
    if (config.tradeMode !== "live" || !config.reconcile) return;
    try {
      const { getAccount } = await import("./exchange/binanceTr.js");
      const balances = parseBalances(await getAccount());
      // Yanit ayristirilamadiysa (API semasi degismis olabilir) yanlis alarm/durdurma
      // yapma - bakiyeleri sifir sanip her sey sapma gorunur. Uyar ve gec.
      if (Object.keys(balances).length === 0) {
        lastReconcile = Date.now();
        log.warn("Hesap mutabakati: borsa bakiyeleri ayristirilamadi (API semasi degismis olabilir) - atlandi.");
        return;
      }
      const { ok, drifts } = reconcile(portfolio, balances, {
        tolerancePct: config.reconcileTolerancePct,
        quoteAsset: "TRY",
      });
      lastReconcile = Date.now();
      if (!ok) {
        const msg = formatDrift(drifts);
        log.warn(`Hesap mutabakati SAPMA: ${msg}`);
        await notify(`⚠️ Hesap mutabakati sapmasi:\n${msg}`);
        if (config.reconcileHaltOnDrift) {
          reconcileHalt = true;
          log.error("RECONCILE_HALT_ON_DRIFT aktif: yeni girisler durduruldu.");
        }
      } else {
        log.info("Hesap mutabakati temiz: ic durum borsa bakiyeleriyle uyumlu.");
      }
    } catch (err) {
      log.warn(`Hesap mutabakati yapilamadi: ${err.message}`);
    }
  };
  await runReconcile();

  let tick = 0;
  while (running) {
    for (const engine of engines) {
      try {
        const { closedCandles, currentPrice } = await feed.snapshot(engine.symbol);
        // Veri sagligi bekcisi: tek turda asiri fiyat sicramasi = muhtemel veri
        // aksakligi. O tur islenmez - bozuk fiyatla stop/alim tetiklenmez.
        const prevPrice = latestPrices[engine.symbol];
        if (
          config.sanityMaxJumpPct > 0 && prevPrice &&
          Math.abs((currentPrice - prevPrice) / prevPrice) * 100 > config.sanityMaxJumpPct
        ) {
          log.error(
            `${engine.symbol}: supheli fiyat sicramasi ${prevPrice} -> ${currentPrice} ` +
            `(>%${config.sanityMaxJumpPct}) - bu tur atlandi, veri dogrulanacak.`
          );
          continue;
        }
        latestPrices[engine.symbol] = currentPrice;
        await engine.step(closedCandles, currentPrice, Date.now());
        errorStreaks.set(engine.symbol, 0);
        apiHealth.recordSuccess();
      } catch (err) {
        log.error(`${engine.symbol}: ${err.message}`);
        const streak = (errorStreaks.get(engine.symbol) || 0) + 1;
        errorStreaks.set(engine.symbol, streak);
        if (streak === 5) {
          await notify(`🚨 ${engine.symbol}: 5 ardisik veri/islem hatasi - son hata: ${err.message}`);
        }
        // API devre kesici: art arda hatada yeni girisler gecici durur
        if (apiHealth.recordError()) {
          log.error(`API DEVRE KESICI ACILDI: ${config.apiCircuitCooldownMin} dk yeni giris yok.`);
          await notify(`🔌 API devre kesici acildi (art arda ${config.apiMaxConsecutiveErrors} hata). ${config.apiCircuitCooldownMin} dk yeni islem yok.`);
        }
      }
    }

    // Periyodik hesap mutabakati (live)
    if (
      config.tradeMode === "live" && config.reconcile &&
      Date.now() - lastReconcile > config.reconcileIntervalMin * 60_000
    ) {
      await runReconcile();
    }

    // Gunluk ozet raporu (Telegram)
    if (config.dailyReportHour >= 0) {
      const now = new Date();
      const today = now.toISOString().slice(0, 10);
      if (today !== lastReportDay && now.getHours() >= config.dailyReportHour) {
        lastReportDay = today;
        await notify(`📊 Gunluk ozet:\n${portfolio.summary(latestPrices)}`);
      }
    }
    if (Object.keys(latestPrices).length) {
      const equity = portfolio.equity(latestPrices);
      equityHistory.push({ t: Date.now(), equity });
      if (equityHistory.length > 1000) equityHistory.shift();
      // Acil fren kontrolu: zirveden asiri dususte tum yeni islemler durur
      if (risk.updateEquity(equity)) {
        saveState(portfolio, risk);
        log.error(`ACIL FREN DEVREDE: sermaye zirveden %${config.maxTotalDrawdownPct} dustu. Yeni islem acilmayacak.`);
        await notify(`🛑 ACIL FREN: toplam sermaye zirveden %${config.maxTotalDrawdownPct} dustu. Bot yeni islem ACMAYACAK - kontrol edin.`);
      }
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
