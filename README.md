# Ali-512-javascript

# JARVIS2 — Tam Proje Dökümü

## PROJE HAKKINDA
Python 3.11, Windows, Tkinter tabanlı JARVIS tarzı yapay zeka masaüstü asistanı.
Groq API (llama-3.3-70b-versatile) ile doğal dil işleme, edge-tts ile ses çıkışı,
SpeechRecognition ile ses girişi, Selenium ile WhatsApp Web otomasyonu,
Home Assistant REST API ile akıllı ev kontrolü.

---

## KLASÖR YAPISI

```
jarvis2/
├── main.py
├── ui.py                          # Stark HUD v12.0 — Tkinter arayüzü (1797 satır)
├── core/
│   ├── orchestrator.py            # Merkezi yönetici
│   └── intent_parser.py           # Doğal dil → action parser
├── modules/
│   ├── whatsapp.py                # WhatsApp Web entegrasyonu (577 satır)
│   ├── smart_home.py              # Home Assistant REST API (Sonoff S60)
│   ├── ai_brain.py                # Groq API (llama-3.3-70b) function calling
│   ├── daily_planner.py           # Dinamik günlük plan üretici
│   ├── google_search.py           # Web arama
│   ├── system_control.py          # Windows sistem kontrolü
│   └── proactive.py               # Proaktif görev yöneticisi
├── voice/
│   ├── input.py                   # SpeechRecognition + sürekli dinleme
│   └── output.py                  # edge-tts + pyttsx3 (offline fallback)
├── memory/
│   └── manager.py                 # JSON tabanlı bellek yöneticisi
├── config/
│   └── settings.json              # Ayarlar
└── .env                           # API key'ler
```

---

## ÇALIŞAN ÖZELLİKLER

### 1. UI (ui.py) — Stark HUD v12.0
- 8 sekme: TERMİNAL, WHATSAPP, LOG, GEÇMİŞ, NOTLAR, YAPILACAK, HATIRLATICI, İSTATİSTİK, TAKVİM
- Sol panel: Analog saat + dijital saat, CPU/RAM/DISK/PİL çubukları, akıllı ev durumu, 10 hızlı erişim butonu, AĞ RADARI, son aramalar, istatistik mini, bildirimler
- Arc Reaktör animasyonu: 3 bağımsız dönen ring, parçacık sistemi, hex grid, scan line, veri akışı, tıklamada genişleyen halkalar, 8 yönlü enerji ışını
- Radar animasyonu: 16 trail katmanı, hedef tespit efekti
- Ses dalgası animasyonu: mikrofon/işleme modunda bar, normal modda sakin dalga
- 6+1 tema: CYAN, GREEN, RED, GOLD, PURPLE, MATRIX, ORANGE
- Boot sequence: Sıralı başlangıç mesajları
- Özellikler: Autocomplete popup, komut geçmişi (↑↓), Tab tamamlama, drag & drop pencere, maximize, toast bildirimleri, sağ tık menüsü, chat arama kutusu, export (JSON/TXT), hatırlatıcı dialog, emoji picker
- Takvim sekmesi: Aylık görünüm, ay navigasyonu, bugün vurgusu, hafta sonları kırmızı
- TODO sekmesi: Öncelik seçimi (yüksek/orta/normal), filtre, tamamlandı işaretleme, kalıcı kayıt
- Hatırlatıcı sekmesi: Aktif hatırlatıcı listesi, hazır öneri butonları
- Pil durumu: Topbar'da şarj ikonu ve yüzde

### 2. Orchestrator (core/orchestrator.py)
- Intent parser → action yönlendirme
- Kısa süreli bağlam hafızası (last_contact, last_query, last_app vb.)
- Çeşitli cevap listeleri (GREET, ACK, DONE, NOT_FOUND, UNKNOWN, SEARCH, OPEN, SEND)
- Hatırlatıcı sistemi (add/list/clear_reminders)
- Oturum istatistikleri (commands, searches, messages, voice_cmds, uptime)
- Plugin callbacks (set_search_callback, set_contacts_callback, set_speak_callback, set_notify_callback)
- Sesli dinleme yönetimi (start/stop_voice_mode)
- Ayarlar yenileme (reload_settings)

### 3. Intent Parser (core/intent_parser.py)
Tanınan action'lar:
- time, date, greet, help, exit
- search, translate
- morning_routine, stats
- reminder, list_reminders, clear_reminders
- whatsapp_open, whatsapp_contacts, whatsapp_unread, whatsapp_last_messages
- whatsapp_group, whatsapp_search_and_ask, whatsapp
- add_contact, list_contacts
- open_app, close_app, shutdown, restart
- ai_brain (priz/lamba/genel AI sorgusu)

### 4. WhatsApp (modules/whatsapp.py) — Selenium yok, subprocess tabanlı
- open_web() — WhatsApp Web'i Chrome ile açar (ayrı session klasörü)
- send_message(contact, message) — wa.me deep link ile direkt sohbete gider, mesaj hazır gelir
- broadcast_message(contacts, message) — toplu mesaj
- broadcast_to_favorites(message) — favorilere toplu mesaj
- schedule_message(contact, message, seconds) — zamanlanmış mesaj
- import_contacts_from_text(raw) — CSV/metin formatından toplu kişi ekleme
- export_contacts_to_text() — rehberi metin olarak dışa aktar
- Mesaj şablonları (10 hazır + özelleştirilebilir)
- Kişi notları, favoriler, mesaj logu, istatistikler
- Numara doğrulama
- "Ona/son kişiye tekrar yaz" bağlam desteği

### 5. Ses Çıkışı (voice/output.py)
- edge-tts ile online TTS (EmelNeural Türkçe, SoniaNeural İngilizce)
- Bağlantı yoksa pyttsx3 ile offline fallback
- Blocking/non-blocking konuşma, kuyruk sistemi
- Sessize alma (toggle_mute), ses seviyesi ayarı
- settings.json'dan canlı ayar okuma (tts_rate, tts_pitch, tts_voice)

### 6. Ses Girişi (voice/input.py)
- SpeechRecognition + Google Speech API
- Sürekli dinleme modu (require_wake_word=True)
- Uyanma kelimesi: "jarvis" — "jarvis priz aç" tek nefeste söylenince direkt işlenir
- Pause/resume (JARVIS konuşurken kendini duymasın)
- Periyodik kalibrasyon, durum callback'i

### 7. AI Brain (modules/ai_brain.py)
- Groq API, llama-3.3-70b-versatile (fallback: llama-3.1-8b-instant)
- Function calling ile priz kontrolü (turn_on/off/get_state)
- daily_briefing(): tarih/saate göre dinamik günlük plan
- Otomatik model fallback (kota doluşunda sıradaki modele geçer)

### 8. Akıllı Ev (modules/smart_home.py)
- Home Assistant REST API (Sonoff S60)
- Çoklu cihaz: config/smart_home_devices.json
- turn_on/off/toggle/get_state/get_power
- Zamanlayıcı: schedule_turn_off/on, cancel_timer
- turn_on_all/turn_off_all
- check_connection(), add_device(), remove_device()

### 9. Daily Planner (modules/daily_planner.py)
- AI varsa Groq'tan dinamik plan (sabit programa bağlı değil)
- AI yoksa zaman dilimine göre (sabah/öğle/akşam/gece) rastgele yerel mesaj

### 10. Memory Manager (memory/manager.py)
- JSON tabanlı kalıcı bellek
- list_contacts(), add_contact(), log_interaction()

---

## AYARLAR (config/settings.json)
```json
{
  "assistant_name": "JARVIS",
  "wake_word": "jarvis",
  "language": "tr-TR",
  "tts_voice": "tr-TR-EmelNeural",
  "tts_rate": 170,
  "tts_pitch": "+0Hz",
  "tts_volume": 1.0,
  "owner_name": "Efendim",
  "search_results_count": 3
}
```

## .env
```
GROQ_API_KEY=gsk_...
HOME_ASSISTANT_URL=http://localhost:8123
HOME_ASSISTANT_TOKEN=...
OWM_API_KEY=...        # Opsiyonel, hava durumu için
OWM_CITY=Istanbul      # Opsiyonel
```

---

## KOMUTLAR (Kullanıcı ne söyleyebilir)

- saat kaç / tarih → Zaman bilgisi
- günaydın / günlük plan → Groq ile dinamik günlük plan
- [konu] ara / [konu] nedir → Web arama
- whatsapp aç → WhatsApp Web'i açar
- whatsapp kişileri listele → Rehberdeki kişileri gösterir
- [kişi]e [mesaj] yaz → O kişinin sohbetini açar, mesaj hazır
- priz aç/kapat/durumu → Sonoff S60 kontrolü
- chrome/youtube/spotify aç → Uygulama/site açma
- [uygulama] kapat → Uygulama kapatma
- sistemi kapat → Windows shutdown
- 10 dakika sonra [mesaj] hatırlat → Hatırlatıcı
- istatistik → Oturum istatistikleri
- jarvis [komut] → Sesli komut (uyanma kelimesi)
- /theme CYAN|GREEN|RED|GOLD|PURPLE|MATRIX|ORANGE → Tema değiştir
- /help /clear /exit /export /settings → UI komutları

---

## KURULUM
```
pip install tkinter psutil groq edge-tts pygame pyttsx3 SpeechRecognition
pip install selenium webdriver-manager python-dotenv requests
pip install pyaudio
```

Docker ile Home Assistant:
```
docker run -d --name homeassistant -p 8123:8123 -v /path/to/config:/config ghcr.io/home-assistant/home-assistant:stable
```

---

## ÇALIŞTIRILMASI
```
python main.py
```

---

## BİLİNEN KISITLAMALAR
- WhatsApp: Selenium olmadığı için mesaj otomatik gönderilmiyor, kullanıcı Enter'a basıyor
- Okunmamış mesajlar/son mesajlar: WhatsApp Web açılıyor, içerik okunamıyor
- Watch Fit 2 entegrasyonu: HarmonyOS Lite kapalı sistem, direkt entegrasyon yok
- Telegram bot: kullanıcı isteği üzerine eklenmedi

---

## GELİŞTİRİLEBİLECEKLER (Öneri)
- ElevenLabs API ile gerçek JARVIS sesi
- Home Assistant Companion App + notify servisi (saate bildirim)
- Google Calendar entegrasyonu
- Flask + PWA ile mobil erişim (Tailscale VPN üzerinden)

---

## v2 GERÇEKLEME DURUMU (kod artık `jarvis2/` altında)

Dökümantasyondaki yapı çalışan Python koduna dönüştürüldü. Tüm modüller
eksik paket/anahtar durumunda çökmeden çalışır (graceful degradation).

### Çalıştırma
```bash
cd jarvis2
pip install -r requirements.txt      # opsiyonel paketler için
cp .env.example .env                  # anahtarlarınızı girin
python main.py                        # Stark HUD (varsayılan)
python main.py --console              # terminal modu
python main.py --voice                # terminal + sesli dinleme
```

### Testler
```bash
cd jarvis2
python -m unittest discover tests     # 19 birim testi
```

### Uygulanan modüller
| Modül | Durum | Not |
|-------|-------|-----|
| `ui.py` (Stark HUD) | ✅ | Arc reaktör, 10 sekme, 7 tema, animasyonlar, AYARLAR |
| `core/intent_parser.py` | ✅ | Kural tabanlı TR parser |
| `core/orchestrator.py` | ✅ | Action yönlendirme, bağlam, istatistik |
| `modules/ai_brain.py` | ✅ | Groq + function calling + model fallback |
| `modules/smart_home.py` | ✅ | Home Assistant REST, zamanlayıcı, çoklu cihaz |
| `modules/whatsapp.py` | ✅ | wa.me + pywhatkit ile OTOMATİK gönderim |
| `modules/weather.py` | ✅ | OpenWeatherMap widget'ı (önbellekli) |
| `modules/google_search.py` | ✅ | DuckDuckGo API ile gerçek sonuç (anahtarsız) |
| `modules/system_control.py` | ✅ | Ses, kilit, uyku, ekran görüntüsü, medya tuşları |
| `modules/proactive.py` | ✅ | Düşük pil + zamanı gelen hatırlatıcı bildirimi |
| `modules/bluetooth_manager.py` | ✅ | BT cihaz keşfi + JARVIS sesini BT hoparlör/kulaklığa yönlendirme |
| `modules/daily_planner.py` | ✅ | AI'lı/yerel dinamik plan |
| `memory/manager.py` | ✅ | Kişi/geçmiş/hatırlatıcı/not/todo (JSON) |
| `voice/output.py` | ✅ | edge-tts + pyttsx3 fallback |
| `voice/input.py` | ✅ | SpeechRecognition + uyanma kelimesi |

### Yeni komut örnekleri (v2)
- `ekranı kilitle` · `ekran görüntüsü al` · `uyku moduna al`
- `ses seviyesi 50` · `sesi kıs` · `bilgisayarın sesini kapat`
- `sonraki şarkı` · `müziği duraklat`
- `hava durumu` · `[konu] ara` (artık gerçek metin cevabı döner)
- `bluetooth tara` · `ses cihazlarını listele` · `eşleşmiş cihazlar`
- `hoparlörden konuş` · `buradan konuş` · `sesi varsayılana al`

### Bluetooth ile "oradan konuşma" — nasıl çalışır?
1. Cihazı (hoparlör/kulaklık) **bir kez Windows'ta eşleştirin** (işletim sistemi kısıtlaması).
2. HUD → **BLUETOOTH** sekmesi → **Ses Cihazları** ile bağlı cihazları listeleyin.
3. Cihazı seçip **Buradan Konuş**'a basın (veya "hoparlörden konuş" deyin).
4. JARVIS'in sesi artık o cihaza gider. **Varsayılan** ile geri alırsınız.

JARVIS sesi iki yolla yönlendirilir: (a) sistem varsayılan ses çıkışını değiştirerek
(pygame/pyttsx3 için), (b) `sounddevice` ile doğrudan hedef cihaz indeksine çalarak.
BLE taraması `bleak`, ses çalma `sounddevice`+`miniaudio` gerektirir (hepsi opsiyonel).
</content>
