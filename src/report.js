// Islem gunlugunden (logs/trades.jsonl) bagimsiz HTML performans raporu uretir.
// Kullanim: npm run report  ->  logs/report.html
// Rapor tek dosyadir; tarayicida acilir, sunucu gerektirmez.

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import path from "node:path";
import { config } from "./config.js";

const tradesPath = path.join(config.logDir, "trades.jsonl");

function loadTrades() {
  if (!existsSync(tradesPath)) {
    console.error(`Islem gunlugu bulunamadi: ${tradesPath}`);
    console.error("Once botu calistirin (paper/live) - islemler bu dosyaya yazilir.");
    process.exit(1);
  }
  return readFileSync(tradesPath, "utf8")
    .split("\n")
    .filter(Boolean)
    .map((line) => { try { return JSON.parse(line); } catch { return null; } })
    .filter(Boolean);
}

function aggregate(records) {
  const closed = records.filter((r) => r.pnl != null);
  const bySymbol = {};
  const byStrategy = {};
  let cumulative = 0;
  const cumSeries = [];
  const daily = {};

  for (const t of closed) {
    cumulative += t.pnl;
    cumSeries.push({ ts: t.ts, pnl: cumulative });
    const day = (t.ts || "").slice(0, 10);
    daily[day] = (daily[day] || 0) + t.pnl;
    const s = (bySymbol[t.symbol] ||= { trades: 0, wins: 0, pnl: 0 });
    s.trades++;
    if (t.pnl > 0) s.wins++;
    s.pnl += t.pnl;
    const st = (byStrategy[t.strategy || "bilinmiyor"] ||= { trades: 0, wins: 0, pnl: 0 });
    st.trades++;
    if (t.pnl > 0) st.wins++;
    st.pnl += t.pnl;
  }

  const wins = closed.filter((t) => t.pnl > 0);
  return {
    generatedAt: new Date().toISOString(),
    totalRecords: records.length,
    closedTrades: closed.length,
    winCount: wins.length,
    winRatePct: closed.length ? (wins.length / closed.length) * 100 : 0,
    totalPnl: cumulative,
    best: closed.length ? Math.max(...closed.map((t) => t.pnl)) : 0,
    worst: closed.length ? Math.min(...closed.map((t) => t.pnl)) : 0,
    bySymbol,
    byStrategy,
    cumSeries,
    daily: Object.entries(daily).sort(([a], [b]) => a.localeCompare(b)),
    recent: closed.slice(-50).reverse(),
  };
}

function render(data) {
  return `<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><title>Coin Bot Performans Raporu</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box;margin:0}
body{font:14px/1.5 system-ui,sans-serif;background:#0d1117;color:#e6edf3;padding:24px;max-width:1100px;margin:auto}
h1{font-size:20px;margin-bottom:4px}h2{font-size:15px;margin:20px 0 8px}
.sub{color:#8b949e;font-size:12px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:8px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px}
.card .l{color:#8b949e;font-size:11px;text-transform:uppercase}.card .v{font-size:20px;font-weight:600;margin-top:4px}
.pos{color:#3fb950}.neg{color:#f85149}
canvas{width:100%;height:200px;background:#161b22;border:1px solid #30363d;border-radius:8px}
table{width:100%;border-collapse:collapse;background:#161b22;border:1px solid #30363d;border-radius:8px;overflow:hidden}
th,td{padding:7px 12px;text-align:left;border-bottom:1px solid #21262d;font-size:13px}
th{color:#8b949e;font-size:11px;text-transform:uppercase}
</style></head><body>
<h1>📈 Coin Bot Performans Raporu</h1>
<div class="sub">Olusturulma: ${data.generatedAt} | Kaynak: logs/trades.jsonl (${data.totalRecords} kayit)</div>
<div class="grid">
  <div class="card"><div class="l">Toplam K/Z</div><div class="v ${data.totalPnl >= 0 ? "pos" : "neg"}">${data.totalPnl.toFixed(2)} TRY</div></div>
  <div class="card"><div class="l">Kapanan Islem</div><div class="v">${data.closedTrades}</div></div>
  <div class="card"><div class="l">Kazanma Orani</div><div class="v">%${data.winRatePct.toFixed(1)}</div></div>
  <div class="card"><div class="l">En Iyi / En Kotu</div><div class="v"><span class="pos">+${data.best.toFixed(0)}</span> / <span class="neg">${data.worst.toFixed(0)}</span></div></div>
</div>
<h2>Kumulatif Gerceklesen K/Z</h2><canvas id="cum" width="2000" height="400"></canvas>
<h2>Gunluk K/Z</h2><canvas id="daily" width="2000" height="400"></canvas>
<h2>Sembol Bazinda</h2>
<table><thead><tr><th>Sembol</th><th>Islem</th><th>Kazanan</th><th>K/Z (TRY)</th></tr></thead><tbody>
${Object.entries(data.bySymbol).map(([s, v]) =>
  `<tr><td>${s}</td><td>${v.trades}</td><td>${v.wins}</td><td class="${v.pnl >= 0 ? "pos" : "neg"}">${v.pnl.toFixed(2)}</td></tr>`).join("")}
</tbody></table>
<h2>Strateji Bazinda</h2>
<table><thead><tr><th>Strateji</th><th>Islem</th><th>Kazanan</th><th>K/Z (TRY)</th></tr></thead><tbody>
${Object.entries(data.byStrategy).map(([s, v]) =>
  `<tr><td>${s}</td><td>${v.trades}</td><td>${v.wins}</td><td class="${v.pnl >= 0 ? "pos" : "neg"}">${v.pnl.toFixed(2)}</td></tr>`).join("")}
</tbody></table>
<h2>Son Islemler</h2>
<table><thead><tr><th>Zaman</th><th>Yon</th><th>Sembol</th><th>Miktar</th><th>Fiyat</th><th>K/Z</th><th>Neden</th></tr></thead><tbody>
${data.recent.map((t) =>
  `<tr><td>${(t.ts || "").replace("T", " ").slice(0, 19)}</td><td>${t.side}</td><td>${t.symbol}</td><td>${t.qty}</td><td>${t.price}</td><td class="${t.pnl >= 0 ? "pos" : "neg"}">${t.pnl.toFixed(2)}</td><td style="color:#8b949e">${t.reason || ""}</td></tr>`).join("")}
</tbody></table>
<script>
const CUM = ${JSON.stringify(data.cumSeries.map((p) => p.pnl))};
const DAILY = ${JSON.stringify(data.daily)};
function line(id, vals) {
  const c = document.getElementById(id), ctx = c.getContext("2d");
  if (vals.length < 2) return;
  const min = Math.min(...vals, 0), max = Math.max(...vals, 0), pad = (max - min) * .1 || 1;
  const x = i => i / (vals.length - 1) * (c.width - 20) + 10;
  const y = v => c.height - 20 - (v - (min - pad)) / ((max + pad) - (min - pad)) * (c.height - 40);
  ctx.strokeStyle = "#30363d"; ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(10, y(0)); ctx.lineTo(c.width - 10, y(0)); ctx.stroke(); ctx.setLineDash([]);
  ctx.strokeStyle = vals[vals.length - 1] >= 0 ? "#3fb950" : "#f85149"; ctx.lineWidth = 2.5;
  ctx.beginPath(); vals.forEach((v, i) => i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))); ctx.stroke();
}
function bars(id, entries) {
  const c = document.getElementById(id), ctx = c.getContext("2d");
  if (!entries.length) return;
  const vals = entries.map(e => e[1]);
  const min = Math.min(...vals, 0), max = Math.max(...vals, 0), pad = (max - min) * .1 || 1;
  const w = (c.width - 20) / entries.length;
  const y = v => c.height - 20 - (v - (min - pad)) / ((max + pad) - (min - pad)) * (c.height - 40);
  entries.forEach(([d, v], i) => {
    ctx.fillStyle = v >= 0 ? "#3fb950" : "#f85149";
    const top = Math.min(y(v), y(0));
    ctx.fillRect(10 + i * w + 1, top, Math.max(w - 2, 1), Math.max(Math.abs(y(v) - y(0)), 1));
  });
}
line("cum", CUM); bars("daily", DAILY);
</script></body></html>`;
}

const records = loadTrades();
const data = aggregate(records);
if (data.closedTrades === 0) {
  console.log("Henuz kapanan islem yok - rapor icin en az bir SAT islemi gerekir.");
  process.exit(0);
}
const outPath = path.join(config.logDir, "report.html");
writeFileSync(outPath, render(data));
console.log(`Rapor olusturuldu: ${outPath}`);
console.log(`Toplam K/Z: ${data.totalPnl.toFixed(2)} TRY | Islem: ${data.closedTrades} | Kazanma: %${data.winRatePct.toFixed(1)}`);
