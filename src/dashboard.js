import http from "node:http";
import { log } from "./logger.js";

/**
 * Yerlesik izleme paneli - harici bagimlilik yok.
 * Sadece 127.0.0.1'e baglanir (disariya acmak icin ters proxy kullanin).
 * GET /            -> tek dosyalik HTML panel
 * GET /api/status  -> anlik durum JSON'u
 */

const PAGE = /* html */ `<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Coin Bot Panel</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; margin: 0; }
  body { font: 14px/1.5 system-ui, sans-serif; background: #0d1117; color: #e6edf3; padding: 24px; }
  h1 { font-size: 18px; margin-bottom: 4px; }
  .sub { color: #8b949e; font-size: 12px; margin-bottom: 20px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px; }
  .card .label { color: #8b949e; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }
  .card .value { font-size: 20px; font-weight: 600; margin-top: 4px; }
  .pos { color: #3fb950; } .neg { color: #f85149; }
  canvas { width: 100%; height: 180px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; margin-bottom: 20px; }
  table { width: 100%; border-collapse: collapse; background: #161b22; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; margin-bottom: 20px; }
  th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #21262d; font-size: 13px; }
  th { color: #8b949e; font-weight: 500; font-size: 11px; text-transform: uppercase; }
  .warn { background: #3d1e00; border: 1px solid #9e6a03; border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; display: none; }
</style>
</head>
<body>
<h1>🤖 Binance TR Coin Bot</h1>
<div class="sub" id="sub">yukleniyor...</div>
<div class="warn" id="warn"></div>
<div class="grid" id="cards"></div>
<h1 style="font-size:15px;margin-bottom:8px">Ozsermaye</h1>
<canvas id="chart" width="1200" height="360"></canvas>
<h1 style="font-size:15px;margin-bottom:8px">Fiyat Grafigi <select id="symSelect" style="background:#161b22;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:2px 8px;margin-left:8px"></select> <span style="color:#8b949e;font-size:12px" id="sigInfo"></span></h1>
<canvas id="candleChart" width="1200" height="400"></canvas>
<h1 style="font-size:15px;margin-bottom:8px">Acik Pozisyonlar</h1>
<table><thead><tr><th>Sembol</th><th>Miktar</th><th>Giris</th><th>Guncel</th><th>K/Z %</th></tr></thead><tbody id="positions"></tbody></table>
<h1 style="font-size:15px;margin-bottom:8px">Son Islemler</h1>
<table><thead><tr><th>Zaman</th><th>Sembol</th><th>Giris</th><th>Cikis</th><th>K/Z</th></tr></thead><tbody id="trades"></tbody></table>
<script>
const fmt = (n, d=2) => Number(n).toLocaleString("tr-TR", {maximumFractionDigits: d, minimumFractionDigits: d});
async function refresh() {
  try {
    const s = await (await fetch("/api/status")).json();
    document.getElementById("sub").textContent =
      s.mode.toUpperCase() + " | " + s.symbols.join(", ") + " @ " + s.interval + " | " + s.strategy + " | guncelleme: " + new Date().toLocaleTimeString("tr-TR");
    const ret = ((s.equity - s.initialBalance) / s.initialBalance) * 100;
    document.getElementById("cards").innerHTML = [
      ["Toplam Deger", fmt(s.equity) + " TRY", ret >= 0 ? "pos" : "neg"],
      ["Getiri", (ret >= 0 ? "+" : "") + fmt(ret) + "%", ret >= 0 ? "pos" : "neg"],
      ["Nakit", fmt(s.quote) + " TRY", ""],
      ["Islem (Kazanan)", s.trades + " (" + s.wins + ")", ""],
      ["Gerceklesen K/Z", fmt(s.realizedPnl) + " TRY", s.realizedPnl >= 0 ? "pos" : "neg"],
    ].map(([l, v, c]) => '<div class="card"><div class="label">' + l + '</div><div class="value ' + c + '">' + v + "</div></div>").join("");
    const warn = document.getElementById("warn");
    if (s.risk.dailyLimitHit) { warn.style.display = "block"; warn.textContent = "⚠️ Gunluk zarar limiti asildi - bugun yeni pozisyon acilmayacak."; }
    else if (s.risk.cooldownUntil > Date.now()) { warn.style.display = "block"; warn.textContent = "⏸️ Sogurma suresi aktif: " + new Date(s.risk.cooldownUntil).toLocaleTimeString("tr-TR") + " kadar yeni islem yok."; }
    else warn.style.display = "none";
    document.getElementById("positions").innerHTML = s.positions.length
      ? s.positions.map(p => { const chg = ((p.currentPrice - p.entryPrice) / p.entryPrice) * 100;
          return "<tr><td>" + p.symbol + "</td><td>" + p.qty + "</td><td>" + fmt(p.entryPrice, 4) + "</td><td>" + fmt(p.currentPrice, 4) + '</td><td class="' + (chg >= 0 ? "pos" : "neg") + '">' + fmt(chg) + "%</td></tr>"; }).join("")
      : '<tr><td colspan="5" style="color:#8b949e">acik pozisyon yok</td></tr>';
    document.getElementById("trades").innerHTML = s.recentTrades.length
      ? s.recentTrades.map(t => "<tr><td>" + new Date(t.closedAt).toLocaleString("tr-TR") + "</td><td>" + t.symbol + "</td><td>" + fmt(t.entryPrice, 4) + "</td><td>" + fmt(t.exitPrice, 4) + '</td><td class="' + (t.pnl >= 0 ? "pos" : "neg") + '">' + fmt(t.pnl) + " TRY</td></tr>").join("")
      : '<tr><td colspan="5" style="color:#8b949e">henuz islem yok</td></tr>';
    drawChart(s.equityHistory, s.initialBalance);
    updateSymbolSelect(s.symbols);
    const sym = document.getElementById("symSelect").value || s.symbols[0];
    const sig = s.signals?.[sym];
    document.getElementById("sigInfo").textContent = sig ? "son sinyal: " + sig.signal + " — " + sig.reason : "";
    drawCandles(s.charts?.[sym] || [], (s.markers || []).filter(m => m.symbol === sym));
  } catch (e) { document.getElementById("sub").textContent = "baglanti hatasi: " + e.message; }
}
function updateSymbolSelect(symbols) {
  const sel = document.getElementById("symSelect");
  if (sel.options.length === symbols.length) return;
  sel.innerHTML = symbols.map(s => '<option value="' + s + '">' + s + "</option>").join("");
}
document.addEventListener("change", e => { if (e.target.id === "symSelect") refresh(); });
function drawCandles(candles, markers) {
  const c = document.getElementById("candleChart"), ctx = c.getContext("2d");
  ctx.clearRect(0, 0, c.width, c.height);
  if (candles.length < 2) return;
  const lows = candles.map(k => k.l), highs = candles.map(k => k.h);
  const min = Math.min(...lows), max = Math.max(...highs), pad = (max - min) * 0.05 || 1;
  const w = (c.width - 20) / candles.length;
  const x = i => 10 + i * w + w / 2;
  const y = v => c.height - 20 - ((v - (min - pad)) / ((max + pad) - (min - pad))) * (c.height - 40);
  candles.forEach((k, i) => {
    const up = k.c >= k.o;
    ctx.strokeStyle = ctx.fillStyle = up ? "#3fb950" : "#f85149";
    ctx.beginPath(); ctx.moveTo(x(i), y(k.h)); ctx.lineTo(x(i), y(k.l)); ctx.stroke();
    const bh = Math.max(1, Math.abs(y(k.o) - y(k.c)));
    ctx.fillRect(x(i) - w * 0.35, Math.min(y(k.o), y(k.c)), w * 0.7, bh);
  });
  // Islem isaretleri: giris (yukari ucgen) / cikis (asagi ucgen)
  const t0 = candles[0].t, t1 = candles[candles.length - 1].t;
  const tx = t => 10 + ((t - t0) / (t1 - t0)) * (c.width - 20);
  const tri = (px, py, up, color) => {
    ctx.fillStyle = color; ctx.beginPath();
    ctx.moveTo(px, py); ctx.lineTo(px - 6, py + (up ? 10 : -10)); ctx.lineTo(px + 6, py + (up ? 10 : -10));
    ctx.closePath(); ctx.fill();
  };
  for (const m of markers) {
    if (m.openedAt >= t0 && m.openedAt <= t1) tri(tx(m.openedAt), y(m.entryPrice) + 4, true, "#3fb950");
    if (m.closedAt >= t0 && m.closedAt <= t1) tri(tx(m.closedAt), y(m.exitPrice) - 4, false, m.pnl >= 0 ? "#d29922" : "#f85149");
  }
}
function drawChart(hist, base) {
  const c = document.getElementById("chart"), ctx = c.getContext("2d");
  ctx.clearRect(0, 0, c.width, c.height);
  if (hist.length < 2) return;
  const vals = hist.map(h => h.equity);
  const min = Math.min(...vals, base), max = Math.max(...vals, base), pad = (max - min) * 0.1 || 1;
  const x = i => (i / (hist.length - 1)) * (c.width - 20) + 10;
  const y = v => c.height - 20 - ((v - (min - pad)) / ((max + pad) - (min - pad))) * (c.height - 40);
  ctx.strokeStyle = "#30363d"; ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(10, y(base)); ctx.lineTo(c.width - 10, y(base)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.strokeStyle = vals[vals.length - 1] >= base ? "#3fb950" : "#f85149"; ctx.lineWidth = 2;
  ctx.beginPath();
  hist.forEach((h, i) => i === 0 ? ctx.moveTo(x(i), y(h.equity)) : ctx.lineTo(x(i), y(h.equity)));
  ctx.stroke();
}
refresh(); setInterval(refresh, 5000);
</script>
</body>
</html>`;

export function startDashboard(port, getStatus, getHealth = null) {
  if (!port) return null;
  const server = http.createServer((req, res) => {
    if (req.url === "/api/status") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(getStatus()));
    } else if (req.url === "/api/health") {
      // Izleme sistemleri (uptime kontrolu, k8s liveness vb.) icin
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(getHealth ? getHealth() : { status: "ok" }));
    } else {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(PAGE);
    }
  });
  server.on("error", (err) => log.error(`Panel sunucusu hatasi: ${err.message}`));
  server.listen(port, "127.0.0.1", () =>
    log.info(`Izleme paneli: http://127.0.0.1:${port}`)
  );
  return server;
}
