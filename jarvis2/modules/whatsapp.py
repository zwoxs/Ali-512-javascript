"""WhatsApp — Selenium'suz, wa.me deep link + tarayıcı tabanlı entegrasyon.

Mesaj otomatik gönderilmez; sohbet açılır ve mesaj kutuya hazır gelir,
kullanıcı Enter'a basar. (Bilinen kısıtlama.)

Kişiler bellek yöneticisinden (MemoryManager) okunur.
"""
import platform
import subprocess
import threading
import time
import urllib.parse
import webbrowser


class WhatsApp:
    def __init__(self, memory=None):
        self.memory = memory
        self.favorites = set()
        self.message_log = []  # {"contact", "message", "ts"}
        self.templates = {
            "selam": "Merhaba, nasılsın?",
            "toplanti": "Merhaba, toplantımızı hatırlatmak istedim.",
            "tesekkur": "Çok teşekkür ederim!",
            "gunaydin": "Günaydın! İyi günler dilerim.",
            "iyi_geceler": "İyi geceler, tatlı rüyalar.",
            "mesgul": "Şu an meşgulüm, birazdan dönerim.",
            "yoldayim": "Yoldayım, birazdan oradayım.",
            "tamam": "Tamamdır, anlaştık.",
            "ararim": "Birazdan seni ararım.",
            "kutlama": "Tebrikler! 🎉",
        }

    # ---------- yardımcılar ----------
    @staticmethod
    def _normalize_number(raw: str) -> str:
        """Telefon numarasını uluslararası formata indirger (sadece rakam)."""
        digits = "".join(ch for ch in raw if ch.isdigit())
        # Türkiye: 0 ile başlıyorsa 90 ekle
        if digits.startswith("0"):
            digits = "90" + digits[1:]
        return digits

    @staticmethod
    def is_valid_number(raw: str) -> bool:
        digits = "".join(ch for ch in raw if ch.isdigit())
        return 10 <= len(digits) <= 15

    def _resolve_contact(self, contact: str):
        """İsim veya numara al; (görünen ad, numara) döndür."""
        if self.is_valid_number(contact):
            return contact, self._normalize_number(contact)
        if self.memory:
            phone = self.memory.get_contact(contact)
            if phone:
                return contact, self._normalize_number(phone)
        return contact, None

    # ---------- açma ----------
    def open_web(self) -> str:
        webbrowser.open("https://web.whatsapp.com")
        return "WhatsApp Web açılıyor, Efendim."

    def send_message(self, contact: str, message: str) -> str:
        """Kişinin sohbetini wa.me deep link ile açar, mesajı hazır getirir."""
        name, number = self._resolve_contact(contact)
        if not number:
            return (f"'{contact}' için numara bulamadım, Efendim. "
                    "Önce rehbere ekleyin veya numara söyleyin.")

        text = urllib.parse.quote(message)
        url = f"https://wa.me/{number}?text={text}"
        webbrowser.open(url)

        self.message_log.append({"contact": name, "message": message, "ts": time.time()})
        return f"{name} ile sohbet açıldı. Mesaj hazır — göndermek için Enter'a basın, Efendim."

    # ---------- toplu ----------
    def broadcast_message(self, contacts: list, message: str) -> str:
        sent = 0
        for c in contacts:
            _, number = self._resolve_contact(c)
            if number:
                self.send_message(c, message)
                sent += 1
                time.sleep(1)  # tarayıcı sekmeleri arasında nefes
        return f"{sent} kişiye mesaj sekmesi açıldı, Efendim."

    def broadcast_to_favorites(self, message: str) -> str:
        if not self.favorites:
            return "Favori listeniz boş, Efendim."
        return self.broadcast_message(list(self.favorites), message)

    def add_favorite(self, contact: str) -> None:
        self.favorites.add(contact.strip().lower())

    # ---------- zamanlanmış ----------
    def schedule_message(self, contact: str, message: str, seconds: int) -> str:
        t = threading.Timer(seconds, self.send_message, args=[contact, message])
        t.daemon = True
        t.start()
        return f"{contact} için mesaj {seconds} saniye sonra hazırlanacak, Efendim."

    # ---------- şablonlar ----------
    def get_template(self, key: str):
        return self.templates.get(key.strip().lower())

    def add_template(self, key: str, text: str) -> None:
        self.templates[key.strip().lower()] = text

    # ---------- içe/dışa aktarma ----------
    def import_contacts_from_text(self, raw: str) -> int:
        """Her satır 'isim, numara' veya 'isim: numara' formatında."""
        if not self.memory:
            return 0
        count = 0
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            for sep in (",", ":", ";", "\t"):
                if sep in line:
                    name, _, phone = line.partition(sep)
                    if name.strip() and phone.strip():
                        self.memory.add_contact(name.strip(), phone.strip())
                        count += 1
                    break
        return count

    def export_contacts_to_text(self) -> str:
        if not self.memory:
            return ""
        lines = [f"{name}, {phone}" for name, phone in self.memory.list_contacts().items()]
        return "\n".join(lines)
