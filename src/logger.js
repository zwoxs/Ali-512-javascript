import { appendFileSync, mkdirSync, existsSync } from "node:fs";
import path from "node:path";
import { config } from "./config.js";

const LEVELS = { debug: 10, info: 20, warn: 30, error: 40 };
const threshold = LEVELS[config.logLevel] ?? LEVELS.info;

function ensureDir(dir) {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

const stamp = () => new Date().toISOString().replace("T", " ").slice(0, 19);

function write(level, label, msg) {
  if (LEVELS[level] < threshold) return;
  // json formati log toplayicilar (Loki, CloudWatch, ELK...) icin
  const line = config.logFormat === "json"
    ? JSON.stringify({ ts: new Date().toISOString(), level, msg })
    : `[${stamp()}] ${label} ${msg}`;
  (level === "error" ? console.error : level === "warn" ? console.warn : console.log)(line);
  ensureDir(config.logDir);
  appendFileSync(path.join(config.logDir, "bot.log"), line + "\n");
}

export const log = {
  debug: (msg) => write("debug", "DEBUG", msg),
  info: (msg) => write("info", "INFO ", msg),
  warn: (msg) => write("warn", "UYARI", msg),
  error: (msg) => write("error", "HATA ", msg),
  /** Islem kaydi: konsol + logs/trades.jsonl (makine-okur denetim izi) */
  trade: (record) => {
    const pnlTxt = record.pnl != null ? ` | K/Z: ${record.pnl.toFixed(2)} TRY` : "";
    write("info", "ISLEM", `${record.side} ${record.qty} ${record.symbol} @ ${record.price}${pnlTxt} | ${record.reason}`);
    ensureDir(config.logDir);
    appendFileSync(
      path.join(config.logDir, "trades.jsonl"),
      JSON.stringify({ ts: new Date().toISOString(), ...record }) + "\n"
    );
  },
};
