"""Proaktif Görev Yöneticisi.

Arka planda periyodik olarak durumları kontrol eder ve gerektiğinde
bildirim callback'i tetikler:
- Düşük pil uyarısı
- Zamanı gelen hatırlatıcılar (backup kontrol)
- Uzun süre aktivite yoksa nazik hatırlatma (opsiyonel)

Her kontrol güvenli biçimde try/except ile sarılıdır; bir modül yoksa atlanır.
"""
import threading
import time
from datetime import datetime

try:
    import psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False


class Proactive:
    def __init__(self, memory=None, smart_home=None, notify=None,
                 bluetooth=None, companion=None, auto_follow_phone=True,
                 check_interval: int = 60):
        self.memory = memory
        self.smart_home = smart_home
        self.bluetooth = bluetooth
        self.companion = companion
        self.auto_follow_phone = auto_follow_phone
        self.notify = notify or (lambda msg: None)
        self.check_interval = check_interval

        self._running = False
        self._thread = None
        self._battery_warned = False
        self._fired_reminders = set()
        self._phone_active = False   # telefonu takip modunda mıyız

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                self._check_battery()
                self._check_reminders()
                self._check_phone_presence()
            except Exception:
                pass
            # telefon takibi için daha sık uyan (15 sn'de bir tara)
            for _ in range(min(self.check_interval, 15)):
                if not self._running:
                    return
                time.sleep(1)

    # ---------- kontroller ----------
    def _check_battery(self):
        if not _PSUTIL_OK:
            return
        batt = psutil.sensors_battery()
        if not batt:
            return
        if batt.percent <= 20 and not batt.power_plugged and not self._battery_warned:
            self.notify(f"🔋 Pil %{int(batt.percent)}, Efendim. Şarj etmenizi öneririm.")
            self._battery_warned = True
        elif batt.power_plugged or batt.percent > 30:
            self._battery_warned = False

    def _check_reminders(self):
        if not self.memory:
            return
        now = datetime.now()
        for i, r in enumerate(self.memory.list_reminders(include_done=True)):
            if r.get("done"):
                continue
            key = f"{i}:{r.get('at')}"
            if key in self._fired_reminders:
                continue
            try:
                due = datetime.fromisoformat(r["at"])
            except (ValueError, KeyError):
                continue
            if due <= now:
                self.notify(f"⏰ Hatırlatma, Efendim: {r['text']}")
                self._fired_reminders.add(key)
                try:
                    self.memory.mark_reminder_done(i)
                except Exception:
                    pass

    def _check_phone_presence(self):
        """Bağlı bir telefon görülünce arayüzü otomatik telefon moduna al.

        Telefon bağlantısı kesilince masaüstü moduna geri döner.
        """
        if not (self.auto_follow_phone and self.bluetooth and self.companion):
            return
        try:
            paired = self.bluetooth.list_paired()  # bağlı/kayıtlı cihazlar
        except Exception:
            return
        phone = None
        for d in paired:
            if self.bluetooth.classify_device(d.get("name", "")) == "phone":
                phone = d.get("name")
                break

        if phone and not self._phone_active:
            # telefon bağlandı → yanına geç
            self.companion.set_mode("phone", phone)
            self._phone_active = True
            url = self.companion.local_url() if self.companion.running else ""
            self.notify(f"📱 {phone} bağlandı, Efendim. Telefon moduna geçtim; "
                        f"yanınızdayım. {url}".strip())
        elif not phone and self._phone_active:
            # telefon ayrıldı → masaüstüne dön
            self.companion.set_mode("desktop")
            self._phone_active = False
            self.notify("🖥 Telefon bağlantısı kesildi; masaüstü moduna döndüm, Efendim.")
