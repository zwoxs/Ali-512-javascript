import { config } from "./config.js";
import { log } from "./logger.js";

/**
 * Bildirim katmani: Telegram ve/veya Discord webhook (istege bagli).
 * Yapilandirilan tum kanallara paralel gonderir.
 * Bildirim hatasi botu ASLA durdurmaz - sadece loglanir.
 */

async function sendTelegram(text) {
  if (!config.telegramToken || !config.telegramChatId) return;
  try {
    const res = await fetch(`https://api.telegram.org/bot${config.telegramToken}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: config.telegramChatId, text, parse_mode: "HTML" }),
      signal: AbortSignal.timeout(10_000),
    });
    if (!res.ok) log.warn(`Telegram bildirimi basarisiz: HTTP ${res.status}`);
  } catch (err) {
    log.warn(`Telegram bildirimi basarisiz: ${err.message}`);
  }
}

async function sendDiscord(text) {
  if (!config.discordWebhookUrl) return;
  try {
    const res = await fetch(config.discordWebhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // Telegram HTML etiketlerini duz metne cevir
      body: JSON.stringify({ content: text.replace(/<[^>]+>/g, "") }),
      signal: AbortSignal.timeout(10_000),
    });
    if (!res.ok && res.status !== 204) log.warn(`Discord bildirimi basarisiz: HTTP ${res.status}`);
  } catch (err) {
    log.warn(`Discord bildirimi basarisiz: ${err.message}`);
  }
}

// Bildirim kisitlama: kritik olmayan mesajlar arasi minimum aralik.
// Ag/veri dalgalanmasinda tekrarlayan uyarilarin telefonu bombardimana
// tutmasini onler. Kritik bildirimler (islemler, acil fren) her zaman gecer.
let lastThrottledAt = 0;

/**
 * @param {string} text
 * @param {object} [opts]
 * @param {boolean} [opts.critical=true] - false ise NOTIFY_THROTTLE_SEC uygulanir
 * @param {function} [opts.now] - test icin saat enjeksiyonu
 * @returns {Promise<boolean>} gonderildi mi
 */
export async function notify(text, { critical = true, now = () => Date.now() } = {}) {
  if (!critical && config.notifyThrottleSec > 0) {
    if (now() - lastThrottledAt < config.notifyThrottleSec * 1000) return false;
    lastThrottledAt = now();
  }
  await Promise.all([sendTelegram(text), sendDiscord(text)]);
  return true;
}

/** Test yardimcisi: throttle durumunu sifirlar. */
export function _resetThrottle() {
  lastThrottledAt = 0;
}

const SIDE_EMOJI = {
  "AL": "🟢", "SAT": "🔴", "KISMI-SAT": "🟡",
  "KADEME-AL": "🟩", "SINYAL-AL": "📈", "SINYAL-SAT": "📉", "UYARI": "⚠️",
};

export function formatTradeMessage(record) {
  const emoji = SIDE_EMOJI[record.side] || "ℹ️";
  const pnlLine = record.pnl != null ? `\nK/Z: <b>${record.pnl.toFixed(2)} TRY</b>` : "";
  const qtyLine = record.qty ? `\nMiktar: ${record.qty}` : "";
  return (
    `${emoji} <b>${record.side}</b> ${record.symbol} [${record.mode}]${qtyLine}\n` +
    `Fiyat: ${record.price}${pnlLine}\n${record.reason}`
  );
}
