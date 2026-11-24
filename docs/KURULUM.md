# Kurulum rehberi (yaklaşık 1,5 saat, bir kez yapılır)

Bu adımların hepsini **sen** yaparsın, çünkü senin hesapların, telefonun ve imzan gerekiyor.
Şifreni veya doğrulama kodlarını hiçbir yere (Claude dahil) yazma.

## 1. Projeyi bilgisayarına indir (5 dk)

1. PowerShell'i aç.
2. Şunları yaz:
   ```
   cd $HOME\Documents
   git clone https://github.com/alpoejordan-cloud/shorts-ofis.git
   cd shorts-ofis
   ```
   Git yüklü değilse önce `winget install Git.Git` yaz, PowerShell'i kapatıp aç.

## 2. Kurulum betiğini çalıştır (20-40 dk, çoğu indirme)

```
powershell -ExecutionPolicy Bypass -File scripts\kurulum.ps1
```

Bu betik Python, FFmpeg, Ollama'yı kurar, yapay zeka modelini ve ses modellerini indirir.
Sonunda "sağlık kontrolü" listesi çıkar; EKSİK yazanları sonraki adımlar tamamlar.

## 3. Stok video anahtarı (isteğe bağlı, 5 dk)

Anahtar olmadan da çalışır; görüntüler yapay zekayla üretilir. Gerçek stok videolar istersen Pexels veya
Pixabay (pixabay.com/api/docs, giriş yapınca anahtar sayfada görünür) anahtarını `.env` içine yaz.

1. https://www.pexels.com/api/ adresinden ücretsiz hesap aç ve "Your API Key" al.
2. Proje klasöründeki `.env` dosyasını Not Defteri ile aç, `PEXELS_API_ANAHTARI=` satırının sonuna yapıştır.

## 4. YouTube kanalları ve Google Cloud (40 dk)

### 4a. Üç kanalı aç
1. Tek bir Google hesabıyla YouTube'a gir.
2. https://www.youtube.com/channel_switcher adresinden "Kanal oluştur" ile 3 ayrı **marka kanalı** aç
   (teknoloji, finans, GTA). İsimleri birlikte seçebiliriz.
3. Her kanalda https://www.youtube.com/verify ile telefon doğrulaması yap.
4. Kanal adlarını `config/kanallar.yaml` içindeki `ad:` alanlarına yaz.

### 4b. Google Cloud projesi
1. https://console.cloud.google.com adresine gir, "Yeni proje" oluştur, adı: `shorts-ofis`.
2. "API'ler ve Hizmetler > Kitaplık" bölümünden **YouTube Data API v3**'ü bul ve "Etkinleştir"e bas.
3. "OAuth izin ekranı": Kullanıcı türü **Harici**, uygulama adı `shorts-ofis`, kendi e-postanı yaz.
   "Test kullanıcıları" bölümüne kendi Gmail adresini ekle.
4. "Kimlik bilgileri > Kimlik bilgisi oluştur > OAuth istemci kimliği", tür: **Masaüstü uygulaması**.
   JSON'u indir, adını `client_secret.json` yap ve projenin `config` klasörüne koy.
5. Aynı yerden "API anahtarı" oluştur, `.env` içindeki `YOUTUBE_API_ANAHTARI=` satırına yapıştır.

Not: Uygulama "test" modundayken izin 7 günde bir yenilenmek isteyebilir. Bunun önüne geçmek için
OAuth izin ekranında "Uygulamayı yayınla"ya bas (Google denetimi istemez, sadece uyarı ekranı çıkar).

### 4c. Kanalları sisteme bağla
Her kanal için bir kez:
```
.venv\Scripts\python.exe -m ofis yetkilendir teknoloji_en
.venv\Scripts\python.exe -m ofis yetkilendir finans_tr
.venv\Scripts\python.exe -m ofis yetkilendir gta_en
```
Tarayıcı açılır; hesabını seçtikten sonra **o kanalı** seç ve izin ver. "Google bu uygulamayı doğrulamadı"
uyarısında "Gelişmiş > shorts-ofis'e git" de (uygulama senin, güvenli).

**Önemli:** Google'ın denetiminden geçmemiş API projelerinde yüklenen videolar "gizli" kalabilir.
O durumda videolar YouTube Studio'da hazır bekler, sen "Herkese açık" yaparsın. Denetim başvurusunu
sistem oturunca birlikte yaparız.

## 5. İlk deneme (15-30 dk)

```
.venv\Scripts\python.exe -m ofis doktor
.venv\Scripts\python.exe -m ofis uret --kanal teknoloji_en --adet 1
```
Sonra `onay_masasi.bat` dosyasına çift tıkla; tarayıcıda videoyu izle, Onayla veya Reddet.
Onayladığını yüklemek için:
```
.venv\Scripts\python.exe -m ofis yukle
```

## 6. Otomatiğe al (2 dk)

```
powershell -ExecutionPolicy Bypass -File scripts\zamanla.ps1
```
Bundan sonra her gece 02:30'da videolar üretilir. Senin işin: günde bir kez `onay_masasi.bat`.

## Sorun olursa
- `python -m ofis doktor` eksikleri söyler.
- `python -m ofis durum` hangi işin nerede takıldığını gösterir.
- Günlükler: `veri\gunluk\` klasörü. Hata mesajını Claude'a yapıştırman yeterli.
- Model çok yavaşsa `.env` içinde `OLLAMA_MODEL=qwen2.5:7b` yap (biraz daha hızlı, Türkçesi daha zayıf) ve `ollama pull qwen2.5:7b` çalıştır.
