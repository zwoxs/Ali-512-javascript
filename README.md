# 🤖 Binance TR Coin Bot

EMA kesişimi + RSI filtresi stratejisiyle çalışan, zarar durdur / kâr al risk yönetimli
kripto alım-satım botu. **Hiçbir harici paket gerektirmez** — Node.js 18+ yeterlidir.

> ⚠️ **YASAL UYARI:** Kripto para alım-satımı yüksek risk içerir ve paranızın tamamını
> kaybetmenize yol açabilir. Bu bot eğitim amaçlıdır, yatırım tavsiyesi değildir.
> Geçmiş performans gelecekteki sonuçların garantisi değildir. Canlı moda geçmeden önce
> **mutlaka** paper (simülasyon) modda uzun süre test edin. Ayrıca Binance TR'nin
> Türkiye'deki güncel hizmet/lisans durumunu ve API dokümantasyonunu kendiniz doğrulayın.

## Özellikler

- 📊 **Strateji:** EMA(9/21) kesişimi + RSI(14) aşırı alım/satım filtresi (tamamı ayarlanabilir)
- 🛡️ **Risk yönetimi:** Pozisyon büyüklüğü (%), zarar durdur (stop-loss), kâr al (take-profit), komisyon hesabı
- 🧪 **Paper trading (varsayılan):** Gerçek para kullanmadan sanal bakiye ile birebir simülasyon
- ⏪ **Backtest:** Stratejiyi geçmiş mum verisiyle saniyeler içinde test etme, al-ve-tut karşılaştırması
- 📝 **İşlem kaydı:** Tüm alım-satımlar `logs/trades.jsonl` dosyasına yazılır
- 🔴 **Live mod iskeleti:** Binance TR Open API üzerinden imzalı (HMAC-SHA256) gerçek emir gönderimi

## Kurulum

```bash
# 1. Node.js 18 veya üzeri gerekli (node --version ile kontrol edin)

# 2. Ayar dosyasını oluşturun
cp .env.example .env

# 3. .env dosyasını düzenleyin (sembol, strateji, risk ayarları)
```

## Kullanım

### 1) Backtest — önce stratejiyi geçmişte test edin

```bash
npm run backtest                       # .env'deki sembol/aralık ile
node src/backtest.js BTCTRY 1h 500     # BTCTRY, 1 saatlik, son 500 mum
node src/backtest.js ETHTRY 15m 1000
```

### 2) Paper mod — sanal parayla canlı simülasyon (varsayılan)

```bash
npm start
```

Bot her `POLL_SECONDS` saniyede piyasayı kontrol eder, sinyal oluştuğunda sanal
bakiyeyle alım/satım yapar ve durumu ekrana + `logs/trades.jsonl` dosyasına yazar.

### 3) Live mod — gerçek para (⚠️ dikkat!)

1. Binance TR hesabınızda API anahtarı oluşturun (sadece **spot trade** yetkisi verin,
   **çekim yetkisi asla vermeyin**, mümkünse IP kısıtlaması ekleyin).
2. `.env` içinde `BINANCE_TR_API_KEY` ve `BINANCE_TR_API_SECRET` değerlerini girin.
3. `TRADE_MODE=live` yapın ve `npm start` ile başlatın. Bot başlamadan önce
   10 saniyelik iptal süresi tanır.

> Canlı emir uç noktaları Binance TR Open API'ye göre yazılmıştır
> (`/open/v1/orders`). API sözleşmesi değişmiş olabilir — canlıya geçmeden önce
> [resmî dokümantasyonla](https://www.trbinance.com/apidocs) karşılaştırın.

## Ayarlar (.env)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `TRADE_MODE` | `paper` | `paper` = simülasyon, `live` = gerçek emir |
| `SYMBOL` | `BTCTRY` | İşlem çifti |
| `INTERVAL` | `15m` | Mum aralığı (`1m`, `5m`, `15m`, `1h`, `4h`, `1d`...) |
| `EMA_FAST` / `EMA_SLOW` | `9` / `21` | EMA periyotları |
| `RSI_PERIOD` | `14` | RSI periyodu |
| `RSI_OVERBOUGHT` / `RSI_OVERSOLD` | `70` / `30` | RSI eşikleri |
| `PAPER_BALANCE` | `10000` | Paper mod başlangıç bakiyesi (TRY) |
| `POSITION_PCT` | `25` | Her işlemde kullanılacak bakiye yüzdesi |
| `STOP_LOSS_PCT` | `2` | Zarar durdur yüzdesi |
| `TAKE_PROFIT_PCT` | `4` | Kâr al yüzdesi |
| `FEE_PCT` | `0.1` | İşlem komisyonu yüzdesi |
| `POLL_SECONDS` | `30` | Piyasa kontrol sıklığı (saniye) |

## Mimari

```
src/
├── index.js              # Ana döngü: veri çek → sinyal üret → emir yönet
├── backtest.js           # Geçmiş veriyle strateji testi
├── strategy.js           # EMA kesişimi + RSI sinyal mantığı
├── indicators.js         # EMA, RSI hesaplamaları
├── portfolio.js          # Bakiye, pozisyon, stop-loss/take-profit, K/Z takibi
├── config.js             # .env yükleyici ve doğrulama
├── logger.js             # Konsol + logs/trades.jsonl işlem kaydı
└── exchange/
    └── binanceTr.js      # Piyasa verisi (kline) + Binance TR imzalı emir API'si
```

## Güvenlik notları

- `.env` dosyası `.gitignore`'dadır — API anahtarlarınızı asla commit etmeyin.
- API anahtarına **yalnızca spot işlem** yetkisi verin, çekim yetkisi vermeyin.
- Küçük tutarlarla başlayın; botu gözetimsiz uzun süre bırakmayın.
