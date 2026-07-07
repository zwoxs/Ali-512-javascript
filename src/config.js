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

export const INTERVAL_MS = {
  "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
  "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000,
  "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000, "1w": 604_800_000,
};

export const config = {
  root: ROOT,
  dataDir: path.join(ROOT, "data"),
  logDir: path.join(ROOT, "logs"),

  tradeMode: str("TRADE_MODE", "paper").toLowerCase(),
  symbols: str("SYMBOLS", str("SYMBOL", "BTCTRY"))
    .toUpperCase()
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
  interval: str("INTERVAL", "15m"),
  pollSeconds: num("POLL_SECONDS", 30),
  logLevel: str("LOG_LEVEL", "info").toLowerCase(),

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

  // Sermaye ve boyutlama
  paperBalance: num("PAPER_BALANCE", 10000),
  sizingMode: str("SIZING_MODE", "percent").toLowerCase(), // percent | risk
  positionPct: num("POSITION_PCT", 25),        // percent modu: bakiyenin %'si
  riskPerTradePct: num("RISK_PER_TRADE_PCT", 1), // risk modu: islem basina riske edilen sermaye %'si

  // Cikis kurallari
  stopLossPct: num("STOP_LOSS_PCT", 2),
  takeProfitPct: num("TAKE_PROFIT_PCT", 4),
  trailingStopPct: num("TRAILING_STOP_PCT", 0), // 0 = kapali

  // Devre kesiciler
  maxDailyLossPct: num("MAX_DAILY_LOSS_PCT", 5),      // gunluk zarar limiti (baslangic sermayesine gore %)
  maxConsecutiveLosses: num("MAX_CONSECUTIVE_LOSSES", 3),
  cooldownMinutes: num("COOLDOWN_MINUTES", 60),

  // Islem maliyetleri
  feePct: num("FEE_PCT", 0.1),
  slippagePct: num("SLIPPAGE_PCT", 0.05), // paper/backtest gerceklik payi

  // API
  marketBaseUrl: str("MARKET_BASE_URL", "https://api.binance.com"),
  tradeBaseUrl: str("TRADE_BASE_URL", "https://api.trbinance.com"),
  apiKey: str("BINANCE_TR_API_KEY", ""),
  apiSecret: str("BINANCE_TR_API_SECRET", ""),

  // Bildirim
  telegramToken: str("TELEGRAM_BOT_TOKEN", ""),
  telegramChatId: str("TELEGRAM_CHAT_ID", ""),
};

export function validateConfig(cfg = config) {
  const errors = [];
  if (!["paper", "live"].includes(cfg.tradeMode))
    errors.push(`TRADE_MODE 'paper' veya 'live' olmali (su an: ${cfg.tradeMode})`);
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
  return errors;
}
