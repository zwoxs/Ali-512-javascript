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

export async function notify(text) {
  await Promise.all([sendTelegram(text), sendDiscord(text)]);
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
