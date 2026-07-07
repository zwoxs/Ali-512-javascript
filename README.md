# 🤖 Binance TR Coin Bot

Katmanlı mimarili, gerçek zamanlı WebSocket beslemeli, walk-forward optimizasyonlu,
kurumsal risk yönetimli kripto alım-satım botu. **Hiçbir harici paket gerektirmez** —
Node.js 18+ yeterlidir (WebSocket akışı için 21+; yoksa otomatik REST'e düşer).

> ⚠️ **YASAL UYARI:** Kripto para alım-satımı yüksek risk içerir ve paranızın tamamını
> kaybetmenize yol açabilir. Bu bot eğitim amaçlıdır, yatırım tavsiyesi değildir.
> Geçmiş performans gelecekteki sonuçların garantisi değildir. Canlı moda geçmeden önce
> **mutlaka** backtest + optimizasyon + paper modda uzun süre test edin. Ayrıca Binance
> TR'nin Türkiye'deki güncel hizmet/lisans durumunu ve API dokümantasyonunu doğrulayın.

## Yetenekler

**Veri ve yürütme**
- 📡 **WebSocket kline akışı**: gerçek zamanlı mum güncellemeleri; kopunca üstel geri çekilmeyle yeniden bağlanır, akış bayatlarsa **şeffaf REST fallback** — motor kaynağı bilmez
- 🔁 **Tek kod yolu**: backtest, optimizasyon ve canlı işlem aynı `Engine`/`RiskManager`/`Portfolio` sınıflarından geçer
- 🧩 **Takılabilir stratejiler**: `ema_rsi` (trend), `macd` (momentum), `bollinger` (ortalamaya dönüş) — ortak sözleşme, tek dosyayla yenisi eklenir

**Risk yönetimi**
- 📏 **Risk bazlı boyutlama**: pozisyon büyüklüğü = riske edilen sermaye / stop mesafesi
- 🌊 **ATR (volatiliteye uyumlu) stoplar**: `STOP_MODE=atr` ile stop/hedef, giriş anındaki piyasa oynaklığına göre belirlenir — sakin piyasada dar, dalgalı piyasada geniş
- 🧭 **Üst zaman dilimi trend filtresi**: `HTF_FILTER=true` ile düşüş trendinde AL sinyalleri engellenir
- 🛑 **İz süren stop, günlük zarar limiti, ardışık zarar soğuması**: üç bağımsız devre kesici
- 🧮 **Tam tur muhasebe**: K/Z hesabına giriş + çıkış komisyonu ve kayma dahildir

**Araştırma araçları**
- ⏪ **Backtest**: maks. düşüş, Sharpe, kâr faktörü + özsermaye/işlem **CSV dışa aktarımı**
- 🔬 **Walk-forward optimizasyon**: parametreler eğitim diliminde aranır, görülmemiş test diliminde doğrulanır — **aşırı uyum (overfitting) uyarısıyla**

**Operasyon**
- 📊 **Web izleme paneli**: özsermaye grafiği, açık pozisyonlar, işlem geçmişi, devre kesici durumu (`DASHBOARD_PORT=8080`)
- 💾 **Atomik durum kalıcılığı**: yeniden başlatmada pozisyonlar diskten kurtarılır
- 📱 **Telegram bildirimleri**, JSONL denetim izi, seviyeli loglama
- 🐳 **Docker + docker-compose + pm2** dağıtım dosyaları, **GitHub Actions CI**
- ✅ **32 birim/entegrasyon testi** (`npm test`)

## Kurulum

```bash
node --version        # >= 18 (WebSocket icin >= 21 onerilir)
cp .env.example .env  # ayarlari duzenleyin
npm test              # 32 testin gectigini dogrulayin
```

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
├── notifier.js               # Telegram bildirimleri (hata botu durdurmaz)
├── dashboard.js              # Yerlesik web izleme paneli (sadece 127.0.0.1)
├── indicators.js             # SMA, EMA, RSI, MACD, Bollinger, ATR - saf fonksiyonlar
├── strategies/               # Strateji kayit defteri + 3 strateji (ortak sozlesme)
├── core/
│   ├── engine.js             # Karar dongusu - backtest ve canli icin TEK kod yolu
│   ├── portfolio.js          # Tam tur muhasebe: bakiye, pozisyon, K/Z defteri
│   ├── riskManager.js        # Boyutlama, percent/ATR stoplar, devre kesiciler
│   ├── trendFilter.js        # Ust zaman dilimi EMA trend filtresi
│   ├── backtester.js         # Yeniden kullanilabilir backtest cekirdegi
│   ├── optimizer.js          # Izgara arama + walk-forward dogrulama
│   └── metrics.js            # Drawdown, Sharpe, kar faktoru
└── exchange/
    ├── wsFeed.js             # WebSocket kline akisi + otomatik REST fallback
    ├── market.js             # REST veri - yeniden deneme + rate-limit yonetimi
    ├── brokers.js            # PaperBroker / LiveBroker (ayni arayuz) + LOT_SIZE
    └── binanceTr.js          # Binance TR Open API imzali istekler (HMAC-SHA256)
test/                         # 32 birim + entegrasyon testi (node:test)
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
| `SYMBOLS` | `BTCTRY` | Virgülle çoklu: `BTCTRY,ETHTRY` |
| `STRATEGY` | `ema_rsi` | `ema_rsi` \| `macd` \| `bollinger` |
| `SIZING_MODE` | `percent` | `percent` \| `risk` (stop mesafesine göre) |
| `STOP_MODE` | `percent` | `percent` \| `atr` (volatiliteye uyumlu) |
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
