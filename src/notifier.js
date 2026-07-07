import { config } from "./config.js";
import { log } from "./logger.js";

/**
 * Telegram bildirimi (istege bagli).
 * TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID ayarliysa islem/uyari mesajlari gonderir.
 * Bildirim hatasi botu ASLA durdurmaz - sadece loglanir.
 */
export async function notify(text) {
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

export function formatTradeMessage(record) {
  const emoji = record.side === "AL" ? "🟢" : record.side === "SAT" ? "🔴" : "⚠️";
  const pnlLine = record.pnl != null ? `\nK/Z: <b>${record.pnl.toFixed(2)} TRY</b>` : "";
  return (
    `${emoji} <b>${record.side}</b> ${record.symbol} [${record.mode}]\n` +
    `Miktar: ${record.qty}\nFiyat: ${record.price}${pnlLine}\n${record.reason}`
  );
}
