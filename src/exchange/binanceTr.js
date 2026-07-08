import { createHmac, randomBytes } from "node:crypto";
import { config } from "../config.js";

/**
 * Idempotent istemci emir kimligi uretir.
 * Ag hatasi sonrasi bir emir yeniden gonderilirse, AYNI clientOrderId ile
 * gonderildiginde borsa ikinci emri reddeder - boylece cift dolum onlenir.
 * Format: bot-<symbol>-<side>-<zaman36>-<rastgele>. Binance 36 karakter siniri.
 */
export function makeClientOrderId(symbol, side) {
  const sym = symbol.replace(/[^A-Z0-9]/gi, "").slice(0, 8);
  const rand = randomBytes(3).toString("hex");
  return `b${sym}${side[0]}${Date.now().toString(36)}${rand}`.slice(0, 36);
}

// ---------------------------------------------------------------------------
// Binance TR Open API - imzali (canli emir) istekler
// Dokumantasyon: https://www.trbinance.com/apidocs
// NOT: Binance TR'nin Turkiye'deki hizmet durumu ve API yollari degisebilir.
// Canli moda gecmeden once guncel resmi dokumantasyonu MUTLAKA dogrulayin.
// ---------------------------------------------------------------------------

function sign(queryString) {
  return createHmac("sha256", config.apiSecret).update(queryString).digest("hex");
}

// Borsa saati senkronizasyonu: yerel saat borsadan sapmissa imzali istekler
// "timestamp outside recvWindow" hatasiyla reddedilir. Ofset 30 dk'da bir tazelenir.
let timeOffset = 0;
let lastClockSync = 0;

async function syncClock() {
  if (Date.now() - lastClockSync < 30 * 60_000) return;
  try {
    const res = await fetch(`${config.marketBaseUrl}/api/v3/time`, {
      signal: AbortSignal.timeout(5_000),
    });
    const { serverTime } = await res.json();
    timeOffset = serverTime - Date.now();
    lastClockSync = Date.now();
  } catch {
    // senkronizasyon basarisiz: mevcut ofsetle devam edilir
  }
}

async function signedRequest(method, endpoint, params = {}) {
  if (!config.apiKey || !config.apiSecret) {
    throw new Error("API anahtari eksik: BINANCE_TR_API_KEY / BINANCE_TR_API_SECRET ayarlayin.");
  }
  await syncClock();
  const query = new URLSearchParams({
    ...params,
    timestamp: String(Date.now() + timeOffset),
    recvWindow: "5000",
  });
  query.append("signature", sign(query.toString()));

  const url = `${config.tradeBaseUrl}${endpoint}`;
  const res = await fetch(method === "GET" ? `${url}?${query}` : url, {
    method,
    headers: {
      "X-MBX-APIKEY": config.apiKey,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: method === "GET" ? undefined : query.toString(),
    signal: AbortSignal.timeout(15_000),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || (data.code && data.code !== 0 && data.code !== 200)) {
    throw new Error(`Binance TR API hatasi (${endpoint}): ${JSON.stringify(data)}`);
  }
  return data;
}

/** Hesap bakiyelerini getirir (live mod). */
export function getAccount() {
  return signedRequest("GET", "/open/v1/account/spot");
}

/**
 * Piyasa (MARKET) emri gonderir (live mod).
 * Binance TR Open API sembol formati alt cizgilidir: BTC_TRY
 * side kodlamasi: BUY -> 0, SELL -> 1; type: 2 -> MARKET
 * @param {string} [clientOrderId] - idempotency icin; verilmezse otomatik uretilir
 */
export function placeMarketOrder(symbol, side, quantity, clientOrderId) {
  const trSymbol = symbol.includes("_") ? symbol : symbol.replace(/(TRY|USDT|BTC|ETH)$/, "_$1");
  return signedRequest("POST", "/open/v1/orders", {
    symbol: trSymbol,
    side: side === "BUY" ? "0" : "1",
    type: "2",
    quantity: String(quantity),
    newClientOrderId: clientOrderId || makeClientOrderId(symbol, side),
  });
}
