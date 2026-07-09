"""Intent Parser — doğal dil (Türkçe) metnini action + parametrelere çevirir.

Kural tabanlı hafif bir parser. Eşleşme bulunamazsa 'ai_brain' action'ına
düşer (genel AI sorgusu).
"""
import re


class IntentParser:
    def __init__(self, settings: dict):
        self.settings = settings
        self.wake_word = settings.get("wake_word", "jarvis").lower()

    def parse(self, text: str) -> dict:
        t = (text or "").strip().lower()
        # uyanma kelimesini temizle
        if t.startswith(self.wake_word):
            t = t[len(self.wake_word):].strip()

        if not t:
            return {"action": "unknown", "params": {}}

        # ----- UI / slash komutları -----
        if t.startswith("/"):
            return {"action": "command", "params": {"raw": t}}

        # ----- çıkış -----
        if t in ("çık", "kapat kendini", "kapan", "exit", "quit", "görüşürüz"):
            return {"action": "exit", "params": {}}

        # ----- yardım -----
        if t in ("yardım", "yardim", "help", "ne yapabilirsin"):
            return {"action": "help", "params": {}}

        # ----- zaman / tarih -----
        if re.search(r"\bsaat\s*kaç\b", t) or t == "saat":
            return {"action": "time", "params": {}}
        if re.search(r"\b(bugün.*tarih|tarih ne|hangi gün|günlerden ne)\b", t) or t == "tarih":
            return {"action": "date", "params": {}}

        # ----- selam -----
        if re.search(r"\b(selam|merhaba|günaydın|gunaydin|iyi günler|iyi akşamlar|hey)\b", t):
            if "günaydın" in t or "gunaydin" in t or "günlük plan" in t:
                return {"action": "morning_routine", "params": {}}
            return {"action": "greet", "params": {}}

        # ----- günlük plan -----
        if re.search(r"\b(günlük plan|günü planla|plan yap|brifing|brief)\b", t):
            return {"action": "morning_routine", "params": {}}

        # ----- istatistik -----
        if re.search(r"\b(istatistik|oturum bilgisi|kaç komut)\b", t):
            return {"action": "stats", "params": {}}

        # ----- hava durumu -----
        if re.search(r"\bhava\s*(durumu|nasıl|nasil|ne durumda)?\b", t):
            return {"action": "weather", "params": {}}

        # ----- hatırlatıcı -----
        m = re.search(r"(\d+)\s*(saniye|dakika|saat)\s*sonra\s+(.*?)\s*(?:hatırlat|hatirlat)", t)
        if m:
            amount = int(m.group(1))
            unit = m.group(2)
            note = m.group(3).strip()
            seconds = amount * {"saniye": 1, "dakika": 60, "saat": 3600}[unit]
            return {"action": "reminder", "params": {"seconds": seconds, "text": note}}
        if re.search(r"\bhatırlatıcıları listele|hatırlatıcılar\b", t):
            return {"action": "list_reminders", "params": {}}
        if re.search(r"\bhatırlatıcıları temizle|hatırlatıcıları sil\b", t):
            return {"action": "clear_reminders", "params": {}}

        # ----- akıllı ev (priz/lamba) -----
        m = re.search(r"\b(priz|lamba|ışık|isik|klima|fan)\b", t)
        if m:
            device = m.group(1).replace("ışık", "lamba").replace("isik", "lamba")
            if re.search(r"\b(aç|ac|yak|çalıştır)\b", t):
                return {"action": "device_on", "params": {"device": device}}
            if re.search(r"\b(kapat|kapa|söndür|sondur|durdur)\b", t):
                return {"action": "device_off", "params": {"device": device}}
            if re.search(r"\b(durum|durumu|açık mı|kapalı mı)\b", t):
                return {"action": "device_state", "params": {"device": device}}

        # ----- WhatsApp -----
        if re.search(r"\bwhatsapp\b.*\b(aç|ac|başlat)\b", t) or t == "whatsapp aç":
            return {"action": "whatsapp_open", "params": {}}
        if re.search(r"\bwhatsapp\b.*\b(kişileri|rehber|kişiler).*(listele|göster)\b", t):
            return {"action": "list_contacts", "params": {}}
        # "[kişi]e [mesaj] yaz" / "[kişi]e ... gönder"
        m = re.search(r"(.+?)['’]?[ae]?\s+(.+?)\s+(?:yaz|gönder|ilet|mesaj at)$", t)
        if m and "whatsapp" not in m.group(1):
            contact = m.group(1).strip()
            message = m.group(2).strip()
            if contact and message and len(contact) < 30:
                return {"action": "whatsapp_send",
                        "params": {"contact": contact, "message": message}}

        # ----- kişi ekle -----
        m = re.search(r"(?:kişi ekle|rehbere ekle)\s+(.+?)\s+(\+?\d[\d\s]+)", t)
        if m:
            return {"action": "add_contact",
                    "params": {"name": m.group(1).strip(), "phone": m.group(2).strip()}}

        # ----- uygulama aç/kapat -----
        m = re.search(r"\b(chrome|youtube|spotify|not defteri|hesap makinesi|explorer|dosya gezgini)\b.*\b(aç|ac|başlat)\b", t)
        if m:
            return {"action": "open_app", "params": {"app": m.group(1)}}
        m = re.search(r"\b(chrome|youtube|spotify|not defteri|hesap makinesi)\b.*\bkapat\b", t)
        if m:
            return {"action": "close_app", "params": {"app": m.group(1)}}

        # ----- sistem: ses seviyesi -----
        m = re.search(r"ses(?:i)?\s*(?:seviyesi(?:ni)?)?\s*(?:yüzde\s*)?(\d{1,3})", t)
        if m and re.search(r"\bses\b", t):
            return {"action": "set_volume", "params": {"percent": int(m.group(1))}}
        if re.search(r"\b(sesi aç|sesi yükselt|ses aç)\b", t):
            return {"action": "set_volume", "params": {"percent": 80}}
        if re.search(r"\b(sesi kıs|sesi azalt|ses kıs)\b", t):
            return {"action": "set_volume", "params": {"percent": 30}}
        if re.search(r"\b(bilgisayarın sesini kapat|sistemi sessize al|sesi kapat)\b", t):
            return {"action": "mute_system", "params": {}}

        # ----- sistem: kilit / uyku / ekran görüntüsü / medya -----
        if re.search(r"\b(ekranı kilitle|bilgisayarı kilitle|kilitle)\b", t):
            return {"action": "lock", "params": {}}
        if re.search(r"\b(uyku moduna al|uyut|uyku)\b", t):
            return {"action": "sleep", "params": {}}
        if re.search(r"\b(ekran görüntüsü|ekran resmi|screenshot)\b", t):
            return {"action": "screenshot", "params": {}}
        if re.search(r"\b(sonraki şarkı|sonraki parça|next)\b", t):
            return {"action": "media", "params": {"cmd": "next"}}
        if re.search(r"\b(önceki şarkı|önceki parça|geri sar)\b", t):
            return {"action": "media", "params": {"cmd": "prev"}}
        if re.search(r"\b(müziği duraklat|müziği başlat|oynat|duraklat|play|pause)\b", t):
            return {"action": "media", "params": {"cmd": "play_pause"}}

        # ----- sistem: kapat / yeniden başlat -----
        if re.search(r"\b(sistemi kapat|bilgisayarı kapat)\b", t):
            return {"action": "shutdown", "params": {}}
        if re.search(r"\b(yeniden başlat|restart et)\b", t):
            return {"action": "restart", "params": {}}

        # ----- web arama -----
        m = re.search(r"^(.*?)\s+(?:ara|araştır|nedir|kimdir|ne demek)$", t)
        if m and m.group(1).strip():
            return {"action": "search", "params": {"query": m.group(1).strip()}}

        # ----- eşleşme yok: AI beynine devret -----
        return {"action": "ai_brain", "params": {"query": text.strip()}}
