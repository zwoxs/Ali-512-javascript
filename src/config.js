import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// Basit .env yukleyici (harici bagimlilik gerektirmez)
function loadEnvFile() {
  const envPath = path.join(ROOT, ".env");
  if (!existsSync(envPath)) return;
  for (const line of readFileSync(envPath, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    const value = trimmed.slice(eq + 1).trim();
    if (!(key in process.env)) process.env[key] = value;
  }
}

loadEnvFile();

const num = (key, def) => {
  const v = parseFloat(process.env[key]);
  return Number.isFinite(v) ? v : def;
};
const str = (key, def) => (process.env[key] || def).trim();
const bool = (key, def) => /^(1|true|yes|on)$/i.test(process.env[key] ?? String(def));

export const INTERVAL_MS = {
  "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
  "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000,
  "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000, "1w": 604_800_000,
};

/**
 * SYMBOLS girdisini ayristirir. Sembol basina strateji atanabilir:
 * "BTCTRY:ema_rsi,ETHTRY:supertrend" veya duz "BTCTRY,ETHTRY".
 */
export function parseSymbolEntries(raw) {
  const symbols = [];
  const symbolStrategies = {};
  for (const entry of raw.split(",")) {
    const [sym, strat] = entry.split(":");
    const symbol = sym?.trim().toUpperCase();
    if (!symbol) continue;
    symbols.push(symbol);
    if (strat?.trim()) symbolStrategies[symbol] = strat.trim().toLowerCase();
  }
  return { symbols, symbolStrategies };
}

const { symbols: parsedSymbols, symbolStrategies: parsedSymbolStrategies } =
  parseSymbolEntries(str("SYMBOLS", str("SYMBOL", "BTCTRY")));

export const config = {
  root: ROOT,
  dataDir: path.join(ROOT, "data"),
  logDir: path.join(ROOT, "logs"),

  tradeMode: str("TRADE_MODE", "paper").toLowerCase(),
  symbols: parsedSymbols,
  symbolStrategies: parsedSymbolStrategies, // sembol -> strateji adi (bos: STRATEGY kullanilir)
  interval: str("INTERVAL", "15m"),
  pollSeconds: num("POLL_SECONDS", 30),
  logLevel: str("LOG_LEVEL", "info").toLowerCase(),
  logFormat: str("LOG_FORMAT", "text").toLowerCase(), // text | json (log toplayicilar icin)

  // Strateji
  strategy: str("STRATEGY", "ema_rsi").toLowerCase(),
  emaFast: num("EMA_FAST", 9),
  emaSlow: num("EMA_SLOW", 21),
  rsiPeriod: num("RSI_PERIOD", 14),
  rsiOverbought: num("RSI_OVERBOUGHT", 70),
  rsiOversold: num("RSI_OVERSOLD", 30),
  macdFast: num("MACD_FAST", 12),
  macdSlow: num("MACD_SLOW", 26),
  macdSignal: num("MACD_SIGNAL", 9),
  bbPeriod: num("BB_PERIOD", 20),
  bbStdDev: num("BB_STDDEV", 2),
  donchianEntry: num("DONCHIAN_ENTRY", 20),
  donchianExit: num("DONCHIAN_EXIT", 10),
  supertrendPeriod: num("SUPERTREND_PERIOD", 10),
  supertrendMult: num("SUPERTREND_MULT", 3),
  // Konsensus (ensemble) stratejisi: uye stratejiler ve gereken minimum oy
  confluenceStrategies: str("CONFLUENCE_STRATEGIES", "ema_rsi,macd,supertrend")
    .toLowerCase().split(",").map((s) => s.trim()).filter(Boolean),
  confluenceMinVotes: num("CONFLUENCE_MIN_VOTES", 2),

  // Sermaye ve boyutlama
  paperBalance: num("PAPER_BALANCE", 10000),
  sizingMode: str("SIZING_MODE", "percent").toLowerCase(), // percent | risk
  positionPct: num("POSITION_PCT", 25),        // percent modu: bakiyenin %'si
  riskPerTradePct: num("RISK_PER_TRADE_PCT", 1), // risk modu: islem basina riske edilen sermaye %'si

  // Cikis kurallari
  // percent = sabit yuzde | atr = volatiliteye uyumlu (ATR carpani) stop/hedef
  stopMode: str("STOP_MODE", "percent").toLowerCase(),
  stopLossPct: num("STOP_LOSS_PCT", 2),
  takeProfitPct: num("TAKE_PROFIT_PCT", 4),
  trailingStopPct: num("TRAILING_STOP_PCT", 0), // 0 = kapali
  // Iz suren stop modu: percent = sabit yuzde | atr = chandelier (zirve - N x ATR)
  trailingMode: str("TRAILING_MODE", "percent").toLowerCase(),
  chandelierMult: num("CHANDELIER_MULT", 3),
  // Erken basabas: kar bu yuzdeye ulasinca stop giris fiyatina cekilir (0 = kapali)
  breakevenTriggerPct: num("BREAKEVEN_TRIGGER_PCT", 0),
  // Zaman asimi cikisi: bu kadar mumdur KARSIZ bekleyen pozisyon kapatilir (0 = kapali)
  maxHoldCandles: num("MAX_HOLD_CANDLES", 0),
  // Odul/risk zorlamasi: TP mesafesi / SL mesafesi bu oranin altindaysa bot baslamaz (0 = kapali)
  minRr: num("MIN_RR", 0),
  atrPeriod: num("ATR_PERIOD", 14),
  atrStopMult: num("ATR_STOP_MULT", 2),
  atrTpMult: num("ATR_TP_MULT", 3),

  // Kismi kar alma (scale-out): kar bu yuzdeye ulasinca pozisyonun bir kismi
  // kapatilir ve stop basabas noktasina cekilir (0 = kapali)
  partialTpPct: num("PARTIAL_TP_PCT", 0),
  partialTpSize: num("PARTIAL_TP_SIZE", 50), // pozisyonun yuzde kaci kapatilsin

  // Ust zaman dilimi (HTF) trend filtresi: dusus trendinde AL sinyallerini engeller
  htfFilter: bool("HTF_FILTER", false),
  htfMultiple: num("HTF_MULTIPLE", 4),     // 1 HTF mumu = kac taban mum
  htfEmaPeriod: num("HTF_EMA_PERIOD", 20),

  // ADX rejim filtresi: piyasa trendsiz/testere iken (ADX dusuk) islem acilmaz
  adxFilter: bool("ADX_FILTER", false),
  adxPeriod: num("ADX_PERIOD", 14),
  adxMinimum: num("ADX_MINIMUM", 20),

  // Piramitleme: kazanan pozisyona kademeli ekleme (0 = kapali)
  pyramidMaxAddons: num("PYRAMID_MAX_ADDONS", 0),
  pyramidTriggerPct: num("PYRAMID_TRIGGER_PCT", 2), // son girisin bu kadar % ustunde ekle
  pyramidSizeFactor: num("PYRAMID_SIZE_FACTOR", 0.5), // her kademe = onceki boyut x faktor

  // Portfoy seviyesi limitler (0 = kapali)
  maxOpenPositions: num("MAX_OPEN_POSITIONS", 0),
  maxExposurePct: num("MAX_EXPOSURE_PCT", 0), // pozisyonlardaki sermaye / toplam deger

  // ACIL FREN: toplam sermaye zirvesinden bu kadar % dusulurse bot yeni islem ACMAZ
  // (0 = kapali). Devreye girerse manuel inceleme gerekir - en guclu zarar sinirlayici.
  maxTotalDrawdownPct: num("MAX_TOTAL_DRAWDOWN_PCT", 0),

  // Volatilite bekcisi: ATR/fiyat orani bu yuzdenin ustundeyse giris yapilmaz (0 = kapali)
  maxEntryAtrPct: num("MAX_ENTRY_ATR_PCT", 0),

  // Minimum emir tutari (TRY): komisyonun kari yedigi kucuk emirleri engeller (0 = kapali)
  minOrderNotional: num("MIN_ORDER_NOTIONAL", 0),

  // Korelasyon korumasi: acik pozisyonla getiri korelasyonu bu esigin ustundeki
  // sembolde yeni pozisyon acilmaz - ayni riske iki kez girilmez (0 = kapali, 0-1 arasi)
  correlationMax: num("CORRELATION_MAX", 0),
  correlationWindow: num("CORRELATION_WINDOW", 50),

  // Veri sagligi bekcisi: tek turda bu yuzdeden fazla fiyat sicramasi veri
  // aksakligi sayilir ve o tur islenmez (0 = kapali)
  sanityMaxJumpPct: num("SANITY_MAX_JUMP_PCT", 15),

  // Devre kesiciler
  maxDailyLossPct: num("MAX_DAILY_LOSS_PCT", 5),      // gunluk zarar limiti (baslangic sermayesine gore %)
  maxConsecutiveLosses: num("MAX_CONSECUTIVE_LOSSES", 3),
  cooldownMinutes: num("COOLDOWN_MINUTES", 60),

  // Islem maliyetleri
  feePct: num("FEE_PCT", 0.1),
  slippagePct: num("SLIPPAGE_PCT", 0.05), // paper/backtest gerceklik payi

  // Gercek zamanli veri ve izleme
  wsEnabled: bool("WS_ENABLED", true),
  wsBaseUrl: str("WS_BASE_URL", "wss://stream.binance.com:9443"),
  dashboardPort: num("DASHBOARD_PORT", 0), // 0 = kapali

  // API
  marketBaseUrl: str("MARKET_BASE_URL", "https://api.binance.com"),
  tradeBaseUrl: str("TRADE_BASE_URL", "https://api.trbinance.com"),
  apiKey: str("BINANCE_TR_API_KEY", ""),
  apiSecret: str("BINANCE_TR_API_SECRET", ""),

  // Bildirim
  telegramToken: str("TELEGRAM_BOT_TOKEN", ""),
  telegramChatId: str("TELEGRAM_CHAT_ID", ""),
  discordWebhookUrl: str("DISCORD_WEBHOOK_URL", ""),
  dailyReportHour: num("DAILY_REPORT_HOUR", 21), // gunluk ozet raporu saati (yerel, -1 = kapali)
};

export function validateConfig(cfg = config) {
  const errors = [];
  if (!["paper", "live", "signal"].includes(cfg.tradeMode))
    errors.push(`TRADE_MODE 'paper', 'live' veya 'signal' olmali (su an: ${cfg.tradeMode})`);
  if (cfg.tradeMode === "live" && (!cfg.apiKey || !cfg.apiSecret))
    errors.push("Live mod icin BINANCE_TR_API_KEY ve BINANCE_TR_API_SECRET zorunlu.");
  if (!INTERVAL_MS[cfg.interval])
    errors.push(`Gecersiz INTERVAL: ${cfg.interval}. Gecerli: ${Object.keys(INTERVAL_MS).join(", ")}`);
  if (cfg.symbols.length === 0) errors.push("En az bir SYMBOL tanimlanmali.");
  if (cfg.emaFast >= cfg.emaSlow) errors.push("EMA_FAST, EMA_SLOW'dan kucuk olmali.");
  if (cfg.macdFast >= cfg.macdSlow) errors.push("MACD_FAST, MACD_SLOW'dan kucuk olmali.");
  if (!["percent", "risk"].includes(cfg.sizingMode))
    errors.push("SIZING_MODE 'percent' veya 'risk' olmali.");
  if (cfg.positionPct <= 0 || cfg.positionPct > 100)
    errors.push("POSITION_PCT 0-100 arasinda olmali.");
  if (cfg.riskPerTradePct <= 0 || cfg.riskPerTradePct > 10)
    errors.push("RISK_PER_TRADE_PCT 0-10 arasinda olmali.");
  if (cfg.stopLossPct <= 0) errors.push("STOP_LOSS_PCT pozitif olmali.");
  if (!["percent", "atr"].includes(cfg.stopMode))
    errors.push("STOP_MODE 'percent' veya 'atr' olmali.");
  if (cfg.stopMode === "atr" && (cfg.atrStopMult <= 0 || cfg.atrTpMult <= 0))
    errors.push("ATR_STOP_MULT ve ATR_TP_MULT pozitif olmali.");
  if (cfg.htfFilter && (!Number.isInteger(cfg.htfMultiple) || cfg.htfMultiple < 2))
    errors.push("HTF_MULTIPLE en az 2 olan bir tam sayi olmali.");
  if (cfg.partialTpPct > 0 && (cfg.partialTpSize < 1 || cfg.partialTpSize > 90))
    errors.push("PARTIAL_TP_SIZE 1-90 arasinda olmali (pozisyonun tamamini kismi satista kapatmayin).");
  if (cfg.donchianExit >= cfg.donchianEntry)
    errors.push("DONCHIAN_EXIT, DONCHIAN_ENTRY'den kucuk olmali.");
  if (cfg.supertrendPeriod <= 0 || cfg.supertrendMult <= 0)
    errors.push("SUPERTREND_PERIOD ve SUPERTREND_MULT pozitif olmali.");
  if (cfg.pyramidMaxAddons > 0) {
    if (cfg.pyramidSizeFactor <= 0 || cfg.pyramidSizeFactor > 1)
      errors.push("PYRAMID_SIZE_FACTOR 0-1 arasinda olmali (kademeler kuculmeli).");
    if (cfg.pyramidTriggerPct <= 0)
      errors.push("PYRAMID_TRIGGER_PCT pozitif olmali.");
  }
  if (!["percent", "atr"].includes(cfg.trailingMode))
    errors.push("TRAILING_MODE 'percent' veya 'atr' olmali.");
  if (!["text", "json"].includes(cfg.logFormat))
    errors.push("LOG_FORMAT 'text' veya 'json' olmali.");
  if (cfg.correlationMax < 0 || cfg.correlationMax > 1)
    errors.push("CORRELATION_MAX 0-1 arasinda olmali (or. 0.85).");
  if (cfg.confluenceMinVotes < 1)
    errors.push("CONFLUENCE_MIN_VOTES en az 1 olmali.");
  if (cfg.minRr > 0) {
    const rr = cfg.stopMode === "atr"
      ? cfg.atrTpMult / cfg.atrStopMult
      : cfg.takeProfitPct / cfg.stopLossPct;
    if (rr < cfg.minRr)
      errors.push(
        `Odul/risk orani ${rr.toFixed(2)} < MIN_RR ${cfg.minRr}. ` +
        `Hedefi buyutun veya stopu daraltin - dusuk odul/risk uzun vadede kaybettirir.`
      );
  }
  return errors;
}
