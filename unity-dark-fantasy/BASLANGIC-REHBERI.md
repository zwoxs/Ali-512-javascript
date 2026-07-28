# 🗡️ Dark Fantasy Oyunu — Sıfırdan Başlangıç Rehberi

Bu rehber, **modelleme ve animasyon bilmeden** Unity'de 3. şahıs bir dark
fantasy prototipi kurmanı sağlar. Hazır varlıklar (asset) + buradaki scriptlerle
çalışan bir karakter, kamera ve basit savaş elde edeceksin.

> **Önemli:** Amacımız önce **oynanabilir küçük bir prototip**. Elden Ring'i bir
> günde yapamayız — ama "karakterim yürüyor, dövüşüyor" noktasına birkaç saatte
> gelebiliriz. Gerçekçilik ve içerik sonra eklenir.

---

## 0. Neye ihtiyacın var (hepsi ücretsiz)

| Araç | Ne işe yarar | Nereden |
|---|---|---|
| **Unity Hub + Unity 6 LTS** | Oyun motoru | unity.com/download |
| **Mixamo** | Hazır rigli + animasyonlu karakter | mixamo.com (Adobe, ücretsiz) |
| **Quixel Megascans / Bridge** | Fotogerçekçi doğa/ortam | Unity ile ücretsiz |

---

## 1. Projeyi oluştur

1. Unity Hub → **New Project**
2. Şablon: **3D (URP)** seç  *(hafif + şık; güçlü PC'de sonra HDRP'ye geçebilirsin)*
3. İsim: `DarkFantasy` → **Create**

Açıldığında `Assets` klasörünü göreceksin. İşte projemiz burada yaşayacak.

---

## 2. Bu scriptleri projeye ekle

Bu depodaki `unity-dark-fantasy/Scripts/` klasöründeki `.cs` dosyalarını
Unity projendeki `Assets/Scripts/` klasörüne kopyala:

- `ThirdPersonController.cs` — karakter hareketi
- `CameraFollow.cs` — omuz üstü kamera
- `Health.cs` — can sistemi (oyuncu + düşman)
- `PlayerAttack.cs` — yakın dövüş saldırısı
- `SimpleEnemy.cs` — basit düşman AI

Unity otomatik derler. Hata çıkmazsa hazırsın.

---

## 3. Test zemini yap (5 dakika)

1. **GameObject → 3D Object → Plane** — bu senin zeminin.
2. Ölçeğini büyüt: Inspector'da Scale = (5, 1, 5).
3. **GameObject → 3D Object → Cube** ile birkaç duvar/engel koy (atmosfer için).

> İpucu: Karanlık hava için **Directional Light**'ı seç, rengini soğuk mavi/mor
> yap, şiddetini düşür. Window → Rendering → Lighting'den ortam ışığını kıs.

---

## 4. Karakteri getir (Mixamo — modelleme YOK)

1. **mixamo.com**'a ücretsiz gir.
2. Bir **Characters** karakteri seç (ör. zırhlı savaşçı).
3. **Animations** sekmesinden şunları ayrı ayrı indir (Format: **FBX for Unity**):
   - `Idle` (dururken)
   - `Walking` / `Running`
   - `Sword And Shield Slash` (saldırı)
   - İlk indirişte **"With Skin"**, diğer animasyonlarda **"Without Skin"** seç.
4. FBX'leri `Assets/Characters/` klasörüne sürükle.
5. Karakter FBX'ini sahneye sürükle → zeminin üstüne koy.
6. Karakteri seç → tag'ini **"Player"** yap (Inspector'ın en üstünde).

### Karaktere scriptleri tak
Karakter seçiliyken **Add Component** ile ekle:
- **Character Controller** (Unity'nin hazır bileşeni) — yüksekliğini/merkezini
  karaktere göre ayarla (Center Y ≈ 1, Height ≈ 2).
- **ThirdPersonController** (bizim script)
- **PlayerAttack** (bizim script)
- **Health** (bizim script) → maxCan = 100

---

## 5. Kamera

1. **Main Camera**'yı seç → **CameraFollow** scriptini ekle.
2. `Hedef` alanına karakterini sürükle.
3. **Play** ▶️ bas:
   - **W/A/S/D** = hareket, **Shift** = koş, **Space** = zıpla
   - **Fare** = etrafa bak
   - **Sol tık** = saldırı

Karakterin yürüyor ve kamera onu takip ediyorsa **prototipin ilk hali çalışıyor!** 🎉

---

## 6. Animasyonları bağla (Animator)

Karakter kayıyormuş gibi görünüyorsa animasyon eksiktir. Basit çözüm:
1. `Assets`'te sağ tık → **Create → Animator Controller**, adı `PlayerAnim`.
2. Çift tıkla, açılan pencereye Mixamo animasyonlarını sürükle (Idle, Walk/Run, Attack).
3. Bir **Float** parametresi ekle: `Speed`. Bir **Trigger**: `Attack`.
4. Idle ↔ Walk geçişini `Speed` değerine bağla (Speed > 0.1 → Walk).
5. Karakterdeki **Animator** bileşeninde Controller = `PlayerAnim` yap.

> Scriptler zaten `Speed`, `IsGrounded` ve `Attack` parametrelerini otomatik
> günceller — sadece Animator'da bu isimlerle geçişleri kur.

---

## 7. Düşman ekle

1. Mixamo'dan bir düşman karakter daha getir (veya aynısını çoğalt).
2. Ona ekle: **SimpleEnemy** + **Health**.
3. Play'e bas — düşman seni görünce kovalar ve yaklaşınca vurur; sen sol tıkla
   ona hasar verirsin.

---

## 8. Bundan sonra (yol haritası)

Prototip çalışınca sırayla ekle:
1. **Can barı (UI)** — ekranda can göstergesi
2. **Ses** — ayak sesi, kılıç, ortam müziği (freesound.org ücretsiz)
3. **Quixel Megascans** ile gerçekçi ortam (kaya, zemin, ağaç)
4. **Post-processing** (URP) — sis, bloom, renk tonu → dark fantasy atmosferi
5. **Menü + can/ölüm ekranı**
6. Daha akıllı düşman (NavMesh ile engel etrafından dolaşma)

---

## 🎯 Altın kural

Büyük düşünme, **küçük bitir**. Her hafta çalışan tek bir şey ekle. "Yürüyen
karakter" → "dövüşen karakter" → "bir düşman" → "bir küçük alan". Bu adımların
her biri gerçek bir ilerlemedir. Bol bol takılırsın, normal — her takıldığında
bana ekran görüntüsü/hata mesajı getir, birlikte çözeriz.
