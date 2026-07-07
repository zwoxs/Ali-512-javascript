import { readFileSync, writeFileSync, mkdirSync, existsSync, renameSync } from "node:fs";
import path from "node:path";
import { config } from "./config.js";
import { log } from "./logger.js";

const STATE_FILE = path.join(config.dataDir, "state.json");

/**
 * Durum kaliciligi: bot yeniden baslatildiginda acik pozisyonlar,
 * devre kesici sayaclari ve bakiye diskten geri yuklenir.
 * Yazim atomiktir (gecici dosya + rename) - yarim dosya riski yoktur.
 */
export function saveState(portfolio, risk) {
  const state = {
    savedAt: new Date().toISOString(),
    tradeMode: config.tradeMode,
    quote: portfolio.quote,
    positions: Object.fromEntries(portfolio.positions),
    trades: portfolio.trades,
    wins: portfolio.wins,
    realizedPnl: portfolio.realizedPnl,
    risk: {
      dayKey: risk.dayKey,
      dailyPnl: risk.dailyPnl,
      consecutiveLosses: risk.consecutiveLosses,
      cooldownUntil: risk.cooldownUntil,
      dailyLimitHit: risk.dailyLimitHit,
    },
  };
  if (!existsSync(config.dataDir)) mkdirSync(config.dataDir, { recursive: true });
  const tmp = STATE_FILE + ".tmp";
  writeFileSync(tmp, JSON.stringify(state, null, 2));
  renameSync(tmp, STATE_FILE);
}

export function loadState(portfolio, risk) {
  if (!existsSync(STATE_FILE)) return false;
  try {
    const state = JSON.parse(readFileSync(STATE_FILE, "utf8"));
    if (state.tradeMode !== config.tradeMode) {
      log.warn(`Kayitli durum '${state.tradeMode}' moduna ait, su anki mod '${config.tradeMode}' - durum yuklenmedi.`);
      return false;
    }
    portfolio.quote = state.quote;
    portfolio.positions = new Map(Object.entries(state.positions || {}));
    portfolio.trades = state.trades || 0;
    portfolio.wins = state.wins || 0;
    portfolio.realizedPnl = state.realizedPnl || 0;
    Object.assign(risk, state.risk || {});
    log.info(`Durum geri yuklendi (${state.savedAt}): ${portfolio.positions.size} acik pozisyon, bakiye ${portfolio.quote.toFixed(2)} TRY`);
    return true;
  } catch (err) {
    log.error(`Durum dosyasi okunamadi: ${err.message}`);
    return false;
  }
}
