# 🤖 Binance TR Coin Bot

Katmanlı mimarili, gerçek zamanlı WebSocket beslemeli, walk-forward optimizasyonlu,
Monte Carlo doğrulamalı, kurumsal risk yönetimli kripto alım-satım botu.
**Hiçbir harici paket gerektirmez** — Node.js 18+ yeterlidir (WebSocket akışı
için 21+; yoksa otomatik REST'e düşer).

> ⚠️ **YASAL UYARI:** Kripto para alım-satımı yüksek risk içerir ve paranızın tamamını
> kaybetmenize yol açabilir. Bu bot eğitim amaçlıdır, yatırım tavsiyesi değildir.
> Geçmiş performans gelecekteki sonuçların garantisi değildir. Canlı moda geçmeden önce
> **mutlaka** backtest + optimizasyon + paper modda uzun süre test edin. Ayrıca Binance
> TR'nin Türkiye'deki güncel hizmet/lisans durumunu ve API dokümantasyonunu doğrulayın.

## Yetenekler

**Veri ve yürütme**
- 📡 **WebSocket kline akışı**: gerçek zamanlı mum güncellemeleri; kopunca üstel geri çekilmeyle yeniden bağlanır, akış bayatlarsa **şeffaf REST fallback** — motor kaynağı bilmez
- 🔁 **Tek kod yolu**: backtest, optimizasyon ve canlı işlem aynı `Engine`/`RiskManager`/`Portfolio` sınıflarından geçer
- 🧩 **6 takılabilir strateji**: `ema_rsi`, `macd`, `bollinger`, `donchian`, `supertrend` + **`confluence` (konsensüs)**: birden çok strateji oylar, ancak mutabakatta işlem açılır — tek göstergenin yanıltmasına karşı filtre
- 🎯 **Sembol başına strateji**: `SYMBOLS=BTCTRY:ema_rsi,ETHTRY:supertrend` — çoklu strateji portföyü
- 📣 **Sinyal modu**: `TRADE_MODE=signal` — işlem açmadan sadece Telegram/Discord'a sinyal gönderir
- 🕐 **Borsa saati senkronizasyonu** + canlı modda başlangıçta **hesap doğrulaması**
- 📰 **Haber duyarlılık filtresi**: bir coine girmeden önce güncel haber başlıklarını tarar (CryptoPanic API veya RSS); hack/yasak/dava/çöküş gibi güçlü olumsuz haber akışında girişi **veto eder** — bir koruma filtresidir, tek başına alım yapmaz. Manuel inceleme: `npm run news BTCTRY`

**Canlı işlem güvenilirliği (gerçek para katmanı)**
- 🧾 **Hesap mutabakatı**: canlı modda bot durumu ile borsa bakiyeleri periyodik karşılaştırılır; sapma toleransı aşılırsa uyarı (isteğe bağlı yeni işlemleri durdurma)
- 🆔 **İdempotent emir kimlikleri**: ağ hatasında emir aynı `clientOrderId` ile tekrarlanır — kayıp yanıt yüzünden **çift dolum önlenir**
- 🔌 **API devre kesici**: art arda API hatasında yeni girişler geçici durur — borsa/ağ sorununda kör emir denenmez
- 💧 **Likidite/hacim filtresi**: ortalama hacmin altındaki ince piyasada giriş yok (kötü dolumdan korunma)
- 🕰️ **İşlem seansı filtresi**: düşük likidite saatlerinde (UTC saat/gün penceresi) giriş engellenir
- 🔕 **Bildirim kısıtlama**: kritik olmayan uyarılarda spam önleme

**Zarar sınırlama (minimum kayıp)**
- 🛑 **ACİL FREN (kill-switch)**: toplam sermaye zirveden `MAX_TOTAL_DRAWDOWN_PCT` düşerse bot yeni işlem açmayı **kalıcı olarak** durdurur (yeniden başlatmada da korunur) — en güçlü sermaye koruması
- 📏 **Risk bazlı boyutlama**: işlem başına sermayenin sadece %1'i riske edilir (ayarlanabilir)
- ⚖️ **Ödül/risk zorlaması**: `MIN_RR` ile TP/SL oranı düşükse bot hiç başlamaz
- 🌊 **ATR (volatiliteye uyumlu) stoplar** + **volatilite bekçisi**: çılgın piyasada giriş engellenir
- ⏳ **Zaman aşımı çıkışı**: N mumdur kârsız bekleyen "ölü" pozisyon kapatılır
- 🧭 **HTF trend filtresi** + 📐 **ADX rejim filtresi**: düşüş trendinde ve testere piyasada işlem yok
- 🧺 **Portföy limitleri**: maks. pozisyon sayısı + maruziyet tavanı + minimum emir tutarı
- 🔗 **Korelasyon koruması**: açık pozisyonla birlikte hareket eden sembolde (örn. BTC↔ETH) ikinci pozisyon açılmaz — aynı riske iki kez girilmez
- 🧪 **Veri sağlığı bekçisi**: tek turda aşırı fiyat sıçraması (veri aksaklığı) o turu iptal eder — bozuk fiyatla stop/alım tetiklenmez
- ⛔ **Günlük zarar limiti + ardışık zarar soğuması**: kötü günde bot kendini durdurur

**Kâr koruma (maksimum kazanç kilitleme)**
- 🔒 **Erken başabaş stopu**: kâr `BREAKEVEN_TRIGGER_PCT`'ye bir kez ulaşınca stop girişe çekilir — **pozisyon matematiksel olarak artık zarar edemez**
- 🕯️ **Chandelier stop** (`TRAILING_MODE=atr`): zirveden N×ATR sarkınca kâr kilitlenir — trendin nefes almasına izin verir, dönüşte kârı bırakmaz
- ✂️ **Kısmi kâr alma (scale-out)**: ilk hedefte pozisyonun yarısı nakde döner, kalan koşar
- 🔺 **Piramitleme (scale-in)**: kazanan pozisyona küçülen kademelerle ekleme
- 🧮 **Tam tur muhasebe**: K/Z hesabına giriş + çıkış komisyonu ve kayma dahildir

**Araştırma araçları**
- ⏪ **Backtest**: maks. düşüş, Sharpe, **Sortino, CAGR, Calmar, piyasada kalma oranı, en uzun zarar serisi** + CSV dışa aktarımı + **maliyet duyarlılık testi** (2× komisyonda strateji ayakta mı?)
- 🎲 **Monte Carlo sağlamlık analizi**: işlem sırası 1000 kez karıştırılır — getiri/düşüş dağılımı (p5/p50/p95) ve **iflas olasılığı** raporlanır; şanslı sıralamaya bağımlı sonuçlar ifşa edilir
- 🔬 **Walk-forward optimizasyon**: parametreler eğitim diliminde aranır, görülmemiş test diliminde doğrulanır — **aşırı uyum (overfitting) uyarısıyla**
- 💽 **Kline disk önbelleği**: optimizasyondaki yüzlerce koşum tek indirmeyle beslenir

**Operasyon**
- 📊 **Web izleme paneli**: özsermaye + mum grafiği ve işlem işaretleri + `/api/health` + **Prometheus `/metrics`** (Grafana/Alertmanager entegrasyonu)
- 🩺 **`npm run doctor`**: canlıya geçmeden ortam tanılaması — Node sürümü, API erişimi, saat sapması, sembol doğrulama, yazma izinleri, anahtar kontrolü
- 📄 **HTML performans raporu**: `npm run report` — işlem günlüğünden kümülatif K/Z, günlük K/Z ve sembol bazlı tek dosyalık rapor üretir
- 💾 **Atomik durum kalıcılığı**: yeniden başlatmada pozisyonlar diskten kurtarılır
- 📱 **Telegram + Discord**: işlem bildirimleri, **günlük özet raporu**, ardışık hata alarmı
- 🪵 **JSON log formatı** (`LOG_FORMAT=json`): Loki/ELK/CloudWatch gibi log toplayıcılara hazır
- 🐳 **Docker + docker-compose + pm2** dağıtım dosyaları, **GitHub Actions CI**
- ✅ **80 birim/entegrasyon testi** (`npm test`)

## Kurulum

```bash
node --version        # >= 18 (WebSocket icin >= 21 onerilir)
cp .env.example .env  # ayarlari duzenleyin
npm test              # 80 testin gectigini dogrulayin
npm run doctor        # ortam tanilamasi (API erisimi, saat, izinler)
```

### Hazır profiller (önerilen başlangıç)

```bash
# Guvenli: tum koruma katmanlari acik, kucuk sermaye (2-10k TRY) icin
cp profiles/guvenli.env .env

# Dengeli: koruma + buyume dengesi, kismi kar + piramitleme birlikte
cp profiles/dengeli.env .env
```

Güvenli profil felsefesi: **az ama seçici işlem** (HTF + ADX + volatilite filtresi),
işlem başına %1 risk, kâr görülür görülmez başabaş kilidi, chandelier ile kâr takibi,
%12 toplam düşüşte acil fren. Kârı garanti etmez — kaybı sınırlar ve kazancı korur.

## Önerilen iş akışı

```bash
# 1. Stratejiyi gecmiste olcun
npm run backtest                          # .env ayarlariyla
node src/backtest.js BTCTRY 1h 1000 macd  # sembol/aralik/mum/strateji

# 2. Parametreleri walk-forward ile optimize edin (asiri uyuma dikkat!)
node src/optimize.js BTCTRY 1h 1000 ema_rsi

# 3. En iyi parametreleri .env'e yazin, paper modda canli izleyin
DASHBOARD_PORT=8080 npm start             # panel: http://127.0.0.1:8080

# 4. Haftalarca paper sonucu tatmin ediciyse kucuk tutarla live'a gecin
```

### Optimizasyon çıktısı örneği

```
#1 emaFast=9 emaSlow=34 stopLossPct=2 takeProfitPct=6
   Egitim: getiri %  12.4 | dusus %  3.1 | sharpe  1.42 | islem  18
   Test  : getiri %   4.2 | dusus %  2.8 | sharpe  0.91 | islem   7

#2 emaFast=5 emaSlow=21 stopLossPct=1.5 takeProfitPct=3
   Egitim: getiri %  15.1 | dusus %  2.9 | sharpe  1.61 | islem  31
   Test  : getiri %  -3.4 | dusus %  5.2 | sharpe -0.44 | islem  12
   ⚠️  ASIRI UYUM SUPHESI: egitimde iyi, testte zayif - bu parametrelere guvenmeyin.
```

## Live mod (⚠️ gerçek para)

1. Binance TR'de API anahtarı oluşturun: sadece **spot trade** yetkisi,
   **çekim yetkisi asla**, IP kısıtlaması ekleyin.
2. `.env` → `BINANCE_TR_API_KEY`, `BINANCE_TR_API_SECRET`, `TRADE_MODE=live`.
3. `npm start` — bot başlamadan önce 10 saniyelik iptal süresi tanır.

> Canlı emir uç noktaları Binance TR Open API'ye göre yazılmıştır (`/open/v1/orders`).
> API sözleşmesi değişmiş olabilir — canlıya geçmeden önce
> [resmî dokümantasyonla](https://www.trbinance.com/apidocs) karşılaştırın.
> Tüm borsa entegrasyonu tek dosyadadır: `src/exchange/binanceTr.js`.

## 7/24 çalıştırma

```bash
# Docker (onerilen)
docker compose up -d --build
docker compose logs -f

# veya pm2
pm2 start ecosystem.config.cjs
```

Bot `SIGTERM`'de durumunu kaydederek kapanır; yeniden başlatmada açık pozisyonlar
`data/state.json`'dan geri yüklenir.

## Mimari

```
src/
├── index.js                  # Giris: WebSocket besleme + coklu sembol dongusu + panel + durum
├── backtest.js               # Backtest CLI (CSV disa aktarimli)
├── optimize.js               # Walk-forward optimizasyon CLI
├── config.js                 # .env yukleme + dogrulama (hatali ayarla baslamaz)
├── logger.js                 # Seviyeli log + trades.jsonl denetim izi
├── state.js                  # Atomik durum kaliciligi (data/state.json)
├── notifier.js               # Telegram + Discord bildirimleri (hata botu durdurmaz)
├── report.js                 # HTML performans raporu - sembol + strateji kirilimli
├── doctor.js                 # Ortam tanilamasi (npm run doctor)
├── dashboard.js              # Web paneli: ozsermaye + mum grafigi + islem isaretleri
├── indicators.js             # SMA, EMA, RSI, MACD, Bollinger, ATR, Donchian, SuperTrend, ADX
├── strategies/               # Kayit defteri + 6 strateji (confluence dahil, ortak sozlesme)
├── core/
│   ├── engine.js             # Karar dongusu - backtest ve canli icin TEK kod yolu
│   ├── portfolio.js          # Tam tur muhasebe: bakiye, pozisyon, kismi satis, K/Z defteri
│   ├── riskManager.js        # Boyutlama, percent/ATR stoplar, kismi kar, devre kesiciler
│   ├── trendFilter.js        # HTF EMA trend filtresi + ADX rejim filtresi
│   ├── backtester.js         # Yeniden kullanilabilir backtest cekirdegi
│   ├── optimizer.js          # Izgara arama + walk-forward dogrulama
│   ├── monteCarlo.js         # Islem sirasi karistirma - saglamlik/iflas analizi
│   ├── correlation.js        # Pearson korelasyon + cifte risk korumasi
│   ├── sessionFilter.js      # Islem seansi (UTC saat/gun) filtresi
│   ├── liquidity.js          # Hacim/likidite filtresi
│   ├── apiHealth.js          # API devre kesici (circuit breaker)
│   ├── reconciler.js         # Hesap mutabakati (ic durum <-> borsa bakiyesi)
│   ├── newsSentiment.js      # Haber cekme + anahtar kelime duyarlilik puanlama
│   └── metrics.js            # Drawdown, Sharpe, Sortino, CAGR, Calmar, kar faktoru
└── exchange/
    ├── wsFeed.js             # WebSocket kline akisi + otomatik REST fallback
    ├── market.js             # REST veri - yeniden deneme, rate-limit, disk onbellegi
    ├── brokers.js            # PaperBroker / LiveBroker (ayni arayuz) + LOT_SIZE
    └── binanceTr.js          # Binance TR Open API imzali istekler + saat senkronu
test/                         # 80 birim + entegrasyon testi (node:test)
profiles/                     # Hazir .env profilleri: guvenli.env, dengeli.env
.github/workflows/ci.yml      # Her push'ta sozdizimi + test kosan CI
Dockerfile / docker-compose.yml / ecosystem.config.cjs
```

**Katman kuralları:** Stratejiler sadece sinyal üretir (emir bilmez). `RiskManager`
tüm koruma kurallarının tek sahibidir. `Portfolio` sadece muhasebedir. `Engine`
hangi broker'la ve hangi veri kaynağıyla konuştuğunu bilmez.

## Önemli ayarlar (.env)

Tam liste `.env.example` içinde. Öne çıkanlar:

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `TRADE_MODE` | `paper` | `paper` = simülasyon, `live` = gerçek emir |
| `SYMBOLS` | `BTCTRY` | Çoklu + sembol başına strateji: `BTCTRY:ema_rsi,ETHTRY:macd` |
| `STRATEGY` | `ema_rsi` | 5 strateji + `confluence` (konsensüs oylaması) |
| `SIZING_MODE` | `percent` | `percent` \| `risk` (stop mesafesine göre) |
| `STOP_MODE` | `percent` | `percent` \| `atr` (volatiliteye uyumlu) |
| `PARTIAL_TP_PCT` | `0` | Kısmi kâr alma eşiği (0 = kapalı) |
| `PYRAMID_MAX_ADDONS` | `0` | Piramit kademe sayısı (0 = kapalı) |
| `ADX_FILTER` | `false` | Trendsiz piyasada işlem engelleme |
| `MAX_OPEN_POSITIONS` | `0` | Eşzamanlı pozisyon limiti (0 = sınırsız) |
| `MAX_TOTAL_DRAWDOWN_PCT` | `0` | **Acil fren**: zirveden bu kadar düşüşte bot durur |
| `BREAKEVEN_TRIGGER_PCT` | `0` | Erken başabaş kilidi eşiği |
| `TRAILING_MODE` | `percent` | `atr` = chandelier kâr kilitleme |
| `MAX_HOLD_CANDLES` | `0` | Kârsız pozisyon zaman aşımı |
| `MIN_RR` | `0` | Minimum ödül/risk oranı zorlaması |
| `CORRELATION_MAX` | `0` | Korele sembolde çifte pozisyon engeli (örn. 0.85) |
| `RECONCILE` | `true` | Canlı modda hesap mutabakatı (durum ↔ borsa) |
| `VOLUME_FILTER` | `false` | Düşük hacimli ince piyasada giriş engelleme |
| `SESSION_FILTER` | `false` | UTC saat/gün penceresiyle giriş kısıtlama |
| `API_MAX_CONSECUTIVE_ERRORS` | `5` | API devre kesici eşiği |
| `NEWS_FILTER` | `false` | Girişten önce haber taraması (olumsuz haberde veto) |
| `NEWS_SOURCE` | `cryptopanic` | `cryptopanic` (API) \| `rss` (akış URL'leri) |
| `DISCORD_WEBHOOK_URL` | — | Discord bildirimleri (isteğe bağlı) |
| `HTF_FILTER` | `false` | Üst zaman dilimi trend filtresi |
| `TRAILING_STOP_PCT` | `0` | İz süren stop (0 = kapalı) |
| `MAX_DAILY_LOSS_PCT` | `5` | Günlük zarar devre kesicisi |
| `WS_ENABLED` | `true` | WebSocket akışı (Node 21+) |
| `DASHBOARD_PORT` | `0` | İzleme paneli portu (0 = kapalı) |
| `TELEGRAM_BOT_TOKEN` | — | İşlem bildirimleri (isteğe bağlı) |

## Güvenlik notları

- `.env`, `data/`, `logs/` git'e girmez; panel yalnızca `127.0.0.1`'e bağlanır.
- API anahtarına **yalnızca spot işlem** yetkisi verin; çekim yetkisi vermeyin; IP kısıtlayın.
- Küçük tutarlarla başlayın; devre kesici loglarını (`logs/bot.log`) düzenli kontrol edin.
- Optimizasyon sonuçlarında test dilimi zayıfsa o parametrelerle canlıya çıkmayın.
