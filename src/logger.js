import { appendFileSync, mkdirSync, existsSync } from "node:fs";
import path from "node:path";
import { config } from "./config.js";

const LOG_DIR = path.join(config.root, "logs");

function ensureLogDir() {
  if (!existsSync(LOG_DIR)) mkdirSync(LOG_DIR, { recursive: true });
}

function stamp() {
  return new Date().toISOString().replace("T", " ").slice(0, 19);
}

export const log = {
  info: (msg) => console.log(`[${stamp()}] INFO  ${msg}`),
  warn: (msg) => console.warn(`[${stamp()}] UYARI ${msg}`),
  error: (msg) => console.error(`[${stamp()}] HATA  ${msg}`),
  trade: (record) => {
    const line = `[${stamp()}] ISLEM ${record.side} ${record.qty} ${record.symbol} @ ${record.price} | ${record.reason}`;
    console.log(line);
    ensureLogDir();
    appendFileSync(
      path.join(LOG_DIR, "trades.jsonl"),
      JSON.stringify({ ts: Date.now(), ...record }) + "\n"
    );
  },
};
