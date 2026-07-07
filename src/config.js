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
const str = (key, def) => process.env[key] || def;

export const config = {
  root: ROOT,
  tradeMode: str("TRADE_MODE", "paper").toLowerCase(),
  symbol: str("SYMBOL", "BTCTRY").toUpperCase(),
  interval: str("INTERVAL", "15m"),
  pollSeconds: num("POLL_SECONDS", 30),

  emaFast: num("EMA_FAST", 9),
  emaSlow: num("EMA_SLOW", 21),
  rsiPeriod: num("RSI_PERIOD", 14),
  rsiOverbought: num("RSI_OVERBOUGHT", 70),
  rsiOversold: num("RSI_OVERSOLD", 30),

  paperBalance: num("PAPER_BALANCE", 10000),
  positionPct: num("POSITION_PCT", 25),
  stopLossPct: num("STOP_LOSS_PCT", 2),
  takeProfitPct: num("TAKE_PROFIT_PCT", 4),
  feePct: num("FEE_PCT", 0.1),

  marketBaseUrl: str("MARKET_BASE_URL", "https://api.binance.com"),
  tradeBaseUrl: str("TRADE_BASE_URL", "https://api.trbinance.com"),
  apiKey: str("BINANCE_TR_API_KEY", ""),
  apiSecret: str("BINANCE_TR_API_SECRET", ""),
};

export function validateConfig() {
  const errors = [];
  if (!["paper", "live"].includes(config.tradeMode))
    errors.push(`TRADE_MODE 'paper' veya 'live' olmali (su an: ${config.tradeMode})`);
  if (config.tradeMode === "live" && (!config.apiKey || !config.apiSecret))
    errors.push("Live mod icin BINANCE_TR_API_KEY ve BINANCE_TR_API_SECRET zorunlu.");
  if (config.emaFast >= config.emaSlow)
    errors.push("EMA_FAST, EMA_SLOW'dan kucuk olmali.");
  if (config.positionPct <= 0 || config.positionPct > 100)
    errors.push("POSITION_PCT 0-100 arasinda olmali.");
  return errors;
}
