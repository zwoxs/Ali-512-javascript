"""Companion Web Sunucusu — telefon/saat/masaüstü için uyarlanır arayüz.

JARVIS'in masaüstü HUD'u fiziksel olarak bir telefona/saate taşınamaz
(ayrı işletim sistemleri). Bunun yerine bu sunucu, yerel ağda cihaza göre
kendini uyarlayan bir web arayüzü yayınlar. Telefon/saat kendi tarayıcısından
bu adresi açar.

"Bağlanılan cihaza geçiş": sunucu bir 'active_mode' tutar (desktop/phone).
JARVIS bir telefona bağlanınca active_mode='phone' olur; arayüzü açık olan ve
kendi modunu zorlamamış tüm istemciler otomatik olarak telefon düzenine geçer.

Bağımlılık gerektirmez (yalnızca stdlib http.server).
"""
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime


def _lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


class CompanionServer:
    def __init__(self, orchestrator, settings=None, host="0.0.0.0", port=8770):
        self.orch = orchestrator
        self.settings = settings or {}
        self.host = host
        self.port = port
        self.active_mode = "desktop"      # desktop / phone
        self.active_device = None
        self._httpd = None
        self._thread = None
        self.running = False

    # ---------- yaşam döngüsü ----------
    def start(self) -> bool:
        if self.running:
            return True
        try:
            server = self  # closure
            handler = _make_handler(server)
            self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        except OSError:
            return False
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        self.running = True
        return True

    def stop(self):
        if self._httpd:
            try:
                self._httpd.shutdown()
            except Exception:
                pass
        self.running = False

    def local_url(self) -> str:
        return f"http://{_lan_ip()}:{self.port}"

    # ---------- mod (aktif cihaz düzeni) ----------
    def set_mode(self, mode: str, device_name: str = None) -> str:
        mode = (mode or "desktop").lower()
        if mode not in ("desktop", "phone"):
            mode = "desktop"
        self.active_mode = mode
        self.active_device = device_name
        labels = {"desktop": "masaüstü", "phone": "telefon"}
        return f"Arayüz {labels[mode]} moduna geçirildi, Efendim."

    def status(self) -> dict:
        now = datetime.now()
        return {
            "assistant_name": self.settings.get("assistant_name", "JARVIS"),
            "mode": self.active_mode,
            "device": self.active_device,
            "time": now.strftime("%H:%M:%S"),
            "date": now.strftime("%d.%m.%Y"),
        }


# =====================================================================
#  HTTP İSTEK İŞLEYİCİ
# =====================================================================
def _make_handler(server: "CompanionServer"):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # sessiz

        def _send(self, code, content, ctype="text/html; charset=utf-8"):
            data = content.encode("utf-8") if isinstance(content, str) else content
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                self._send(200, _PAGE_HTML)
            elif path == "/api/status":
                self._send(200, json.dumps(server.status()), "application/json")
            elif path == "/manifest.json":
                self._send(200, _MANIFEST, "application/json")
            else:
                self._send(404, "Not found")

        def do_POST(self):
            if self.path.split("?")[0] == "/api/command":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                try:
                    text = json.loads(body).get("text", "")
                except json.JSONDecodeError:
                    text = ""
                resp = server.orch.handle(text) if text else ""
                for marker in ("__EXIT__", "__CLEAR__"):
                    if resp == marker:
                        resp = ""
                self._send(200, json.dumps({"response": resp}), "application/json")
            else:
                self._send(404, "Not found")

    return Handler


# =====================================================================
#  MANIFEST (PWA)
# =====================================================================
_MANIFEST = json.dumps({
    "name": "JARVIS Companion",
    "short_name": "JARVIS",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#05070a",
    "theme_color": "#00e5ff",
})


# =====================================================================
#  UYARLANIR WEB ARAYÜZÜ (tek dosya, self-contained)
# =====================================================================
_PAGE_HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="theme-color" content="#00e5ff">
<link rel="manifest" href="/manifest.json">
<title>JARVIS Companion</title>
<style>
  :root{ --acc:#00e5ff; --bg:#05070a; --bg2:#0b0f14; --bg3:#11161d; --fg:#c8d6e5; --dim:#5a6b7b; }
  *{ box-sizing:border-box; margin:0; padding:0; -webkit-tap-highlight-color:transparent; }
  html,body{ overflow-x:hidden; }
  body{ background:var(--bg); color:var(--fg); font-family:Consolas,'Segoe UI',monospace;
        min-height:100vh; width:100%; display:flex; flex-direction:column; }
  .badge{ position:fixed; top:8px; right:8px; font-size:11px; color:var(--acc);
          border:1px solid var(--acc); border-radius:12px; padding:2px 10px; opacity:.7; }
  header{ padding:16px; text-align:center; }
  header h1{ color:var(--acc); font-size:22px; letter-spacing:2px; }
  header .sub{ color:var(--dim); font-size:12px; margin-top:4px; }
  .clock{ color:var(--acc); font-size:40px; font-weight:bold; text-align:center; margin:8px 0; }
  .date{ color:var(--dim); text-align:center; font-size:13px; }
  #chat{ flex:1; overflow-y:auto; padding:12px 16px; display:flex; flex-direction:column; gap:8px; }
  .msg{ padding:10px 14px; border-radius:14px; max-width:85%; font-size:15px; line-height:1.4;
        white-space:pre-wrap; word-break:break-word; }
  .me{ align-self:flex-end; background:var(--bg3); color:#7fdbff; }
  .jv{ align-self:flex-start; background:var(--bg2); color:var(--acc); border:1px solid #16323c; }
  .quick{ display:flex; flex-wrap:wrap; gap:8px; padding:8px 16px; }
  .quick button{ background:var(--bg3); color:var(--fg); border:1px solid #16323c; border-radius:20px;
        padding:8px 14px; font-size:13px; font-family:inherit; cursor:pointer; }
  .quick button:active{ background:var(--acc); color:var(--bg); }
  .bar{ display:flex; gap:8px; padding:12px 16px; background:var(--bg2); }
  .bar input{ flex:1; min-width:0; background:var(--bg3); border:1px solid #16323c; color:var(--fg);
        border-radius:20px; padding:12px 16px; font-size:16px; font-family:inherit; outline:none; }
  .bar button{ background:var(--acc); color:var(--bg); border:none; border-radius:20px;
        padding:0 18px; font-weight:bold; font-family:inherit; cursor:pointer; font-size:14px; }
  .reactor{ width:90px; height:90px; margin:6px auto; border-radius:50%;
        background:radial-gradient(circle,#fff 0%,var(--acc) 35%,transparent 70%);
        box-shadow:0 0 24px var(--acc); animation:pulse 2s infinite; }
  @keyframes pulse{ 0%,100%{transform:scale(1);opacity:.9} 50%{transform:scale(1.08);opacity:1} }

  /* ---------- TELEFON MODU ---------- */
  body[data-mode="phone"]{ max-width:480px; margin:0 auto; }
  body[data-mode="phone"] header h1{ font-size:20px; }

  /* ---------- MASAÜSTÜ MODU ---------- */
  body[data-mode="desktop"]{ max-width:760px; margin:0 auto; }
  body[data-mode="desktop"] header h1{ font-size:28px; }
</style>
</head>
<body data-mode="desktop">
  <div class="badge" id="badge">●</div>
  <header>
    <div class="reactor"></div>
    <h1 id="title">JARVIS</h1>
    <div class="sub" id="sub">Companion — bağlı</div>
    <div class="clock" id="clock">--:--:--</div>
    <div class="date" id="date"></div>
  </header>

  <div id="chat"></div>

  <div class="quick">
    <button onclick="send('saat kaç')">Saat</button>
    <button onclick="send('hava durumu')">Hava</button>
    <button onclick="send('priz aç')">Priz Aç</button>
    <button onclick="send('priz kapat')">Priz Kapat</button>
    <button onclick="send('günaydın')">Plan</button>
    <button onclick="send('istatistik')">İstatistik</button>
  </div>

  <div class="bar">
    <input id="inp" placeholder="Komut yazın, Efendim…" autocomplete="off"
           onkeydown="if(event.key==='Enter')go()">
    <button onclick="go()">➤</button>
  </div>

<script>
  // ?mode= ile bu cihazın düzenini zorla; yoksa sunucunun aktif modunu takip et.
  const params = new URLSearchParams(location.search);
  const forced = params.get('mode');   // phone / desktop / null
  if (forced) document.body.dataset.mode = forced;

  const chat = document.getElementById('chat');
  function add(text, cls){
    const d = document.createElement('div');
    d.className = 'msg ' + cls; d.textContent = text;
    chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
  }
  async function send(text){
    add(text, 'me');
    try{
      const r = await fetch('/api/command', {method:'POST',
        headers:{'Content-Type':'application/json'}, body:JSON.stringify({text})});
      const j = await r.json();
      if (j.response) add(j.response, 'jv');
    }catch(e){ add('Bağlantı hatası', 'jv'); }
  }
  function go(){ const i=document.getElementById('inp'); const t=i.value.trim();
    if(t){ send(t); i.value=''; } }

  async function poll(){
    try{
      const r = await fetch('/api/status'); const s = await r.json();
      document.getElementById('clock').textContent = s.time;
      document.getElementById('date').textContent = s.date;
      document.getElementById('title').textContent = s.assistant_name;
      document.getElementById('badge').style.color = '#00e676';
      const sub = s.device ? ('Aktif cihaz: ' + s.device) : 'Companion — bağlı';
      document.getElementById('sub').textContent = sub;
      // kendi modunu zorlamayan istemci, sunucunun aktif moduna geçer
      if (!forced && s.mode) document.body.dataset.mode = s.mode;
    }catch(e){ document.getElementById('badge').style.color = '#ff5252'; }
  }
  setInterval(poll, 2000); poll();
</script>
</body>
</html>"""
