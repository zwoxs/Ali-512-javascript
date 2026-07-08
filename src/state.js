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
      equityPeak: risk.equityPeak,
      killSwitch: risk.killSwitch, // acil fren yeniden baslatmada da korunur
    },
  };
  if (!existsSync(config.dataDir)) mkdirSync(config.dataDir, { recursive: true });
  const tmp = STATE_FILE + ".tmp";
  writeFileSync(tmp, JSON.stringify(state, null, 2));
  renameSync(tmp, STATE_FILE);
}

const isFiniteNum = (v) => typeof v === "number" && Number.isFinite(v);

/**
 * Kayitli durumu dogrular. Bozuk/eksik veri (NaN, undefined) muhasebeyi zehirler
 * ve NaN karsilastirmalari stop'lari SESSIZCE devre disi birakir - bu yuzden
 * gecersiz durum YUKLENMEZ, bot temiz baslar. "Hata yapma luksu yok" invaryanti.
 * @returns {{ok: boolean, reason?: string}}
 */
export function validateState(state) {
  if (!state || typeof state !== "object") return { ok: false, reason: "durum nesnesi degil" };
  if (!isFiniteNum(state.quote) || state.quote < 0)
    return { ok: false, reason: `gecersiz bakiye: ${state.quote}` };
  for (const [k, v] of [["trades", state.trades], ["wins", state.wins], ["realizedPnl", state.realizedPnl]]) {
    if (v != null && !isFiniteNum(v)) return { ok: false, reason: `gecersiz ${k}: ${v}` };
  }
  for (const [symbol, pos] of Object.entries(state.positions || {})) {
    if (!pos || !isFiniteNum(pos.qty) || pos.qty <= 0)
      return { ok: false, reason: `${symbol} gecersiz miktar: ${pos?.qty}` };
    if (!isFiniteNum(pos.entryPrice) || pos.entryPrice <= 0)
      return { ok: false, reason: `${symbol} gecersiz giris fiyati: ${pos?.entryPrice}` };
  }
  if (state.risk) {
    for (const key of ["dailyPnl", "cooldownUntil", "equityPeak", "consecutiveLosses"]) {
      const v = state.risk[key];
      if (v != null && !isFiniteNum(v)) return { ok: false, reason: `risk.${key} gecersiz: ${v}` };
    }
  }
  return { ok: true };
}

export function loadState(portfolio, risk) {
  if (!existsSync(STATE_FILE)) return false;
  let state;
  try {
    state = JSON.parse(readFileSync(STATE_FILE, "utf8"));
  } catch (err) {
    log.error(`Durum dosyasi okunamadi/bozuk: ${err.message} - temiz baslaniyor.`);
    return false;
  }
  if (state.tradeMode !== config.tradeMode) {
    log.warn(`Kayitli durum '${state.tradeMode}' moduna ait, su anki mod '${config.tradeMode}' - durum yuklenmedi.`);
    return false;
  }
  const check = validateState(state);
  if (!check.ok) {
    log.error(`Durum dogrulamasi BASARISIZ (${check.reason}) - bozuk durum yuklenmedi, temiz baslaniyor.`);
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
}
