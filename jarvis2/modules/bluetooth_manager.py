"""Bluetooth Yöneticisi — cihaz keşfi, bağlantı ve ses yönlendirme.

JARVIS'in sesini bir Bluetooth hoparlör/kulaklığa yönlendirmenin amacı:
"bağlandığında oradan konuşabilmek". Bunun için iki mekanizma kullanılır:

  1. Sistem varsayılan ses çıkışını seçilen cihaza almak
     (Windows: AudioDeviceCmdlets / nircmd, Linux: pactl, Mac: SwitchAudioSource)
     → pygame/pyttsx3 ile çalan tüm ses otomatik o cihaza gider.
  2. sounddevice ile doğrudan hedef cihaz indeksine çalmak (VoiceOutput üzerinden).

ÖNEMLİ: Yeni bir cihazı sıfırdan EŞLEŞTİRMEK işletim sistemi düzeyinde
kısıtlıdır. Bu modül, işletim sisteminde önceden eşleştirilmiş cihazlara
bağlanır ve sesi oraya yönlendirir. BLE cihazlarını taramak için `bleak`,
ses cihazlarını listelemek için `sounddevice` (ikisi de opsiyonel) kullanılır.
"""
import platform
import subprocess

try:
    import sounddevice as _sd
    _SD_OK = True
except Exception:
    _SD_OK = False

try:
    import bleak  # noqa: F401
    _BLEAK_OK = True
except Exception:
    _BLEAK_OK = False

_IS_WIN = platform.system() == "Windows"
_IS_MAC = platform.system() == "Darwin"
_IS_LINUX = platform.system() == "Linux"


class BluetoothManager:
    def __init__(self, voice_output=None, memory=None):
        self.voice_output = voice_output
        self.memory = memory
        self.current_output = None  # yönlendirilen cihazın adı

    # ---------- yetenek raporu ----------
    def capabilities(self) -> dict:
        return {
            "ble_scan": _BLEAK_OK,
            "audio_list": _SD_OK,
            "platform": platform.system(),
        }

    # =================================================================
    #  KEŞİF
    # =================================================================
    def scan(self, timeout: float = 6.0) -> list:
        """Yakındaki BLE cihazlarını tarar. [{'name','address','rssi'}]"""
        if not _BLEAK_OK:
            return []
        import asyncio
        from bleak import BleakScanner

        async def _run():
            devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
            out = []
            for addr, (dev, adv) in devices.items():
                out.append({
                    "name": dev.name or adv.local_name or "Bilinmeyen",
                    "address": addr,
                    "rssi": getattr(adv, "rssi", None),
                })
            return out

        try:
            return asyncio.run(_run())
        except Exception:
            return []

    def list_paired(self) -> list:
        """İşletim sisteminde eşleştirilmiş/kayıtlı Bluetooth cihazları."""
        try:
            if _IS_WIN:
                ps = ("Get-PnpDevice -Class Bluetooth -Status OK | "
                      "Select-Object -ExpandProperty FriendlyName")
                r = subprocess.run(["powershell", "-c", ps],
                                   capture_output=True, text=True, timeout=15)
                return [{"name": l.strip()} for l in r.stdout.splitlines() if l.strip()]
            if _IS_LINUX:
                r = subprocess.run(["bluetoothctl", "devices"],
                                   capture_output=True, text=True, timeout=10)
                out = []
                for line in r.stdout.splitlines():
                    parts = line.split(" ", 2)  # "Device XX:.. Name"
                    if len(parts) == 3:
                        out.append({"name": parts[2].strip(), "address": parts[1]})
                return out
            if _IS_MAC:
                r = subprocess.run(["system_profiler", "SPBluetoothDataType"],
                                   capture_output=True, text=True, timeout=15)
                return [{"name": "macOS Bluetooth (system_profiler çıktısı)",
                         "raw": r.stdout[:2000]}]
        except Exception:
            pass
        return []

    def list_audio_outputs(self) -> list:
        """Çalma yapılabilen ses cihazları (bağlı BT hoparlör/kulaklıklar dahil).

        [{'index','name','channels','default'}]
        """
        if not _SD_OK:
            return []
        try:
            devices = _sd.query_devices()
            try:
                default_out = _sd.default.device[1]
            except Exception:
                default_out = None
            out = []
            for i, d in enumerate(devices):
                if d.get("max_output_channels", 0) > 0:
                    out.append({
                        "index": i,
                        "name": d["name"],
                        "channels": d["max_output_channels"],
                        "default": (i == default_out),
                    })
            return out
        except Exception:
            return []

    # =================================================================
    #  BAĞLANTI (önceden eşleştirilmiş cihazlar — en iyi çaba)
    # =================================================================
    def connect(self, name_or_addr: str) -> str:
        try:
            if _IS_LINUX:
                addr = self._resolve_linux_addr(name_or_addr)
                if not addr:
                    return f"'{name_or_addr}' eşleşmiş cihazlarda bulunamadı, Efendim."
                r = subprocess.run(["bluetoothctl", "connect", addr],
                                   capture_output=True, text=True, timeout=20)
                ok = "Connection successful" in r.stdout or "successful" in r.stdout
                return (f"{name_or_addr} bağlandı, Efendim." if ok
                        else f"{name_or_addr} bağlanamadı.")
            if _IS_MAC:
                r = subprocess.run(["blueutil", "--connect", name_or_addr],
                                   capture_output=True, text=True, timeout=20)
                return (f"{name_or_addr} bağlandı, Efendim." if r.returncode == 0
                        else "Bağlantı başarısız (blueutil gerekli).")
            if _IS_WIN:
                # Windows'ta klasik BT'yi komutla bağlamak kısıtlı; kullanıcı
                # bir kez eşleştirdiyse cihaz genelde otomatik bağlanır.
                return ("Windows'ta bağlantı, cihaz eşleştirildiğinde otomatik yapılır. "
                        "Sesi yönlendirmek için 'buradan konuş' / ses cihazı seçin, Efendim.")
        except Exception as e:
            return f"Bağlantı hatası: {e}"
        return "Bu platformda bağlantı desteklenmiyor, Efendim."

    def disconnect(self, name_or_addr: str) -> str:
        try:
            if _IS_LINUX:
                addr = self._resolve_linux_addr(name_or_addr) or name_or_addr
                subprocess.run(["bluetoothctl", "disconnect", addr],
                               capture_output=True, text=True, timeout=15)
                return f"{name_or_addr} bağlantısı kesildi, Efendim."
            if _IS_MAC:
                subprocess.run(["blueutil", "--disconnect", name_or_addr],
                               capture_output=True, text=True, timeout=15)
                return f"{name_or_addr} bağlantısı kesildi, Efendim."
        except Exception as e:
            return f"İşlem hatası: {e}"
        return "Bağlantı kesme bu platformda desteklenmiyor, Efendim."

    def _resolve_linux_addr(self, name_or_addr: str):
        if ":" in name_or_addr and len(name_or_addr) >= 17:
            return name_or_addr
        for d in self.list_paired():
            if name_or_addr.lower() in d.get("name", "").lower():
                return d.get("address")
        return None

    # =================================================================
    #  SESLİ KOMUTLA BAĞLAN + KONUŞ (tek adım)
    # =================================================================
    def connect_and_speak(self, spoken_name: str) -> str:
        """'kulaklığa bağlan' gibi bir komutta: cihazı çöz, bağlan ve sesi oraya al.

        Çözümleme sırası: takma ad → ses cihazı adı (kısmi) → eşleşmiş cihaz adı.
        """
        raw = (spoken_name or "").strip()
        if not raw:
            return "Hangi cihaza bağlanayım, Efendim?"

        resolved = self._resolve_device_name(raw)

        # önce (varsa) klasik bağlantıyı dene — Windows'ta bilgi mesajı döner
        connect_msg = ""
        try:
            connect_msg = self.connect(resolved)
        except Exception:
            pass

        # asıl amaç: sesi o cihaza yönlendir
        route_msg = self.set_speak_device(resolved)

        # ses cihazlarında bulunamadıysa yardımcı ol
        if "bulunamadı" in route_msg:
            outs = self.list_audio_outputs()
            if outs:
                names = ", ".join(o["name"] for o in outs[:6])
                return (f"'{raw}' adlı cihazı ses çıkışlarında bulamadım, Efendim. "
                        f"Şu cihazları görüyorum: {names}. "
                        f"Bir takma ad tanımlarsanız (örn. '{raw}' → gerçek ad) "
                        f"bir daha kolayca bağlanırım.")
            return route_msg

        # test sesi çal
        if self.voice_output:
            self.voice_output.speak(
                f"Bağlandım, Efendim. Artık {self.current_output} üzerinden konuşuyorum.",
                blocking=False)
        return route_msg

    def resolve_and_classify(self, spoken: str):
        """(kanonik_ad, tür) döndürür. tür: phone/headphone/speaker/unknown."""
        name = self._resolve_device_name(spoken)
        canon = self._canonical_name(name)
        if canon:
            return canon, self.classify_device(canon)
        # genel tür kelimesi mi? ("telefon","saat","hoparlör","kulaklık")
        spoken_klass = self.classify_device(self._clean_token(name))
        if spoken_klass != "unknown":
            match = self._first_device_of_type(spoken_klass)
            if match:
                return match, spoken_klass
            return name, spoken_klass  # tür biliniyor ama eşleşen cihaz yok
        return name, self.classify_device(name)

    def _first_device_of_type(self, klass: str):
        """Eşleşmiş/ses cihazları içinden verilen türdeki ilk cihazın adı."""
        names = []
        try:
            names += [d.get("name", "") for d in self.list_paired()]
        except Exception:
            pass
        try:
            names += [o.get("name", "") for o in self.list_audio_outputs()]
        except Exception:
            pass
        for n in names:
            if n and self.classify_device(n) == klass:
                return n
        return None

    def _canonical_name(self, name: str):
        """Kısmi adı, eşleşmiş cihaz veya ses çıkışı listesinden tam ada çevirir."""
        key = self._clean_token(name)
        pools = []
        try:
            pools += [d.get("name", "") for d in self.list_paired()]
        except Exception:
            pass
        try:
            pools += [o.get("name", "") for o in self.list_audio_outputs()]
        except Exception:
            pass
        # tam ifade
        low = name.lower().strip()
        for cand in pools:
            if low and low in cand.lower():
                return cand
        # kelime kelime
        for word in low.split():
            tok = self._clean_token(word)
            if len(tok) < 2:
                continue
            for cand in pools:
                if tok in cand.lower():
                    return cand
        return None

    def _resolve_device_name(self, spoken: str) -> str:
        """Konuşulan adı gerçek cihaz adına çevir (takma ad + ek temizleme)."""
        key = self._clean_token(spoken)

        # 1) takma ad tablosu
        if self.memory:
            aliases = self.memory.get_bt_aliases()
            # doğrudan
            if key in aliases:
                return aliases[key]
            # kısmi (takma ad da normalize edilerek)
            for alias, real in aliases.items():
                ak = self._clean_token(alias)
                if ak == key or ak in key or key in ak:
                    return real
        return spoken.strip()

    @staticmethod
    def _clean_token(word: str) -> str:
        """Küçült, kesme işaretini at, yönelme ekini ve ünsüz yumuşamasını geri al.

        Örn: "kulaklığa" -> ek "-a" atılır -> "kulaklığ" -> ğ→k -> "kulaklık".
        """
        w = word.strip().lower()
        if "'" in w or "’" in w:
            w = w.replace("’", "'").split("'")[0]
        # yaygın yönelme ekleri: -ya/-ye (sesli sonrası), -a/-e (sessiz sonrası)
        # Not: "-na/-ne" tampon eki köke dahil 'n'yi yanlışça silebildiği için yok
        #      (örn. "telefona" -> "telefon", "telefo" değil).
        for suf in ("ya", "ye", "a", "e"):
            if w.endswith(suf) and len(w) > len(suf) + 2:
                w = w[: -len(suf)]
                # ünsüz yumuşamasını geri çevir (kök sesi)
                mutate = {"ğ": "k", "g": "k", "b": "p", "c": "ç", "d": "t"}
                if w and w[-1] in mutate:
                    w = w[:-1] + mutate[w[-1]]
                break
        return w

    @staticmethod
    def classify_device(name: str) -> str:
        """Cihaz adından türünü tahmin eder: phone / headphone / speaker / unknown."""
        n = (name or "").lower()
        phone_kw = ("phone", "telefon", "iphone", "galaxy s", "galaxy a",
                    "galaxy note", "redmi", "pixel", "poco", "oneplus",
                    "huawei p", "huawei mate", "reno", "xperia")
        head_kw = ("airpods", "buds", "headphone", "kulaklık", "kulaklik",
                   "wh-", "wf-", "freebuds", "headset", "earphone", "earbud")
        speaker_kw = ("speaker", "hoparlör", "hoparlor", "jbl", "flip", "boom",
                      "soundbar", "charge", "go 3", "clip", "bose", "sony srs")
        for kw in phone_kw:
            if kw in n:
                return "phone"
        for kw in head_kw:
            if kw in n:
                return "headphone"
        for kw in speaker_kw:
            if kw in n:
                return "speaker"
        return "unknown"

    def set_alias(self, alias: str, device_name: str) -> str:
        if not self.memory:
            return "Takma ad kaydı için bellek modülü gerekli, Efendim."
        self.memory.set_bt_alias(alias, device_name)
        return f"Tamam Efendim: '{alias}' → {device_name} olarak kaydedildi."

    # =================================================================
    #  SES YÖNLENDİRME — "oradan konuş"
    # =================================================================
    def set_speak_device(self, name_or_index) -> str:
        """JARVIS'in sesini verilen ses cihazına yönlendirir."""
        target = self._match_audio_output(name_or_index)
        if not target:
            return f"'{name_or_index}' ses cihazlarında bulunamadı, Efendim."

        # 1) VoiceOutput'a doğrudan cihaz indeksi ver (sounddevice yolu)
        if self.voice_output and hasattr(self.voice_output, "set_output_device"):
            self.voice_output.set_output_device(target["index"], target["name"])

        # 2) Sistem varsayılanını da değiştirmeyi dene (pygame/pyttsx3 için)
        self._set_system_default(target["name"])

        self.current_output = target["name"]
        return f"Artık '{target['name']}' üzerinden konuşacağım, Efendim."

    def speak_here_test(self) -> str:
        if self.voice_output:
            msg = f"Ses testi. {self.current_output or 'varsayılan cihaz'} üzerinden konuşuyorum, Efendim."
            self.voice_output.speak(msg, blocking=False)
            return msg
        return "Ses çıkışı modülü yok, Efendim."

    def reset_to_default(self) -> str:
        if self.voice_output and hasattr(self.voice_output, "set_output_device"):
            self.voice_output.set_output_device(None, None)
        self.current_output = None
        return "Ses varsayılan cihaza döndürüldü, Efendim."

    def _match_audio_output(self, name_or_index):
        outputs = self.list_audio_outputs()
        if not outputs:
            return None
        # indeks ile
        try:
            idx = int(name_or_index)
            for o in outputs:
                if o["index"] == idx:
                    return o
        except (ValueError, TypeError):
            pass
        # isim ile (kısmi eşleşme) — tam ifade
        key = str(name_or_index).lower().strip()
        for o in outputs:
            if key and key in o["name"].lower():
                return o
        # kelime kelime dene ("jbl e" -> "jbl"), ekleri de temizleyerek
        for word in key.split():
            tok = self._clean_token(word)
            if len(tok) < 2:
                continue
            for o in outputs:
                if tok in o["name"].lower():
                    return o
        return None

    def _set_system_default(self, device_name: str) -> bool:
        try:
            if _IS_WIN:
                # AudioDeviceCmdlets varsa
                ps = (f"try {{ Set-AudioDevice -Name '{device_name}' -ErrorAction Stop }} "
                      f"catch {{ exit 1 }}")
                r = subprocess.run(["powershell", "-c", ps],
                                   capture_output=True, text=True, timeout=15)
                if r.returncode == 0:
                    return True
                # nircmd yedeği (PATH'te ise)
                subprocess.run(["nircmd", "setdefaultsounddevice", device_name, "1"],
                               capture_output=True, timeout=10)
                return True
            if _IS_LINUX:
                # cihaz adına karşılık gelen sink'i bulup varsayılan yap
                r = subprocess.run(["pactl", "list", "short", "sinks"],
                                   capture_output=True, text=True, timeout=10)
                for line in r.stdout.splitlines():
                    cols = line.split("\t")
                    if len(cols) >= 2:
                        subprocess.run(["pactl", "set-default-sink", cols[1]],
                                       capture_output=True, timeout=10)
                        break
                return True
            if _IS_MAC:
                subprocess.run(["SwitchAudioSource", "-s", device_name],
                               capture_output=True, timeout=10)
                return True
        except Exception:
            pass
        return False
