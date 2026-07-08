import { config } from "../config.js";
import { log } from "../logger.js";
import { placeMarketOrder, makeClientOrderId } from "./binanceTr.js";
import { fetchSymbolFilters } from "./market.js";
import { validateOrder } from "./filters.js";

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
    this.filters = new Map();
  }

  async _getFilters(symbol) {
    if (!this.filters.has(symbol)) {
      try {
        this.filters.set(symbol, await fetchSymbolFilters(symbol));
      } catch (err) {
        log.warn(`${symbol} borsa filtreleri alinamadi (${err.message}); guvenli varsayilanlar.`);
        this.filters.set(symbol, { stepSize: 0.000001, minQty: 0, minNotional: 0, tickSize: 0 });
      }
    }
    return this.filters.get(symbol);
  }

  /**
   * Emri gonderir. Her emir benzersiz clientOrderId tasir (borsada izlenebilir
   * + tekillestirme icin). ORDER_RETRY acikken ag hatasinda AYNI kimlikle bir
   * kez daha dener; kapaliyken (varsayilan) hata dogrudan yukari verilir -
   * boylece belirsiz durumda cift dolum riski alinmaz, mutabakat devreye girer.
   */
  async _send(symbol, side, roundedQty, price) {
    const clientOrderId = makeClientOrderId(symbol, side);
    let res;
    try {
      res = await placeMarketOrder(symbol, side, roundedQty, clientOrderId);
    } catch (err) {
      if (!this.cfg.orderRetry) {
        log.error(
          `${symbol} ${side} emri BASARISIZ (${err.message}). ORDER_RETRY kapali - ` +
          `emir tekrarlanmadi. Borsada gerceklesmis OLABILIR; mutabakat kontrol edecek.`
        );
        throw err;
      }
      log.warn(`${symbol} ${side} emri hata verdi (${err.message}) - ayni kimlikle 1 kez daha deneniyor.`);
      res = await placeMarketOrder(symbol, side, roundedQty, clientOrderId);
    }
    log.debug(`Emir yaniti (${clientOrderId}): ${JSON.stringify(res)}`);
    const fillPrice = parseFloat(res?.data?.price) || price;
    const fillQty = parseFloat(res?.data?.executedQty) || roundedQty;
    return { qty: fillQty, price: fillPrice, fee: fillQty * fillPrice * (this.cfg.feePct / 100), clientOrderId };
  }

  async buy(symbol, qty, price) {
    const filters = await this._getFilters(symbol);
    const v = validateOrder({ qty, price, filters });
    if (!v.ok) {
      log.warn(`${symbol} ALIM borsa filtresine takildi: ${v.reason} - emir gonderilmedi.`);
      return null;
    }
    return this._send(symbol, "BUY", v.qty, price);
  }

  async sell(symbol, qty, price) {
    const filters = await this._getFilters(symbol);
    // Satista MIN_NOTIONAL ihlali olsa bile pozisyondan CIKMAK onceliklidir:
    // sadece adim yuvarlamasi uygulanir, minNotional/minQty veto edilmez.
    const roundedQty = roundToStep(qty, filters.stepSize);
    if (roundedQty <= 0) {
      log.warn(`${symbol}: yuvarlama sonrasi satis miktari sifir - emir gonderilmedi.`);
      return null;
    }
    return this._send(symbol, "SELL", roundedQty, price);
  }
}

export function createBroker(cfg = config) {
  return cfg.tradeMode === "live" ? new LiveBroker(cfg) : new PaperBroker(cfg);
}
