import { createHmac } from "node:crypto";
import { config } from "../config.js";

// ---------------------------------------------------------------------------
// Binance TR Open API - imzali (canli emir) istekler
// Dokumantasyon: https://www.trbinance.com/apidocs
// NOT: Binance TR'nin Turkiye'deki hizmet durumu ve API yollari degisebilir.
// Canli moda gecmeden once guncel resmi dokumantasyonu MUTLAKA dogrulayin.
// ---------------------------------------------------------------------------

function sign(queryString) {
  return createHmac("sha256", config.apiSecret).update(queryString).digest("hex");
}

async function signedRequest(method, endpoint, params = {}) {
  if (!config.apiKey || !config.apiSecret) {
    throw new Error("API anahtari eksik: BINANCE_TR_API_KEY / BINANCE_TR_API_SECRET ayarlayin.");
  }
  const query = new URLSearchParams({
    ...params,
    timestamp: Date.now().toString(),
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
 */
export function placeMarketOrder(symbol, side, quantity) {
  const trSymbol = symbol.includes("_") ? symbol : symbol.replace(/(TRY|USDT|BTC|ETH)$/, "_$1");
  return signedRequest("POST", "/open/v1/orders", {
    symbol: trSymbol,
    side: side === "BUY" ? "0" : "1",
    type: "2",
    quantity: String(quantity),
  });
}
