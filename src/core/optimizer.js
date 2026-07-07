import { runBacktest } from "./backtester.js";
import { getStrategy } from "../strategies/index.js";

/**
 * Walk-forward parametre optimizasyonu.
 *
 * Veriyi egitim (train) ve dogrulama (test) dilimlerine boler:
 * parametreler SADECE egitim diliminde aranir, en iyi adaylar hic gorulmemis
 * test diliminde dogrulanir. Boylece "geriye donuk mukemmel ama gercekte
 * calismayan" asiri uyum (overfitting) yakalanir: egitimde parlayip testte
 * coken kombinasyonlar elenmelidir.
 */

const GRIDS = {
  ema_rsi: {
    emaFast: [5, 9, 12],
    emaSlow: [21, 34, 55],
    stopLossPct: [1.5, 2, 3],
    takeProfitPct: [3, 4, 6],
  },
  macd: {
    macdFast: [8, 12],
    macdSlow: [21, 26],
    macdSignal: [7, 9],
    stopLossPct: [1.5, 2, 3],
    takeProfitPct: [3, 4, 6],
  },
  bollinger: {
    bbPeriod: [14, 20, 28],
    bbStdDev: [1.8, 2, 2.4],
    stopLossPct: [1.5, 2, 3],
    takeProfitPct: [3, 4, 6],
  },
  donchian: {
    donchianEntry: [10, 20, 40],
    donchianExit: [5, 10, 20],
    stopLossPct: [1.5, 2, 3],
    takeProfitPct: [4, 6, 10],
  },
  supertrend: {
    supertrendPeriod: [7, 10, 14],
    supertrendMult: [2, 3, 4],
    stopLossPct: [1.5, 2, 3],
    takeProfitPct: [4, 6, 10],
  },
};

/** Kartezyen carpim: {a:[1,2], b:[3]} -> [{a:1,b:3},{a:2,b:3}] */
export function expandGrid(grid) {
  let combos = [{}];
  for (const [key, values] of Object.entries(grid)) {
    combos = combos.flatMap((combo) => values.map((v) => ({ ...combo, [key]: v })));
  }
  return combos;
}

/** Siralama skoru: getiriden dusus cezasi dusulur (riske gore duzeltilmis). */
export function score(metrics) {
  return metrics.totalReturnPct - 0.5 * metrics.maxDrawdownPct;
}

function isValidCombo(params, cfg) {
  const merged = { ...cfg, ...params };
  if (merged.emaFast >= merged.emaSlow) return false;
  if (merged.macdFast >= merged.macdSlow) return false;
  if (merged.donchianExit >= merged.donchianEntry) return false;
  return true;
}

/**
 * @param {object} opts
 * @param {Array}  opts.klines       - tarihsel mumlar
 * @param {object} opts.cfg          - taban yapilandirma
 * @param {string} opts.strategyName
 * @param {object} [opts.grid]       - ozel parametre izgarasi (varsayilan: strateji izgarasi)
 * @param {number} [opts.trainRatio] - egitim dilimi orani (varsayilan 0.7)
 * @param {number} [opts.topN]       - test dilimine tasinacak aday sayisi
 * @param {function} [opts.onProgress]
 */
export async function optimize({ klines, cfg, strategyName, grid, trainRatio = 0.7, topN = 5, onProgress }) {
  const strategy = getStrategy(strategyName);
  const combos = expandGrid(grid || GRIDS[strategyName] || GRIDS.ema_rsi)
    .filter((p) => isValidCombo(p, cfg));
  if (combos.length === 0) throw new Error("Gecerli parametre kombinasyonu yok.");

  const splitIdx = Math.floor(klines.length * trainRatio);
  const train = klines.slice(0, splitIdx);
  const test = klines.slice(splitIdx);
  if (train.length < 100 || test.length < 50) {
    throw new Error(`Yetersiz veri: egitim=${train.length}, test=${test.length} mum. Daha fazla mum cekin.`);
  }

  const results = [];
  for (let i = 0; i < combos.length; i++) {
    const runCfg = { ...cfg, ...combos[i] };
    const { metrics } = await runBacktest({ klines: train, cfg: runCfg, strategy, silent: true });
    results.push({ params: combos[i], train: metrics });
    onProgress?.(i + 1, combos.length);
  }

  results.sort((a, b) => score(b.train) - score(a.train));
  const top = results.slice(0, topN);
  for (const candidate of top) {
    const runCfg = { ...cfg, ...candidate.params };
    const { metrics } = await runBacktest({ klines: test, cfg: runCfg, strategy, silent: true });
    candidate.test = metrics;
  }

  return { results, top, trainBars: train.length, testBars: test.length };
}
