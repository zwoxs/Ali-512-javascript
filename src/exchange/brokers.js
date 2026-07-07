import { config } from "../config.js";
import { log } from "../logger.js";
import { placeMarketOrder } from "./binanceTr.js";
import { fetchLotStep } from "./market.js";

/** Miktari borsa adim buyuklugune (LOT_SIZE) asagi yuvarlar. */
export function roundToStep(qty, step) {
  if (!step || step <= 0) return qty;
  const rounded = Math.floor(qty / step) * step;
  // Kayan nokta artiklarini temizle
  const decimals = Math.max(0, -Math.floor(Math.log10(step)));
  return parseFloat(rounded.toFixed(decimals));
}

/**
 * Broker sozlesmesi: buy/sell -> { qty, price, fee } (fill) veya null.
 * Engine hangi broker ile konustugunu bilmez - paper ve live tamamen esdegerdir.
 */

/** Sanal broker: kayma (slippage) ve komisyonu simule eder. Gercek emir GONDERMEZ. */
export class PaperBroker {
  constructor(cfg = config) {
    this.cfg = cfg;
  }

  async buy(symbol, qty, price) {
    const fillPrice = price * (1 + this.cfg.slippagePct / 100);
    const roundedQty = roundToStep(qty, 0.000001);
    if (roundedQty <= 0) return null;
    return { qty: roundedQty, price: fillPrice, fee: roundedQty * fillPrice * (this.cfg.feePct / 100) };
  }

  async sell(symbol, qty, price) {
    const fillPrice = price * (1 - this.cfg.slippagePct / 100);
    return { qty, price: fillPrice, fee: qty * fillPrice * (this.cfg.feePct / 100) };
  }
}

/** Canli broker: Binance TR'ye imzali MARKET emri gonderir. */
export class LiveBroker {
  constructor(cfg = config) {
    this.cfg = cfg;
    this.lotSteps = new Map();
  }

  async _step(symbol) {
    if (!this.lotSteps.has(symbol)) {
      try {
        this.lotSteps.set(symbol, await fetchLotStep(symbol));
      } catch (err) {
        log.warn(`${symbol} LOT_SIZE alinamadi (${err.message}); 6 ondalik varsayiliyor.`);
        this.lotSteps.set(symbol, 0.000001);
      }
    }
    return this.lotSteps.get(symbol);
  }

  async buy(symbol, qty, price) {
    const roundedQty = roundToStep(qty, await this._step(symbol));
    if (roundedQty <= 0) {
      log.warn(`${symbol}: yuvarlama sonrasi miktar sifir - emir gonderilmedi.`);
      return null;
    }
    const res = await placeMarketOrder(symbol, "BUY", roundedQty);
    log.debug(`Emir yaniti: ${JSON.stringify(res)}`);
    // MARKET emri aninda dolar; borsa ortalama dolum fiyati donerse onu kullan
    const fillPrice = parseFloat(res?.data?.price) || price;
    const fillQty = parseFloat(res?.data?.executedQty) || roundedQty;
    return { qty: fillQty, price: fillPrice, fee: fillQty * fillPrice * (this.cfg.feePct / 100) };
  }

  async sell(symbol, qty, price) {
    const roundedQty = roundToStep(qty, await this._step(symbol));
    if (roundedQty <= 0) return null;
    const res = await placeMarketOrder(symbol, "SELL", roundedQty);
    log.debug(`Emir yaniti: ${JSON.stringify(res)}`);
    const fillPrice = parseFloat(res?.data?.price) || price;
    const fillQty = parseFloat(res?.data?.executedQty) || roundedQty;
    return { qty: fillQty, price: fillPrice, fee: fillQty * fillPrice * (this.cfg.feePct / 100) };
  }
}

export function createBroker(cfg = config) {
  return cfg.tradeMode === "live" ? new LiveBroker(cfg) : new PaperBroker(cfg);
}
