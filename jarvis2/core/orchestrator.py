"""Orchestrator — merkezi yönetici.

Intent parser'dan gelen action'ı ilgili modüle yönlendirir, cevabı üretir,
belleğe loglar, kısa süreli bağlam tutar ve istatistik toplar.
"""
import platform
import random
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime, timedelta

from core.intent_parser import IntentParser

# ----- çeşitli cevap havuzları -----
GREET = ["Merhaba Efendim.", "Buyurun Efendim.", "Emrinizdeyim.", "Dinliyorum, Efendim."]
ACK = ["Tabii Efendim.", "Hemen Efendim.", "Anlaşıldı.", "Elbette."]
DONE = ["Tamamdır, Efendim.", "Halloldu.", "İşlem tamam.", "Yapıldı, Efendim."]
NOT_FOUND = ["Bunu bulamadım, Efendim.", "Maalesef bir sonuç yok."]
UNKNOWN = ["Bunu tam anlayamadım, Efendim.", "Komutu çözemedim, tekrar eder misiniz?"]

_GUN = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
_AY = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
       "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


class Orchestrator:
    def __init__(self, settings, memory, ai_brain=None, smart_home=None,
                 whatsapp=None, planner=None, voice_output=None, weather=None):
        self.settings = settings
        self.memory = memory
        self.ai_brain = ai_brain
        self.smart_home = smart_home
        self.whatsapp = whatsapp
        self.planner = planner
        self.voice_output = voice_output
        self.weather = weather
        self.parser = IntentParser(settings)

        # kısa süreli bağlam
        self.context = {"last_contact": None, "last_query": None, "last_app": None}

        # oturum istatistikleri
        self.stats = {
            "commands": 0, "searches": 0, "messages": 0,
            "voice_cmds": 0, "started": time.time(),
        }

        # bildirim callback'i (UI/toast)
        self.notify_callback = None

    # ---------- callback kayıtları ----------
    def set_notify_callback(self, cb):
        self.notify_callback = cb

    def _notify(self, msg):
        if self.notify_callback:
            try:
                self.notify_callback(msg)
            except Exception:
                pass

    def reload_settings(self, settings):
        self.settings = settings
        self.parser = IntentParser(settings)

    # ---------- ana giriş noktası ----------
    def handle(self, text: str, from_voice: bool = False) -> str:
        self.stats["commands"] += 1
        if from_voice:
            self.stats["voice_cmds"] += 1

        intent = self.parser.parse(text)
        action = intent["action"]
        params = intent["params"]
        response = self._dispatch(action, params)

        try:
            self.memory.log_interaction(text, response)
        except Exception:
            pass
        return response

    # ---------- action yönlendirme ----------
    def _dispatch(self, action: str, p: dict) -> str:
        handler = getattr(self, f"_act_{action}", None)
        if handler:
            return handler(p)
        return random.choice(UNKNOWN)

    # ---------- temel action'lar ----------
    def _act_time(self, p):
        return f"Saat {datetime.now().strftime('%H:%M')}, Efendim."

    def _act_date(self, p):
        now = datetime.now()
        return f"Bugün {_GUN[now.weekday()]}, {now.day} {_AY[now.month - 1]} {now.year}, Efendim."

    def _act_greet(self, p):
        return random.choice(GREET)

    def _act_help(self, p):
        return (
            "Şunları yapabilirim, Efendim:\n"
            "• saat / tarih\n"
            "• günaydın (günlük plan)\n"
            "• priz/lamba aç-kapat-durumu\n"
            "• [konu] ara\n"
            "• whatsapp aç, kişileri listele, [kişi]ye [mesaj] yaz\n"
            "• [uygulama] aç/kapat\n"
            "• 10 dakika sonra [not] hatırlat\n"
            "• istatistik\n"
            "• serbest soru sorabilirsiniz (AI beyni yanıtlar)"
        )

    def _act_exit(self, p):
        return "__EXIT__"

    def _act_unknown(self, p):
        return random.choice(UNKNOWN)

    def _act_command(self, p):
        return self._handle_slash(p.get("raw", ""))

    # ---------- plan / istatistik ----------
    def _act_morning_routine(self, p):
        if self.planner:
            return self.planner.plan()
        return "Günaydın Efendim. Bugün güzel bir gün olacak."

    def _act_stats(self, p):
        up = int(time.time() - self.stats["started"])
        mins, secs = divmod(up, 60)
        return (f"Oturum istatistikleri, Efendim:\n"
                f"• Komut: {self.stats['commands']}\n"
                f"• Arama: {self.stats['searches']}\n"
                f"• Mesaj: {self.stats['messages']}\n"
                f"• Sesli komut: {self.stats['voice_cmds']}\n"
                f"• Süre: {mins} dk {secs} sn")

    # ---------- hatırlatıcı ----------
    def _act_reminder(self, p):
        seconds = p.get("seconds", 0)
        note = p.get("text", "hatırlatma")
        remind_at = (datetime.now() + timedelta(seconds=seconds)).isoformat(timespec="seconds")
        self.memory.add_reminder(note, remind_at)

        def fire():
            msg = f"⏰ Hatırlatma, Efendim: {note}"
            self._notify(msg)
            if self.voice_output:
                self.voice_output.speak(msg, blocking=False)

        t = threading.Timer(seconds, fire)
        t.daemon = True
        t.start()

        mins = seconds // 60
        when = f"{mins} dakika" if mins else f"{seconds} saniye"
        return f"{when} sonra hatırlatacağım: {note}"

    def _act_list_reminders(self, p):
        reminders = self.memory.list_reminders()
        if not reminders:
            return "Aktif hatırlatıcınız yok, Efendim."
        lines = [f"• {r['text']} ({r['at']})" for r in reminders]
        return "Hatırlatıcılar:\n" + "\n".join(lines)

    def _act_clear_reminders(self, p):
        self.memory.clear_reminders()
        return "Tüm hatırlatıcılar temizlendi, Efendim."

    # ---------- akıllı ev ----------
    def _act_device_on(self, p):
        device = p.get("device", "priz")
        if not self.smart_home or not self.smart_home.available:
            return "Akıllı ev bağlantısı yok, Efendim. Home Assistant ayarlarını kontrol edin."
        ok = self.smart_home.turn_on(device)
        return f"{device.capitalize()} açıldı, Efendim." if ok else f"{device} açılamadı."

    def _act_device_off(self, p):
        device = p.get("device", "priz")
        if not self.smart_home or not self.smart_home.available:
            return "Akıllı ev bağlantısı yok, Efendim."
        ok = self.smart_home.turn_off(device)
        return f"{device.capitalize()} kapatıldı, Efendim." if ok else f"{device} kapatılamadı."

    def _act_device_state(self, p):
        device = p.get("device", "priz")
        if not self.smart_home or not self.smart_home.available:
            return "Akıllı ev bağlantısı yok, Efendim."
        state = self.smart_home.get_state(device)
        tr = {"on": "açık", "off": "kapalı"}.get(state, state)
        return f"{device.capitalize()} şu an {tr}, Efendim."

    # ---------- WhatsApp ----------
    def _act_whatsapp_open(self, p):
        if not self.whatsapp:
            return "WhatsApp modülü yüklü değil."
        return self.whatsapp.open_web()

    def _act_whatsapp_send(self, p):
        if not self.whatsapp:
            return "WhatsApp modülü yüklü değil."
        contact = p.get("contact", "")
        message = p.get("message", "")
        self.context["last_contact"] = contact
        self.stats["messages"] += 1
        return self.whatsapp.send_message(contact, message)

    def _act_list_contacts(self, p):
        contacts = self.memory.list_contacts()
        if not contacts:
            return "Rehberiniz boş, Efendim."
        lines = [f"• {name}: {phone}" for name, phone in contacts.items()]
        return "Rehberdeki kişiler:\n" + "\n".join(lines)

    def _act_add_contact(self, p):
        name = p.get("name", "").strip()
        phone = p.get("phone", "").strip()
        if not name or not phone:
            return "Kişi adı ve numara gerekli, Efendim."
        self.memory.add_contact(name, phone)
        return f"{name} rehbere eklendi, Efendim."

    # ---------- uygulama / sistem ----------
    def _act_open_app(self, p):
        app = p.get("app", "").lower()
        self.context["last_app"] = app
        web_apps = {
            "youtube": "https://youtube.com",
            "spotify": "https://open.spotify.com",
        }
        if app in web_apps:
            webbrowser.open(web_apps[app])
            return f"{app.capitalize()} açılıyor, Efendim."

        win_apps = {
            "chrome": "chrome",
            "not defteri": "notepad",
            "hesap makinesi": "calc",
            "explorer": "explorer",
            "dosya gezgini": "explorer",
        }
        target = win_apps.get(app)
        if target and platform.system() == "Windows":
            try:
                subprocess.Popen(target, shell=True)
                return f"{app.capitalize()} açılıyor, Efendim."
            except Exception as e:
                return f"{app} açılamadı: {e}"
        # Windows dışı: chrome'u tarayıcı olarak aç
        if app == "chrome":
            webbrowser.open("https://google.com")
            return "Tarayıcı açılıyor, Efendim."
        return f"{app} bu sistemde açılamıyor, Efendim."

    def _act_close_app(self, p):
        app = p.get("app", "").lower()
        procs = {"chrome": "chrome.exe", "not defteri": "notepad.exe",
                 "hesap makinesi": "calc.exe", "spotify": "spotify.exe"}
        proc = procs.get(app)
        if proc and platform.system() == "Windows":
            try:
                subprocess.run(["taskkill", "/f", "/im", proc],
                               capture_output=True, check=False)
                return f"{app.capitalize()} kapatıldı, Efendim."
            except Exception as e:
                return f"{app} kapatılamadı: {e}"
        return f"{app} kapatılamadı (yalnızca Windows), Efendim."

    def _act_shutdown(self, p):
        if platform.system() == "Windows":
            subprocess.run(["shutdown", "/s", "/t", "30"], check=False)
            return "Sistem 30 saniye içinde kapanacak, Efendim. İptal için 'shutdown /a'."
        return "Sistem kapatma yalnızca Windows'ta destekleniyor, Efendim."

    def _act_restart(self, p):
        if platform.system() == "Windows":
            subprocess.run(["shutdown", "/r", "/t", "30"], check=False)
            return "Sistem 30 saniye içinde yeniden başlatılacak, Efendim."
        return "Yeniden başlatma yalnızca Windows'ta destekleniyor, Efendim."

    # ---------- web arama ----------
    def _act_search(self, p):
        query = p.get("query", "").strip()
        if not query:
            return random.choice(NOT_FOUND)
        self.context["last_query"] = query
        self.stats["searches"] += 1
        url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
        webbrowser.open(url)
        return f"'{query}' için arama açılıyor, Efendim."

    # ---------- hava durumu ----------
    def _act_weather(self, p):
        if not self.weather or not self.weather.available:
            return "Hava durumu için OWM_API_KEY ayarlı değil, Efendim."
        return self.weather.summary()

    # ---------- AI beyni (fallback) ----------
    def _act_ai_brain(self, p):
        query = p.get("query", "")
        if not self.ai_brain:
            return random.choice(UNKNOWN)
        history = self.memory.get_history(6)
        return self.ai_brain.ask(query, history)

    # ---------- slash komutları ----------
    def _handle_slash(self, raw: str) -> str:
        cmd = raw.lstrip("/").strip().lower()
        if cmd in ("help", "yardım"):
            return self._act_help({})
        if cmd == "stats":
            return self._act_stats({})
        if cmd == "clear":
            return "__CLEAR__"
        if cmd in ("exit", "quit"):
            return "__EXIT__"
        if cmd.startswith("theme"):
            return "__THEME__:" + cmd.replace("theme", "").strip().upper()
        return f"Bilinmeyen komut: /{cmd}"
