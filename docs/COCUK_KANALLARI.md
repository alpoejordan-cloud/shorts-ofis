# Çocuk kanalları (3. ve 4. kanal)

İki yeni kanal: **Pip & Pals** (İngilizce, `cocuk_en`) ve **Fıstık ve Arkadaşları** (Türkçe, `cocuk_tr`).
Adlar öneridir; YouTube'da başka ad seçersen `config/kanallar.yaml` içinde `ad:` satırını değiştir.

## Nasıl çalışır

1. **Fikir:** trend yok. 30 tema (paylaşmak, özür dilemek, renkler, sayılar, diş fırçalamak...) sırayla döner;
   mekan ve karakter ikilisi de en az kullanılanlardan seçilir. Aynı hikaye tekrar etmez.
2. **Hikaye:** Ollama 3-5 sahnelik kısa bir hikaye yazar (anlatıcı + karakter konuşmaları, duygular, sondaki ders).
   Gemini hikayeyi cilalar ve 3-7 yaş uygunluğunu puanlar (7/10 altı düzeltilir).
   Korkutucu/şiddet/marka/başka çizgi film karakteri/“abone ol” sözcükleri otomatik engellenir.
3. **Ses:** anlatıcı ve her karakter kendi sesiyle konuşur (İngilizce Kokoro, Türkçe Piper), karakter sesleri
   çizgi film tınısına inceltilir. Müzik kutusu müziği ve efektler kodla üretilir (telif yok).
4. **Animasyon:** karakterler ve 8 mekan (çayır, orman, sahil, gece, kar, bahçe, oda, gölet) kodla çizilir.
   Karakterler sahneye zıplayarak girer, göz kırpar, konuşanın ağzı sese göre açılır, duygular yüze yansır.
   Altyazıda konuşanın kelimesi kendi renginde parlar. Video ~35-55 sn, 1080x1920.
5. **Kalite + yükleme:** kalite kontrolü ve Gemini çocuk denetimi geçen video otomatik yüklenir,
   **Made for Kids** olarak işaretlenir. Geçmeyen onay masasına düşer.

Bir video bu bilgisayarda ~3-6 dk sürer (hikaye yazımı en uzun adım). Ek maliyet yok, GPU gerekmez.

## Senin yapacakların (bir kez)

1. **İki YouTube kanalı aç** (Google hesabında “Kanal oluştur”). YouTube yeni kanal için telefon/yüz/kimlik
   doğrulaması isteyebilir; bunu sen yaparsın.
   - Kanal ayarları > Gelişmiş: **“Evet, bu kanal çocuklara yöneliktir”** seç.
   - Profil ve banner: `branding/cocuk_en/` ve `branding/cocuk_tr/` içindeki `profil.png`, `banner.png`.
2. **Ayrı Google Cloud projesi** (mevcut proje günde ~6 yüklemeyle dolu): console.cloud.google.com
   > yeni proje > YouTube Data API v3'ü etkinleştir > OAuth istemcisi (Masaüstü uygulaması) > JSON'u indir
   > `config/client_secret_cocuk.json` adıyla kaydet. (İlk projedeki adımların aynısı.)
3. Komutlar:
   ```
   git pull
   python -m ofis sesleri-indir
   python -m ofis yetkilendir cocuk_en     (tarayıcıda Pip & Pals kanalını seç)
   python -m ofis yetkilendir cocuk_tr     (Fıstık ve Arkadaşları kanalını seç)
   python -m ofis doktor
   ```
Kanallar bağlanana kadar her kanal için en fazla 3 video hazırda bekler; bağlanınca yayın saatlerinde çıkar.

## Yayın saatleri (Türkiye saati)

| Kanal | Günlük | Saatler |
|---|---|---|
| cocuk_en | 2 | 15:00, 23:00 (ABD sabahı + okul sonrası) |
| cocuk_tr | 2 | 16:00, 19:30 |

Üretim mevcut zamanlayıcıyla (18:00 ve 02:30) yapılır; 18:00 öncesi üretim kuralı aynen geçerli.

## Bilmen gerekenler

- **Made for Kids** videolarda yorumlar kapanır, kişiselleştirilmiş reklam gösterilmez: izlenme başına gelir
  diğer kanallardan düşüktür. Bu kanallar daha çok izlenme sayısıyla kazanır.
- YouTube, şablonla seri üretilmiş ve birbirine çok benzeyen içeriğe para ödemiyor (“özgün olmayan içerik”).
  Bunu azaltmak için her hikaye özgün, temalar/mekanlar/karakterler döner ve hikayeler insan yazımına yakın
  olsun diye Gemini ile cilalanır. Yine de kanal para kazanma başvurusunda incelenecektir.
- Türkçe için ücretsiz Piper'da yalnız 3 erkek ses var; karakterler bu seslerin inceltilmiş hâlidir.
- Önizleme: `python -m ofis cocuk-ornek cocuk_tr` (karakter tablosu, `veri/raporlar/`).
- Karakterleri değiştirmek: `config/kanallar.yaml` > `karakterler` (tür, renk, aksesuar, ses, perde, kişilik).
