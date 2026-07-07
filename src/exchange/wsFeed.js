import { config } from "../config.js";
import { fetchKlines } from "./market.js";
import { log } from "../logger.js";

const MAX_CANDLES = 500;
const STALE_MS = 90_000;

/**
 * Gercek zamanli piyasa verisi katmani.
 *
 * WebSocket kline akisiyla mum onbellegini canli tutar; baglanti koptugunda
 * ustel geri cekilme ile yeniden baglanir. WebSocket yoksa (Node < 21 /
 * WS_ENABLED=false) veya akis bayatlarsa SEFFAF sekilde REST'e geri duser -
 * motor hangi kaynaktan beslendigini bilmez.
 */
export class MarketFeed {
  constructor(symbols, interval, cfg = config) {
    this.symbols = symbols;
    this.interval = interval;
    this.cfg = cfg;
    this.cache = new Map(); // symbol -> candles[] (candle.final: mum kapandi mi)
    this.lastEvent = 0;
    this.ws = null;
    this.reconnectDelay = 1000;
    this.stopped = false;
    this.wsSupported = cfg.wsEnabled && typeof WebSocket !== "undefined";
  }

  async _seed(symbol) {
    const candles = await fetchKlines(symbol, this.interval, 300);
    candles.forEach((c, i) => (c.final = i < candles.length - 1));
    this.cache.set(symbol, candles);
  }

  async init() {
    for (const symbol of this.symbols) await this._seed(symbol);
    if (this.wsSupported) {
      this._connect();
    } else {
      log.info("WebSocket kullanilamiyor veya kapali - REST yoklama modunda calisiliyor.");
    }
  }

  _connect() {
    if (this.stopped) return;
    const streams = this.symbols
      .map((s) => `${s.toLowerCase()}@kline_${this.interval}`)
      .join("/");
    const url = `${this.cfg.wsBaseUrl}/stream?streams=${streams}`;
    try {
      this.ws = new WebSocket(url);
    } catch (err) {
      log.warn(`WebSocket acilamadi (${err.message}) - REST moduna gecildi.`);
      this.wsSupported = false;
      return;
    }
    this.ws.onopen = () => {
      this.reconnectDelay = 1000;
      this.lastEvent = Date.now();
      log.info(`WebSocket bagli: ${streams}`);
    };
    this.ws.onmessage = (ev) => this._onMessage(ev);
    this.ws.onerror = () => {}; // ardindan onclose gelir
    this.ws.onclose = () => this._scheduleReconnect();
  }

  _scheduleReconnect() {
    if (this.stopped) return;
    log.warn(`WebSocket koptu; ${this.reconnectDelay / 1000}s sonra yeniden baglanilacak.`);
    setTimeout(() => this._connect(), this.reconnectDelay).unref?.();
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, 60_000);
  }

  _onMessage(ev) {
    try {
      const msg = JSON.parse(ev.data);
      const k = msg.data?.k;
      if (!k) return;
      const candles = this.cache.get(msg.data.s);
      if (!candles) return;
      const candle = {
        openTime: k.t,
        open: +k.o, high: +k.h, low: +k.l, close: +k.c,
        volume: +k.v,
        closeTime: k.T,
        final: k.x,
      };
      const lastCandle = candles[candles.length - 1];
      if (lastCandle && lastCandle.openTime === candle.openTime) {
        candles[candles.length - 1] = candle;
      } else {
        candles.push(candle);
        if (candles.length > MAX_CANDLES) candles.shift();
      }
      this.lastEvent = Date.now();
    } catch {
      // bozuk mesaj: yut, akis devam eder
    }
  }

  _isStale() {
    return !this.wsSupported || Date.now() - this.lastEvent > STALE_MS;
  }

  /**
   * Motorun tuketecegi anlik goruntu. Akis bayatsa once REST ile tazelenir.
   * @returns {Promise<{closedCandles: Array, currentPrice: number}>}
   */
  async snapshot(symbol) {
    if (this._isStale()) {
      log.debug(`${symbol}: akis bayat/kapali - REST ile tazeleniyor.`);
      await this._seed(symbol);
    }
    const candles = this.cache.get(symbol);
    if (!candles?.length) throw new Error(`${symbol} icin mum verisi yok.`);
    const lastCandle = candles[candles.length - 1];
    const closedCandles = lastCandle.final ? candles.slice() : candles.slice(0, -1);
    return { closedCandles, currentPrice: lastCandle.close };
  }

  stop() {
    this.stopped = true;
    try { this.ws?.close(); } catch { /* kapanista hata onemsiz */ }
  }
}
