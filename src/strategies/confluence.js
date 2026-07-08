// Konsensus (ensemble) meta-stratejisi.
// Birden fazla uye strateji ayni mumu degerlendirir; sinyal ancak
// CONFLUENCE_MIN_VOTES kadar uye ayni yonde oy verirse uretilir.
// Tek gostergenin yaniltmasina karsi mutabakat filtresi - daha az ama
// daha yuksek kaliteli islem.

import { getStrategy } from "./index.js";

export const name = "Konsensus (coklu strateji oylamasi)";

function members(cfg) {
  const names = (cfg.confluenceStrategies || []).filter((n) => n !== "confluence");
  if (names.length === 0) throw new Error("CONFLUENCE_STRATEGIES bos olamaz.");
  return names.map((n) => ({ name: n, strategy: getStrategy(n) }));
}

export function warmup(cfg) {
  return Math.max(...members(cfg).map((m) => m.strategy.warmup(cfg)));
}

export function evaluate(candles, cfg) {
  const votes = { BUY: [], SELL: [], HOLD: [] };
  for (const m of members(cfg)) {
    const { signal } = m.strategy.evaluate(candles, cfg);
    votes[signal].push(m.name);
  }

  const snapshot = {
    price: candles[candles.length - 1]?.close,
    buyVotes: votes.BUY.length,
    sellVotes: votes.SELL.length,
    voters: { BUY: votes.BUY, SELL: votes.SELL },
  };

  const need = cfg.confluenceMinVotes;
  if (votes.BUY.length >= need && votes.BUY.length > votes.SELL.length) {
    return { signal: "BUY", reason: `Konsensus AL: ${votes.BUY.join("+")} (${votes.BUY.length}/${need} oy)`, snapshot };
  }
  if (votes.SELL.length >= need && votes.SELL.length > votes.BUY.length) {
    return { signal: "SELL", reason: `Konsensus SAT: ${votes.SELL.join("+")} (${votes.SELL.length}/${need} oy)`, snapshot };
  }
  return { signal: "HOLD", reason: `Yetersiz mutabakat (AL:${votes.BUY.length} SAT:${votes.SELL.length}, gereken:${need})`, snapshot };
}
