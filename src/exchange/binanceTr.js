import { createHmac } from "node:crypto";
import { config } from "../config.js";

/**
 * Piyasa verisi: kline/mum cekme.
 * TRY pariteleri (BTCTRY, ETHTRY...) global Binance API'sinde de listelendigi icin
 * varsayilan olarak MARKET_BASE_URL=https://api.binance.com kullanilir.
 * Donen her mum: { openTime, open, high, low, close, volume, closeTime }
 */
export async function fetchKlines(symbol, interval, limit = 200) {
  const url = `${config.marketBaseUrl}/api/v3/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Kline istegi basarisiz: HTTP ${res.status} - ${await res.text()}`);
  }
  const raw = await res.json();
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
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Fiyat istegi basarisiz: HTTP ${res.status}`);
  const data = await res.json();
  return parseFloat(data.price);
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
 * side: "BUY" -> 0, "SELL" -> 1 (TR Open API kodlamasi)
 */
export function placeMarketOrder(symbol, side, quantity) {
  const trSymbol = symbol.includes("_") ? symbol : symbol.replace(/(TRY|USDT|BTC|ETH)$/, "_$1");
  return signedRequest("POST", "/open/v1/orders", {
    symbol: trSymbol,
    side: side === "BUY" ? "0" : "1",
    type: "2", // 2 = MARKET
    quantity: String(quantity),
  });
}
