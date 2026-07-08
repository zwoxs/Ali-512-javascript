import { config } from "../config.js";
import { log } from "../logger.js";

/**
 * Piyasa verisi katmani - ustel geri cekilmeli yeniden deneme ile.
 * Gecici hatalar (ag, 5xx, 429 rate-limit) sessizce tolere edilir;
 * kalici hatalar (4xx) aninda firlatilir.
 */
async function fetchWithRetry(url, { retries = 4, baseDelayMs = 1000 } = {}) {
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(15_000) });
      if (res.ok) return res.json();
      if (res.status === 429 || res.status === 418) {
        // Rate limit: Retry-After basligina saygi goster
        const wait = (parseInt(res.headers.get("retry-after") || "0", 10) || 5) * 1000;
        log.warn(`Rate limit (HTTP ${res.status}), ${wait / 1000}s bekleniyor...`);
        await new Promise((r) => setTimeout(r, wait));
        continue;
      }
      if (res.status >= 500) {
        lastErr = new Error(`HTTP ${res.status}`);
      } else {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
    } catch (err) {
      if (err.name === "TimeoutError") lastErr = new Error("Istek zaman asimi");
      else if (err.message.startsWith("HTTP 4")) throw err;
      else lastErr = err;
    }
    const delay = baseDelayMs * 2 ** attempt;
    log.debug(`Yeniden deneme ${attempt + 1}/${retries} (${delay}ms): ${lastErr?.message}`);
    await new Promise((r) => setTimeout(r, delay));
  }
  throw new Error(`Istek ${retries} denemede basarisiz: ${lastErr?.message} (${url})`);
}

/**
 * Kline/mum verisi ceker.
 * TRY pariteleri global Binance API'de de listelendigi icin varsayilan
 * MARKET_BASE_URL=https://api.binance.com kullanilir.
 * @returns {Promise<Array<{openTime,open,high,low,close,volume,closeTime}>>}
 */
export async function fetchKlines(symbol, interval, limit = 300) {
  const url = `${config.marketBaseUrl}/api/v3/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`;
  const raw = await fetchWithRetry(url);
  return raw.map((k) => ({
    openTime: k[0],
    open: parseFloat(k[1]),
    high: parseFloat(k[2]),
    low: parseFloat(k[3]),
    close: parseFloat(k[4]),
    volume: parseFloat(k[5]),
    closeTime: k[6],
  }));
}

export async function fetchLastPrice(symbol) {
  const url = `${config.marketBaseUrl}/api/v3/ticker/price?symbol=${symbol}`;
  const data = await fetchWithRetry(url);
  return parseFloat(data.price);
}

/**
 * Disk onbellekli kline verisi - backtest/optimizasyon icin.
 * Ayni veri 10 dk icinde tekrar istenirse API'ye gidilmez; optimizasyonda
 * yuzlerce kosum tek indirmeyle beslenir, rate-limit riski sifirlanir.
 */
export async function fetchKlinesCached(symbol, interval, limit = 300, ttlMs = 600_000) {
  const { readFileSync, writeFileSync, mkdirSync, existsSync, statSync } = await import("node:fs");
  const path = await import("node:path");
  const dir = path.join(config.dataDir, "cache");
  const file = path.join(dir, `${symbol}-${interval}-${limit}.json`);

  if (existsSync(file) && Date.now() - statSync(file).mtimeMs < ttlMs) {
    try {
      return JSON.parse(readFileSync(file, "utf8"));
    } catch {
      // bozuk onbellek: yeniden indir
    }
  }
  const klines = await fetchKlines(symbol, interval, limit);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(file, JSON.stringify(klines));
  return klines;
}

/** Sembolun LOT_SIZE adim buyuklugunu getirir (miktar yuvarlama icin). */
export async function fetchLotStep(symbol) {
  const url = `${config.marketBaseUrl}/api/v3/exchangeInfo?symbol=${symbol}`;
  const data = await fetchWithRetry(url);
  const filters = data.symbols?.[0]?.filters || [];
  const lot = filters.find((f) => f.filterType === "LOT_SIZE");
  return lot ? parseFloat(lot.stepSize) : 0.000001;
}

/** Sembolun tum emir filtrelerini getirir (LOT_SIZE, MIN_NOTIONAL, PRICE_FILTER). */
export async function fetchSymbolFilters(symbol) {
  const { parseFilters } = await import("./filters.js");
  const url = `${config.marketBaseUrl}/api/v3/exchangeInfo?symbol=${symbol}`;
  const data = await fetchWithRetry(url);
  return parseFilters(data.symbols?.[0]);
}
