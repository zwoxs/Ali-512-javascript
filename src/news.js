// Haber duyarliligi tanilamasi: npm run news [SEMBOL]
// Yapilandirilan kaynaktan basliklari ceker, puanlar ve kararini gosterir.
// Botun bir coine girmeden once ne "gordugunu" seffaf sekilde incelemenizi saglar.

import { config } from "./config.js";
import { getSentiment, scoreText } from "./core/newsSentiment.js";

const symbol = (process.argv[2] || config.symbols[0]).toUpperCase();

async function main() {
  if (!config.newsFilter) {
    console.log("NEWS_FILTER kapali. .env'de NEWS_FILTER=true yapip kaynak ayarlayin.");
    console.log("Yine de bir deneme yapiliyor...\n");
    config.newsFilter = true;
  }
  console.log(`Haber taramasi: ${symbol} | kaynak: ${config.newsSource}\n`);

  const s = await getSentiment(symbol, config);
  if (s.error) {
    console.error(`Haber cekilemedi: ${s.error}`);
    console.error("NEWS_SOURCE / NEWS_API_KEY / NEWS_RSS_URLS ayarlarini kontrol edin.");
    process.exit(1);
  }
  console.log(`Baslik sayisi : ${s.count}`);
  console.log(`Toplam puan   : ${s.score}`);
  console.log(`Ortalama      : ${s.avg.toFixed(2)}`);
  console.log(`Etiket        : ${s.label.toUpperCase()}`);
  const wouldBlock = s.count >= config.newsMinArticles && s.avg < config.newsMinScore;
  console.log(`Karar         : ${wouldBlock ? "❌ GIRIS ENGELLENIR (olumsuz haber)" : "✓ giris serbest"}`);
  if (s.count < config.newsMinArticles) {
    console.log(`(Not: ${config.newsMinArticles} baslik esigi altinda - filtre uygulanmaz.)`);
  }
}

main().catch((err) => {
  console.error("Haber tanilamasi hatasi:", err.message);
  process.exit(1);
});
