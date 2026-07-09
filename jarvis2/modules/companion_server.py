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
            elif path == "/icon.svg":
                self._send(200, _ICON_SVG, "image/svg+xml")
            elif path == "/sw.js":
                self._send(200, _SW_JS, "application/javascript")
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
    "orientation": "portrait",
    "background_color": "#05070a",
    "theme_color": "#00e5ff",
    "icons": [
        {"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml",
         "purpose": "any maskable"},
    ],
})

# Arc reaktör temalı uygulama ikonu (SVG)
_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
    '<rect width="512" height="512" rx="96" fill="#05070a"/>'
    '<circle cx="256" cy="256" r="150" fill="none" stroke="#00e5ff" stroke-width="18"/>'
    '<circle cx="256" cy="256" r="110" fill="none" stroke="#18ffff" stroke-width="8" opacity="0.6"/>'
    '<circle cx="256" cy="256" r="66" fill="#00e5ff"/>'
    '<circle cx="256" cy="256" r="30" fill="#ffffff"/>'
    '</svg>'
)

# Basit service worker — kabuğu önbelleğe alır (kurulabilirlik + hızlı açılış)
_SW_JS = (
    "const C='jarvis-v1';\n"
    "self.addEventListener('install',e=>{self.skipWaiting();"
    "e.waitUntil(caches.open(C).then(c=>c.addAll(['/','/manifest.json','/icon.svg'])));});\n"
    "self.addEventListener('activate',e=>self.clients.claim());\n"
    "self.addEventListener('fetch',e=>{\n"
    "  const u=new URL(e.request.url);\n"
    "  if(u.pathname.startsWith('/api/')) return;  // API'yi önbelleğe alma\n"
    "  e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));\n"
    "});\n"
)


# =====================================================================
#  UYARLANIR WEB ARAYÜZÜ (tek dosya, self-contained)
# =====================================================================
_PAGE_HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="theme-color" content="#00e5ff">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="JARVIS">
<link rel="manifest" href="/manifest.json">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/icon.svg">
<title>JARVIS Companion</title>
<style>
  :root{
    --acc:#00e5ff; --acc2:#0091ea; --glow:#18ffff;
    --bg:#04070c; --panel:rgba(255,255,255,.04); --line:rgba(0,229,255,.16);
    --fg:#dbe7f2; --dim:#6b7d8f;
  }
  *{ box-sizing:border-box; margin:0; padding:0; -webkit-tap-highlight-color:transparent; }
  html,body{ overflow-x:hidden; }
  body{
    font-family:'Segoe UI',Consolas,system-ui,monospace;
    color:var(--fg); min-height:100vh; width:100%;
    display:flex; flex-direction:column; position:relative;
    background:radial-gradient(120% 80% at 50% -10%, #0a1622 0%, var(--bg) 55%);
  }
  /* --- canlı arka plan: ızgara + tarama çizgisi + parıltı --- */
  .bgfx{ position:fixed; inset:0; z-index:-1; overflow:hidden; pointer-events:none; }
  .grid{ position:absolute; inset:-50%; opacity:.25;
    background-image:linear-gradient(var(--line) 1px,transparent 1px),
                     linear-gradient(90deg,var(--line) 1px,transparent 1px);
    background-size:44px 44px; animation:drift 24s linear infinite;
    mask-image:radial-gradient(60% 50% at 50% 30%, #000 0%, transparent 75%); }
  @keyframes drift{ to{ transform:translateY(44px); } }
  .scan{ position:absolute; left:0; right:0; height:180px;
    background:linear-gradient(180deg,transparent,rgba(0,229,255,.06),transparent);
    animation:scan 7s linear infinite; }
  @keyframes scan{ 0%{top:-200px} 100%{top:110%} }

  .badge{ position:fixed; top:12px; right:12px; z-index:5; display:flex; align-items:center;
    gap:6px; font-size:11px; color:var(--dim); background:var(--panel);
    border:1px solid var(--line); border-radius:20px; padding:5px 11px;
    backdrop-filter:blur(8px); }
  .badge b{ width:8px; height:8px; border-radius:50%; background:#00e676;
    box-shadow:0 0 8px #00e676; }

  /* --- tema seçici --- */
  .themebtn{ position:fixed; top:12px; left:12px; z-index:6; width:36px; height:36px;
    border-radius:50%; background:var(--panel); border:1px solid var(--line); color:var(--acc);
    font-size:17px; cursor:pointer; backdrop-filter:blur(8px); }
  .palette{ position:fixed; top:56px; left:12px; z-index:6; display:none; gap:9px;
    padding:12px; width:128px; flex-wrap:wrap; background:var(--panel);
    border:1px solid var(--line); border-radius:16px; backdrop-filter:blur(12px); }
  .palette.open{ display:flex; }
  .swatch{ width:26px; height:26px; border-radius:50%; cursor:pointer;
    border:2px solid rgba(255,255,255,.18); transition:transform .12s; }
  .swatch:active{ transform:scale(.88); }
  .swatch.sel{ border-color:#fff; box-shadow:0 0 10px currentColor; }

  header{ padding:20px 16px 10px; text-align:center; }
  /* --- Arc reaktör --- */
  .reactor{ width:118px; height:118px; margin:2px auto 10px; position:relative; }
  .reactor svg{ position:absolute; inset:0; width:100%; height:100%; }
  .reactor .r-spin circle{ stroke:var(--acc); }
  .reactor .r-spin.rev circle{ stroke:var(--glow); }
  .reactor svg>circle{ stroke:var(--acc); opacity:.22; }
  .r-spin{ transform-origin:60px 60px; animation:spin 8s linear infinite; }
  .r-spin.rev{ animation:spin 12s linear infinite reverse; }
  @keyframes spin{ to{ transform:rotate(360deg); } }
  .r-core{ position:absolute; inset:38px; border-radius:50%;
    background:radial-gradient(circle,#fff 0%,var(--glow) 30%,var(--acc) 60%,transparent 72%);
    box-shadow:0 0 26px var(--acc),0 0 54px rgba(0,229,255,.5); animation:corePulse 2.4s ease-in-out infinite; }
  @keyframes corePulse{ 0%,100%{transform:scale(1);opacity:.92} 50%{transform:scale(1.1);opacity:1} }

  header h1{ font-size:26px; font-weight:700; letter-spacing:6px; color:#eafcff;
    text-shadow:0 0 18px var(--acc); }
  .sub{ margin-top:6px; display:inline-flex; align-items:center; gap:8px; font-size:12px;
    color:var(--dim); }
  .chip{ background:var(--panel); border:1px solid var(--line); border-radius:20px;
    padding:3px 10px; color:var(--acc); font-size:11px; }
  .clock{ font-size:46px; font-weight:700; letter-spacing:2px; margin:10px 0 2px;
    font-variant-numeric:tabular-nums; color:#eafcff; text-shadow:0 0 20px var(--acc); }
  .date{ color:var(--dim); font-size:12px; letter-spacing:1px; }

  /* --- ses dalgası (dinlerken) --- */
  .wave{ height:0; display:flex; align-items:center; justify-content:center; gap:5px;
    overflow:hidden; transition:height .3s ease; }
  body.listening .wave{ height:34px; margin:6px 0; }
  .wave i{ width:4px; height:8px; border-radius:3px; background:var(--acc);
    box-shadow:0 0 8px var(--acc); }
  body.listening .wave i{ animation:eq .9s ease-in-out infinite; }
  .wave i:nth-child(2){ animation-delay:.1s } .wave i:nth-child(3){ animation-delay:.2s }
  .wave i:nth-child(4){ animation-delay:.3s } .wave i:nth-child(5){ animation-delay:.15s }
  .wave i:nth-child(6){ animation-delay:.25s } .wave i:nth-child(7){ animation-delay:.05s }
  @keyframes eq{ 0%,100%{ height:8px } 50%{ height:28px } }

  #chat{ flex:1; overflow-y:auto; padding:14px 16px 8px; display:flex; flex-direction:column;
    gap:10px; scroll-behavior:smooth; }
  .msg{ position:relative; padding:11px 15px; border-radius:16px; max-width:86%; font-size:15px;
    line-height:1.45; white-space:pre-wrap; word-break:break-word; backdrop-filter:blur(10px);
    animation:pop .28s cubic-bezier(.2,.8,.2,1); }
  @keyframes pop{ from{ opacity:0; transform:translateY(8px) scale(.98) } to{ opacity:1; transform:none } }
  .me{ align-self:flex-end; color:#eafcff;
    background:linear-gradient(135deg, color-mix(in srgb,var(--acc2) 34%,transparent),
                                       color-mix(in srgb,var(--acc) 18%,transparent));
    border:1px solid color-mix(in srgb,var(--acc) 38%,transparent);
    border-bottom-right-radius:5px; }
  .jv{ align-self:flex-start; color:#d6f4ff; background:var(--panel);
    border:1px solid var(--line); border-left:3px solid var(--acc); border-bottom-left-radius:5px; }
  .typing{ color:var(--dim); font-style:italic; }
  .typing::after{ content:'▋'; animation:blink 1s steps(2) infinite; }
  @keyframes blink{ 0%,50%{opacity:1} 51%,100%{opacity:0} }

  .quick{ display:flex; flex-wrap:wrap; gap:8px; padding:6px 16px 10px; }
  .quick button{ background:var(--panel); color:var(--fg); border:1px solid var(--line);
    border-radius:20px; padding:9px 15px; font-size:13px; font-family:inherit; cursor:pointer;
    transition:all .15s; backdrop-filter:blur(8px); }
  .quick button:active{ background:var(--acc); color:var(--bg); transform:scale(.95);
    box-shadow:0 0 14px rgba(0,229,255,.5); }

  .bar{ display:flex; gap:9px; padding:12px 14px calc(12px + env(safe-area-inset-bottom));
    background:linear-gradient(180deg,transparent,rgba(4,7,12,.85) 30%);
    align-items:center; position:sticky; bottom:0; }
  .bar input{ flex:1; min-width:0; background:var(--panel); border:1px solid var(--line);
    color:var(--fg); border-radius:24px; padding:13px 16px; font-size:16px; font-family:inherit;
    outline:none; transition:box-shadow .2s,border-color .2s; }
  .bar input:focus{ border-color:var(--acc); box-shadow:0 0 0 3px rgba(0,229,255,.15); }
  .icon{ min-width:46px; height:46px; border-radius:50%; background:var(--panel);
    color:var(--acc); border:1px solid var(--line); font-size:19px; cursor:pointer;
    display:flex; align-items:center; justify-content:center; transition:all .15s; flex:0 0 auto; }
  .icon:active{ transform:scale(.92); }
  .icon.on{ background:#ff5252; color:#fff; border-color:#ff5252; box-shadow:0 0 14px rgba(255,82,82,.6);
    animation:corePulse 1s infinite; }
  .icon.cont{ background:var(--acc); color:var(--bg); border-color:var(--acc);
    box-shadow:0 0 14px rgba(0,229,255,.5); }
  .send{ min-width:52px; height:46px; border-radius:24px; border:none; cursor:pointer;
    background:linear-gradient(135deg,var(--acc),var(--acc2)); color:var(--bg);
    font-size:18px; font-weight:700; box-shadow:0 0 16px rgba(0,229,255,.45);
    display:flex; align-items:center; justify-content:center; flex:0 0 auto; transition:transform .15s; }
  .send:active{ transform:scale(.92); }

  /* --- düzenler --- */
  body[data-mode="phone"]{ max-width:520px; margin:0 auto; }
  body[data-mode="desktop"]{ max-width:840px; margin:0 auto; }
  body[data-mode="desktop"] header h1{ font-size:30px; }
  body[data-mode="desktop"] .clock{ font-size:54px; }
</style>
</head>
<body data-mode="desktop">
  <div class="bgfx"><div class="grid"></div><div class="scan"></div></div>
  <div class="badge"><b></b><span id="btxt">bağlanıyor…</span></div>
  <button class="themebtn" onclick="togglePalette()" title="Tema">🎨</button>
  <div class="palette" id="palette"></div>

  <header>
    <div class="reactor">
      <svg viewBox="0 0 120 120">
        <g class="r-spin">
          <circle cx="60" cy="60" r="54" fill="none" stroke="#00e5ff" stroke-width="2"
            stroke-dasharray="8 12" opacity="0.8"/>
        </g>
        <g class="r-spin rev">
          <circle cx="60" cy="60" r="44" fill="none" stroke="#18ffff" stroke-width="1.5"
            stroke-dasharray="4 10" opacity="0.6"/>
        </g>
        <circle cx="60" cy="60" r="34" fill="none" stroke="rgba(0,229,255,.25)" stroke-width="1"/>
      </svg>
      <div class="r-core"></div>
    </div>
    <h1 id="title">JARVIS</h1>
    <div class="sub"><span id="sub">Companion</span></div>
    <div class="clock" id="clock">--:--:--</div>
    <div class="date" id="date"></div>
    <div class="wave"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
  </header>

  <div id="chat"></div>

  <div class="quick">
    <button onclick="send('saat kaç')">🕐 Saat</button>
    <button onclick="send('hava durumu')">🌤 Hava</button>
    <button onclick="send('priz aç')">🔌 Priz Aç</button>
    <button onclick="send('priz kapat')">⭕ Priz Kapat</button>
    <button onclick="send('günaydın')">📋 Plan</button>
    <button onclick="send('istatistik')">📊 İstatistik</button>
  </div>

  <div class="bar">
    <button id="mic" class="icon" onclick="toggleMic()" title="Sesli komut">🎤</button>
    <button id="cont" class="icon" onclick="toggleCont()" title="Eller serbest">♾️</button>
    <input id="inp" placeholder="Konuşun veya yazın, Efendim…" autocomplete="off"
           onkeydown="if(event.key==='Enter')go()">
    <button id="snd" class="icon" onclick="toggleSound()" title="Sesli cevap">🔊</button>
    <button class="send" onclick="go()">➤</button>
  </div>

<script>
  const params = new URLSearchParams(location.search);
  const forced = params.get('mode');
  if (forced) document.body.dataset.mode = forced;

  const chat = document.getElementById('chat');
  function add(text, cls){
    const d = document.createElement('div');
    d.className = 'msg ' + cls; d.textContent = text;
    chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
    return d;
  }
  function showTyping(){ if(document.getElementById('typing')) return;
    const d = add('JARVIS düşünüyor', 'jv typing'); d.id='typing'; }
  function hideTyping(){ const t=document.getElementById('typing'); if(t) t.remove(); }
  function buzz(ms){ try{ navigator.vibrate && navigator.vibrate(ms); }catch(e){} }

  let speakOn = true;
  const synth = window.speechSynthesis;
  function speak(t){
    if(!speakOn || !synth || !t) return;
    try{
      const u = new SpeechSynthesisUtterance(t);
      u.lang='tr-TR'; u.rate=1.0; u.pitch=1.0;
      const v=(synth.getVoices()||[]).find(x=>x.lang && x.lang.toLowerCase().startsWith('tr'));
      if(v) u.voice=v;
      u.onstart = ()=>{ speaking=true; try{ rec && rec.stop(); }catch(e){} };
      u.onend = ()=>{ speaking=false; if(contMode) setTimeout(startRec, 300); };
      synth.cancel(); synth.speak(u);
    }catch(e){}
  }
  function toggleSound(){
    speakOn=!speakOn;
    document.getElementById('snd').textContent = speakOn?'🔊':'🔇';
    if(!speakOn && synth) synth.cancel();
  }

  async function send(text){
    add(text, 'me'); showTyping();
    try{
      const r = await fetch('/api/command', {method:'POST',
        headers:{'Content-Type':'application/json'}, body:JSON.stringify({text})});
      const j = await r.json();
      hideTyping();
      if (j.response){ add(j.response, 'jv'); buzz(30); speak(j.response); }
    }catch(e){ hideTyping(); add('Bağlantı hatası, Efendim.', 'jv'); }
  }
  function go(){ const i=document.getElementById('inp'); const t=i.value.trim();
    if(t){ send(t); i.value=''; } }

  let rec=null, listening=false, contMode=false, speaking=false;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  function setMic(on){
    listening=on;
    document.body.classList.toggle('listening', on);
    const m=document.getElementById('mic');
    m.textContent = on?'🔴':'🎤'; m.classList.toggle('on', on && !contMode);
  }
  function startRec(){
    if(!SR || listening || speaking) return;
    rec = new SR(); rec.lang='tr-TR'; rec.interimResults=false; rec.maxAlternatives=1;
    setMic(true);
    rec.onresult = e => { const t = e.results[0][0].transcript; if(t) send(t); };
    rec.onerror = () => setMic(false);
    rec.onend = () => { setMic(false); if(contMode && !speaking) setTimeout(startRec, 400); };
    try{ rec.start(); }catch(e){ setMic(false); }
  }
  function toggleMic(){
    if(!SR){ add('Bu tarayıcı sesli komutu desteklemiyor, Efendim.', 'jv'); return; }
    if(listening){ try{rec.stop();}catch(e){} return; }
    startRec();
  }
  function toggleCont(){
    if(!SR){ add('Bu tarayıcı sesli komutu desteklemiyor, Efendim.', 'jv'); return; }
    contMode=!contMode;
    document.getElementById('cont').classList.toggle('cont', contMode);
    if(contMode){ add('Eller serbest mod açık — dinliyorum, Efendim.', 'jv'); startRec(); }
    else { add('Eller serbest mod kapalı.', 'jv'); try{rec && rec.stop();}catch(e){} }
  }
  if(synth) synth.onvoiceschanged = ()=>{};

  async function poll(){
    try{
      const r = await fetch('/api/status'); const s = await r.json();
      document.getElementById('clock').textContent = s.time;
      document.getElementById('date').textContent = s.date;
      document.getElementById('title').textContent = s.assistant_name;
      document.getElementById('btxt').textContent = 'bağlı';
      document.querySelector('.badge b').style.background = '#00e676';
      document.getElementById('sub').innerHTML = s.device
        ? ('Aktif cihaz: <span class="chip">'+s.device+'</span>') : 'Companion — hazır';
      if (!forced && s.mode) document.body.dataset.mode = s.mode;
    }catch(e){
      document.getElementById('btxt').textContent = 'bağlantı yok';
      document.querySelector('.badge b').style.background = '#ff5252';
    }
  }
  setInterval(poll, 2000); poll();

  // ---- Tema seçici (HUD ile aynı 7 palet) ----
  const THEMES = {
    CYAN:['#00e5ff','#0091ea','#18ffff'], GREEN:['#00e676','#00c853','#69f0ae'],
    RED:['#ff5252','#d50000','#ff8a80'], GOLD:['#ffd54f','#ffab00','#ffe57f'],
    PURPLE:['#b388ff','#7c4dff','#e1bee7'], MATRIX:['#39ff14','#00ff41','#76ff03'],
    ORANGE:['#ff9100','#ff6d00','#ffab40'],
  };
  function applyTheme(name){
    const t = THEMES[name]; if(!t) return;
    const r = document.documentElement.style;
    r.setProperty('--acc', t[0]); r.setProperty('--acc2', t[1]); r.setProperty('--glow', t[2]);
    r.setProperty('--line', t[0].replace(')', '') + '28');  // hafif çizgi (yaklaşık)
    document.querySelector('meta[name=theme-color]').setAttribute('content', t[0]);
    try{ localStorage.setItem('jarvisTheme', name); }catch(e){}
    document.querySelectorAll('.swatch').forEach(s=>s.classList.toggle('sel', s.dataset.n===name));
  }
  function buildPalette(){
    const p = document.getElementById('palette');
    Object.keys(THEMES).forEach(name=>{
      const s = document.createElement('div');
      s.className='swatch'; s.dataset.n=name; s.style.background=THEMES[name][0];
      s.style.color=THEMES[name][0]; s.title=name;
      s.onclick=()=>{ applyTheme(name); togglePalette(); };
      p.appendChild(s);
    });
  }
  function togglePalette(){ document.getElementById('palette').classList.toggle('open'); }
  buildPalette();
  applyTheme(localStorage.getItem('jarvisTheme') || 'CYAN');

  if('serviceWorker' in navigator){ navigator.serviceWorker.register('/sw.js').catch(()=>{}); }
</script>
</body>
</html>"""
