import { log } from "../logger.js";
import { splitSymbol } from "./reconciler.js";

/**
 * Haber duyarlilik filtresi.
 *
 * Bir coine GIRIS yapmadan once guncel haber basliklarini ceker ve duyarlilik
 * puanlar. Guclu olumsuz haber akisi varsa (hack, yasak, dava, cokus...) giris
 * engellenir. Bu bir SINYAL URETICISI DEGIL, bir KORUMA filtresidir: kotu
 * haberde teknik sinyali veto eder, iyi haberde tek basina alim yapmaz.
 *
 * DURUSTLUK NOTU: Haberler gecikmeli, celiskili ve manipulasyona acik olabilir;
 * bu filtre riski azaltir ama "haberi onceden gorup kar etme" araci degildir.
 * Anahtar kelime tabanlidir (harici LLM/ucretli servis gerektirmez).
 */

// Kripto haber duyarlilik sozlugu. Agirlik = siddet (mutlak deger buyudukce guclu).
export const LEXICON = {
  // Guclu olumsuz
  hack: -3, hacked: -3, exploit: -3, exploited: -3, breach: -3, stolen: -3,
  ban: -3, banned: -3, lawsuit: -3, "sec charges": -3, fraud: -3, scam: -3,
  rug: -3, rugpull: -3, "rug pull": -3, insolvent: -3, bankruptcy: -3, collapse: -3,
  halt: -2, halted: -2, delist: -3, delisted: -3, delisting: -3,
  // Olumsuz
  crash: -2, plunge: -2, plunges: -2, dump: -2, dumps: -2, "sell-off": -2, selloff: -2,
  bearish: -2, liquidation: -2, liquidated: -2, warning: -1, investigation: -2,
  decline: -1, declines: -1, drop: -1, drops: -1, fall: -1, falls: -1, slump: -2,
  fear: -1, fud: -1, lawsuit_filed: -2, probe: -2, freeze: -2, frozen: -2, outage: -2,
  // Olumlu
  surge: 2, surges: 2, rally: 2, rallies: 2, soar: 2, soars: 2, bullish: 2,
  breakout: 2, gain: 1, gains: 1, jump: 1, jumps: 1, "record high": 2, "all-time high": 2,
  adoption: 2, partnership: 2, integration: 1, listing: 2, listed: 2, upgrade: 1,
  approval: 2, approved: 2, "etf approval": 3, mainnet: 1, launch: 1, launches: 1,
  institutional: 2, accumulate: 1, accumulation: 1, halving: 1, rebound: 2, recovery: 1,
};

/**
 * Tek bir metni puanlar. Buyuk/kucuk harf duyarsiz; coklu kelime kaliplari once.
 * @returns {number} net puan
 */
export function scoreText(text, lexicon = LEXICON) {
  if (!text) return 0;
  const lower = ` ${String(text).toLowerCase()} `;
  let score = 0;
  for (const [term, weight] of Object.entries(lexicon)) {
    if (term.includes(" ") || term.includes("-")) {
      if (lower.includes(term)) score += weight;
    } else {
      // kelime siniri: yanlis eslesmeleri onle (or. "banned" != "band")
      const re = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "g");
      const hits = lower.match(re);
      if (hits) score += weight * hits.length;
    }
  }
  return score;
}

/**
 * Basliklari topluca degerlendirir.
 * @param {string[]} headlines
 * @returns {{score:number, avg:number, count:number, label:string}}
 */
export function scoreHeadlines(headlines, lexicon = LEXICON) {
  const count = headlines.length;
  if (count === 0) return { score: 0, avg: 0, count: 0, label: "veri-yok" };
  const score = headlines.reduce((s, h) => s + scoreText(h, lexicon), 0);
  const avg = score / count;
  const label = avg <= -0.5 ? "olumsuz" : avg >= 0.5 ? "olumlu" : "notr";
  return { score, avg, count, label };
}

// --- Haber cekme (ag) ---

const cache = new Map(); // asset -> { ts, headlines }

async function fetchJson(url, headers = {}) {
  const res = await fetch(url, { headers, signal: AbortSignal.timeout(8_000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/** CryptoPanic API'den baslik ceker (ucretsiz kademe: auth_token gerekir). */
async function fetchCryptoPanic(asset, cfg) {
  const url = `${cfg.newsApiUrl || "https://cryptopanic.com/api/v1/posts/"}` +
    `?auth_token=${encodeURIComponent(cfg.newsApiKey)}&currencies=${asset}&kind=news&public=true`;
  const data = await fetchJson(url);
  return (data.results || []).map((r) => r.title).filter(Boolean);
}

/** Genel RSS/Atom akisindan <title> basliklarini ceker (regex ile, bagimlilik yok). */
async function fetchRss(asset, cfg) {
  const urls = (cfg.newsRssUrls || "").split(",").map((u) => u.trim()).filter(Boolean);
  const all = [];
  for (const url of urls) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(8_000) });
      if (!res.ok) continue;
      const xml = await res.text();
      const titles = [...xml.matchAll(/<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?<\/title>/gis)]
        .map((m) => m[1].trim())
        .filter(Boolean)
        .slice(1); // ilk <title> genelde akisin adi
      // Sadece bu varligi anan basliklari filtrele (gurultuyu azalt)
      const re = new RegExp(`\\b${asset}\\b`, "i");
      all.push(...titles.filter((t) => re.test(t) || urls.length === 1));
    } catch (err) {
      log.debug(`RSS cekme hatasi (${url}): ${err.message}`);
    }
  }
  return all;
}

/**
 * Sembol icin guncel haber duyarliligini dondurur (onbellekli).
 * @returns {Promise<{score,avg,count,label,cached}>}
 */
export async function getSentiment(symbol, cfg) {
  const { base } = splitSymbol(symbol);
  const now = Date.now();
  const cached = cache.get(base);
  if (cached && now - cached.ts < cfg.newsCacheSec * 1000) {
    return { ...scoreHeadlines(cached.headlines), cached: true };
  }
  let headlines = [];
  try {
    if (cfg.newsSource === "cryptopanic") {
      if (!cfg.newsApiKey) throw new Error("NEWS_API_KEY eksik (cryptopanic icin gerekli).");
      headlines = await fetchCryptoPanic(base, cfg);
    } else if (cfg.newsSource === "rss") {
      headlines = await fetchRss(base, cfg);
    }
  } catch (err) {
    log.warn(`${symbol} haber cekme basarisiz: ${err.message}`);
    return { score: 0, avg: 0, count: 0, label: "veri-yok", cached: false, error: err.message };
  }
  cache.set(base, { ts: now, headlines });
  return { ...scoreHeadlines(headlines), cached: false };
}

/**
 * Giris kapisi: haber duyarliligi esigin altindaysa engel nedeni dondurur.
 * Yeterli sayida makale yoksa (veri az) ENGELLEMEZ - eksik veriyle veto koymaz.
 * @returns {Promise<string|null>}
 */
export async function newsBlocked(symbol, cfg) {
  if (!cfg.newsFilter) return null;
  const s = await getSentiment(symbol, cfg);
  if (s.count < cfg.newsMinArticles) return null; // yetersiz veri: filtre uygulanmaz
  if (s.avg < cfg.newsMinScore) {
    return `Haber duyarliligi olumsuz (ort ${s.avg.toFixed(2)} < ${cfg.newsMinScore}, ${s.count} baslik) - giris ertelendi.`;
  }
  return null;
}

/** Test/izleme icin onbellegi temizler. */
export function _clearCache() {
  cache.clear();
}
