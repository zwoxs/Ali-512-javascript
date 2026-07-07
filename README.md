# 🤖 Binance TR Coin Bot

Katmanlı mimarili, çoklu stratejili, kurumsal risk yönetimli kripto alım-satım botu.
**Hiçbir harici paket gerektirmez** — Node.js 18+ yeterlidir.

> ⚠️ **YASAL UYARI:** Kripto para alım-satımı yüksek risk içerir ve paranızın tamamını
> kaybetmenize yol açabilir. Bu bot eğitim amaçlıdır, yatırım tavsiyesi değildir.
> Geçmiş performans gelecekteki sonuçların garantisi değildir. Canlı moda geçmeden önce
> **mutlaka** backtest + paper modda uzun süre test edin. Ayrıca Binance TR'nin
> Türkiye'deki güncel hizmet/lisans durumunu ve API dokümantasyonunu kendiniz doğrulayın.

## Neden "profesyonel"?

| Özellik | Açıklama |
|---|---|
| **Tek kod yolu** | Backtest ve canlı işlem **aynı** `Engine`/`RiskManager`/`Portfolio` sınıflarını kullanır — backtest'te ölçtüğünüz davranış, canlıda çalışan davranışın birebir aynısıdır |
| **Takılabilir stratejiler** | `ema_rsi`, `macd`, `bollinger` — ortak sözleşme (`warmup` + `evaluate`), yeni strateji tek dosyayla eklenir |
| **Risk bazlı boyutlama** | `SIZING_MODE=risk`: pozisyon büyüklüğü stop mesafesine göre hesaplanır (işlem başına sabit sermaye riski) |
| **İz süren stop** | Zirveden `TRAILING_STOP_PCT` geri çekilmede kârı kilitler |
| **Devre kesiciler** | Günlük zarar limiti → o gün işlem durur; üst üste N zarar → soğuma süresi |
| **Durum kalıcılığı** | Açık pozisyonlar ve sayaçlar `data/state.json`'a atomik yazılır; bot yeniden başlayınca kaldığı yerden devam eder |
| **Kurumsal metrikler** | Backtest çıktısı: maksimum düşüş, Sharpe oranı, kâr faktörü, ortalama kazanç/kayıp, al-ve-tut karşılaştırması |
| **Dayanıklı ağ katmanı** | Üstel geri çekilmeli yeniden deneme, 429 rate-limit'te `Retry-After`'a saygı, istek zaman aşımları |
| **Gerçekçi simülasyon** | Paper/backtest'te kayma (slippage) ve komisyon modellemesi |
| **LOT_SIZE hassasiyeti** | Canlı emirlerde miktar borsanın adım büyüklüğüne yuvarlanır |
| **Telegram bildirimleri** | Her işlem ve devre kesici olayı anlık mesajla (isteğe bağlı) |
| **Denetim izi** | Tüm işlemler `logs/trades.jsonl`'a makine-okur JSON olarak yazılır |
| **Test kapsamı** | 22 birim/entegrasyon testi (`npm test`, yerleşik `node:test`) |

## Kurulum

```bash
node --version        # >= 18 olmali
cp .env.example .env  # ayarlari duzenleyin
npm test              # 22 testin gectigini dogrulayin
```

## Kullanım

### 1) Backtest — stratejiyi geçmişte ölçün

```bash
npm run backtest                            # .env ayarlariyla
node src/backtest.js BTCTRY 1h 1000         # sembol, aralik, mum sayisi
node src/backtest.js BTCTRY 1h 1000 macd    # farkli strateji dene
node src/backtest.js ETHTRY 15m 1000 bollinger
```

Örnek çıktı:

```
========================= SONUC =========================
Islem sayisi       : 14 (kazanan: 8)
Kazanma orani      : %57.1
Kar faktoru        : 1.62
Maks. dusus        : %4.31
Sharpe orani       : 1.18
Strateji getirisi  : %7.84
Al-ve-tut getirisi : %3.12 (karsilastirma)
```

### 2) Paper mod — sanal parayla canlı simülasyon (varsayılan)

```bash
npm start
```

### 3) Live mod — gerçek para (⚠️ dikkat!)

1. Binance TR'de API anahtarı oluşturun: sadece **spot trade** yetkisi,
   **çekim yetkisi asla**, mümkünse IP kısıtlaması.
2. `.env` → `BINANCE_TR_API_KEY`, `BINANCE_TR_API_SECRET`, `TRADE_MODE=live`.
3. `npm start` — bot başlamadan önce 10 saniyelik iptal süresi tanır.

> Canlı emir uç noktaları Binance TR Open API'ye göre yazılmıştır (`/open/v1/orders`).
> API sözleşmesi değişmiş olabilir — canlıya geçmeden önce
> [resmî dokümantasyonla](https://www.trbinance.com/apidocs) karşılaştırın.
> Tüm borsa entegrasyonu tek dosyadadır: `src/exchange/binanceTr.js`.

## Mimari

```
src/
├── index.js                  # Giris: coklu sembol dongusu, sinyal yonetimi, kapanista durum kaydi
├── backtest.js               # Ayni Engine ile tarihsel simulasyon + metrik raporu
├── config.js                 # .env yukleme + dogrulama (hatali ayarla baslamaz)
├── logger.js                 # Seviyeli log (debug/info/warn/error) + trades.jsonl denetim izi
├── state.js                  # Atomik durum kaliciligi (data/state.json)
├── notifier.js               # Telegram bildirimleri (hata botu durdurmaz)
├── indicators.js             # SMA, EMA, RSI, MACD, Bollinger, ATR - saf fonksiyonlar
├── strategies/
│   ├── index.js              # Strateji kayit defteri (ortak sozlesme)
│   ├── emaRsi.js             # Trend takip: EMA kesisimi + RSI filtresi
│   ├── macdCross.js          # Momentum: MACD sinyal kesisimi + histogram onayi
│   └── bollingerRevert.js    # Ortalamaya donus: bant tasmasi + RSI onayi
├── core/
│   ├── engine.js             # Karar dongusu - backtest ve canli icin TEK kod yolu
│   ├── portfolio.js          # Cift tarafli muhasebe: bakiye, pozisyon, K/Z defteri
│   ├── riskManager.js        # Boyutlama, SL/TP/trailing, devre kesiciler
│   └── metrics.js            # Drawdown, Sharpe, kar faktoru
├── exchange/
│   ├── market.js             # Kline/fiyat verisi - yeniden deneme + rate-limit yonetimi
│   ├── brokers.js            # PaperBroker / LiveBroker (ayni arayuz) + LOT_SIZE yuvarlama
│   └── binanceTr.js          # Binance TR Open API imzali istekler (HMAC-SHA256)
test/                         # 22 birim + entegrasyon testi (node:test)
```

**Katman kuralları:** Stratejiler sadece sinyal üretir (emir bilmez). `RiskManager`
tüm koruma kurallarının tek sahibidir. `Portfolio` sadece muhasebedir. `Engine`
hangi broker'la konuştuğunu bilmez — paper ve live tamamen eşdeğerdir.

## Önemli ayarlar (.env)

Tam liste ve açıklamalar için `.env.example` dosyasına bakın. Öne çıkanlar:

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `TRADE_MODE` | `paper` | `paper` = simülasyon, `live` = gerçek emir |
| `SYMBOLS` | `BTCTRY` | Virgülle çoklu: `BTCTRY,ETHTRY` |
| `STRATEGY` | `ema_rsi` | `ema_rsi` \| `macd` \| `bollinger` |
| `SIZING_MODE` | `percent` | `percent` \| `risk` (stop mesafesine göre) |
| `TRAILING_STOP_PCT` | `0` | İz süren stop (0 = kapalı) |
| `MAX_DAILY_LOSS_PCT` | `5` | Günlük zarar devre kesicisi |
| `MAX_CONSECUTIVE_LOSSES` | `3` | Bu kadar üst üste zararda soğuma başlar |
| `SLIPPAGE_PCT` | `0.05` | Simülasyon gerçeklik payı |
| `TELEGRAM_BOT_TOKEN` | — | İşlem bildirimleri (isteğe bağlı) |

## Test

```bash
npm test   # gostergeler, risk kurallari, metrikler, uctan uca motor testleri
```

## Güvenlik notları

- `.env`, `data/`, `logs/` git'e girmez (`.gitignore`).
- API anahtarına **yalnızca spot işlem** yetkisi verin; çekim yetkisi vermeyin; IP kısıtlayın.
- Küçük tutarlarla başlayın; devre kesici loglarını (`logs/bot.log`) düzenli kontrol edin.
- Sunucuda 7/24 çalıştırma için `systemd` veya `pm2` kullanın; bot SIGTERM'de durumunu kaydederek kapanır.
