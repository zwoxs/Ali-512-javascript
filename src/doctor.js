// Sistem tanilamasi: npm run doctor
// Canliya gecmeden once ortamin ve yapilandirmanin saglikli oldugunu dogrular.
// Cikis kodu: 0 = tum kontroller temiz, 1 = en az bir sorun var.

import { existsSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import path from "node:path";
import { config, validateConfig } from "./config.js";
import { getStrategy } from "./strategies/index.js";

const results = [];
const ok = (name, detail = "") => results.push({ pass: true, name, detail });
const fail = (name, detail = "") => results.push({ pass: false, name, detail });
const warn = (name, detail = "") => results.push({ pass: true, warn: true, name, detail });

async function main() {
  console.log("\n🩺 Coin Bot Tanilamasi\n");

  // 1) Node surumu ve WebSocket
  const major = parseInt(process.versions.node.split(".")[0], 10);
  if (major >= 18) ok("Node.js surumu", `v${process.versions.node}`);
  else fail("Node.js surumu", `v${process.versions.node} - en az 18 gerekli`);
  if (typeof WebSocket !== "undefined") ok("WebSocket destegi", "gercek zamanli akis kullanilabilir");
  else warn("WebSocket destegi", "Node < 21: REST yoklama moduna dusulecek (calisir ama gecikmeli)");

  // 2) Yapilandirma
  const errors = validateConfig();
  if (errors.length === 0) ok("Yapilandirma (.env)", `mod=${config.tradeMode}, ${config.symbols.length} sembol`);
  else errors.forEach((e) => fail("Yapilandirma", e));
  try {
    for (const s of config.symbols) {
      getStrategy(config.symbolStrategies[s] || config.strategy).warmup(config);
    }
    ok("Strateji cozumlemesi", config.symbols.map((s) => `${s}=${config.symbolStrategies[s] || config.strategy}`).join(", "));
  } catch (err) {
    fail("Strateji cozumlemesi", err.message);
  }

  // 3) Dizin yazma izinleri
  for (const dir of [config.dataDir, config.logDir]) {
    try {
      if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
      const probe = path.join(dir, ".doctor-probe");
      writeFileSync(probe, "ok");
      rmSync(probe);
      ok(`Yazma izni: ${path.basename(dir)}/`);
    } catch (err) {
      fail(`Yazma izni: ${path.basename(dir)}/`, err.message);
    }
  }

  // 4) Piyasa API erisimi + saat sapmasi
  try {
    const t0 = Date.now();
    const res = await fetch(`${config.marketBaseUrl}/api/v3/time`, { signal: AbortSignal.timeout(10_000) });
    const { serverTime } = await res.json();
    const latency = Date.now() - t0;
    const drift = Math.abs(serverTime - (t0 + latency / 2));
    ok("Piyasa API erisimi", `${config.marketBaseUrl} (${latency}ms)`);
    if (drift < 1000) ok("Saat senkronizasyonu", `sapma ~${drift}ms`);
    else warn("Saat senkronizasyonu", `sapma ~${drift}ms - bot otomatik duzeltir ama sistem saatinizi kontrol edin (NTP)`);
  } catch (err) {
    fail("Piyasa API erisimi", `${config.marketBaseUrl}: ${err.message}`);
  }

  // 5) Sembol dogrulamasi
  for (const symbol of config.symbols) {
    try {
      const res = await fetch(
        `${config.marketBaseUrl}/api/v3/ticker/price?symbol=${symbol}`,
        { signal: AbortSignal.timeout(10_000) }
      );
      if (res.ok) {
        const { price } = await res.json();
        ok(`Sembol: ${symbol}`, `guncel fiyat ${price}`);
      } else {
        fail(`Sembol: ${symbol}`, `HTTP ${res.status} - sembol adini kontrol edin`);
      }
    } catch (err) {
      fail(`Sembol: ${symbol}`, err.message);
    }
  }

  // 6) Islem API'si (sadece live modda anlamli)
  if (config.tradeMode === "live") {
    if (!config.apiKey || !config.apiSecret) {
      fail("Binance TR API anahtarlari", "live mod icin zorunlu, .env'de eksik");
    } else {
      try {
        const { getAccount } = await import("./exchange/binanceTr.js");
        await getAccount();
        ok("Binance TR hesap erisimi", "API anahtarlari calisiyor");
      } catch (err) {
        fail("Binance TR hesap erisimi", err.message);
      }
    }
  } else {
    warn("Binance TR hesap erisimi", `mod=${config.tradeMode}: kontrol atlandi (live degil)`);
  }

  // 7) Bildirim kanallari
  if (config.telegramToken && config.telegramChatId) ok("Telegram", "yapilandirilmis");
  else warn("Telegram", "yapilandirilmamis (istege bagli)");
  if (config.discordWebhookUrl) ok("Discord", "yapilandirilmis");
  else warn("Discord", "yapilandirilmamis (istege bagli)");

  // 8) Haber filtresi
  if (!config.newsFilter) {
    warn("Haber filtresi", "kapali (istege bagli - NEWS_FILTER=true ile acin)");
  } else {
    try {
      const { getSentiment } = await import("./core/newsSentiment.js");
      const s = await getSentiment(config.symbols[0], config);
      if (s.error) fail("Haber filtresi", `kaynak erisilemedi: ${s.error}`);
      else ok("Haber filtresi", `${config.newsSource} calisiyor (${s.count} baslik, etiket: ${s.label})`);
    } catch (err) {
      fail("Haber filtresi", err.message);
    }
  }

  // Ozet
  console.log("");
  for (const r of results) {
    const icon = !r.pass ? "✗" : r.warn ? "△" : "✓";
    console.log(` ${icon} ${r.name}${r.detail ? ` — ${r.detail}` : ""}`);
  }
  const failures = results.filter((r) => !r.pass);
  console.log(
    `\n${failures.length === 0 ? "✅ Tum kontroller temiz." : `❌ ${failures.length} sorun bulundu - yukaridaki ✗ satirlarini duzeltin.`}\n`
  );
  process.exit(failures.length === 0 ? 0 : 1);
}

main().catch((err) => {
  console.error("Tanilamada beklenmeyen hata:", err.message);
  process.exit(1);
});
