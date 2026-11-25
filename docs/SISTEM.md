# Shorts Ofis — Sistem, araçlar ve kapasite

Bu belge sistemin bugünkü hâlini anlatır: hangi aracı neden kullandığımızı, bir videonun ne kadar sürdüğünü ve günde kaç video çıkardığımızı.

## Akış

```
trend (fikir) → senarist (senaryo, Ollama) → seslendirme (Kokoro / Piper + Whisper altyazı)
   → görsel (CC fotoğraf / izinli klip) → kurgu (FFmpeg) → onay masası → yükleyici (YouTube API)
```

Her iş `veri/isler/<id>.json` dosyasında durur. Bir adım hata verirse müdür aynı çalışmada
3 kez dener (45 sn, 90 sn bekleyerek). Yine olmazsa iş `hata` olur ve günlük özete yazılır.

## Seçilen araçlar (hepsi ücretsiz, CPU'da çalışır)

| İş | Araç | Neden | Yedeği |
|---|---|---|---|
| Dil modeli | Ollama + **qwen3:8b** (`think` kapalı) | qwen2.5:7b'ye göre Türkçesi daha temiz, araya Çince karışmıyor; ~%15–20 daha yavaş | `.env` → `OLLAMA_MODEL=qwen2.5:7b` |
| İngilizce ses | **Kokoro-82M** (kokoro-onnx, MIT; model Apache 2.0): `af_heart` (Tech), `am_michael` (GTA) | Açık kaynak TTS'ler arasında en doğal İngilizce ses; CPU'da gerçek zamandan hızlı | Piper `en_US-ryan-high` (Kokoro çalışmazsa kendiliğinden devreye girer) |
| Türkçe ses | **Piper** `tr_TR-dfki-medium` | Kokoro Türkçe desteklemiyor | — |
| Altyazı zamanlaması | faster-whisper kelime zamanları | Kelime kelime vurgulu altyazı | Cümle süresine göre tahmin |
| Ses seviyesi | FFmpeg `loudnorm I=-14:TP=-1.5:LRA=11` | YouTube'un hedef seviyesi; videolar arasında ses farkı olmaz | — |
| Kampanya klibinde an seçimi | Ses enerjisine göre (RMS) en hareketli bölüm | Klip izin verilen süreden uzunsa en iyi 58 sn alınır | Baştan kesim |
| Yüz kamerası | OpenCV Haar (4.x) | Hafif, kurulumu sorunsuz; mediapipe gerekmedi | Tam ekran oyun görüntüsü |
| Sahne tespiti | Gerek yok | Klipler zaten kısa (≤60 sn); PySceneDetect yük getirirdi | — |
| Görsel | Openverse / Wikimedia (CC, atıflı) | Lisanslı ve ücretsiz | Desenli arka plan |
| İkinci yapay zeka (denetçi) | **Gemini** ücretsiz katman (`google-genai`, gemini-2.5-flash) | Ollama yazar, Gemini eleştirir (kanca, SEO, dil, uydurma iddia), Ollama düzeltir; en fazla 2 tur. Fikirlerde de puanlar, zayıfları değiştirtir | Anahtar yoksa ya da kota dolarsa sessizce yalnızca Ollama |

## Ölçülen süreler (bu bilgisayar, 16 GB RAM, CPU)

| Kanal | Toplam | Trend | Senaryo | Ses | Görsel | Kurgu | Video |
|---|---|---|---|---|---|---|---|
| Tech in 30 (teknoloji_en) | 11.5 dk | 140 sn | 260 sn | 73 sn | 31 sn | 183 sn | 43 sn |
| Cebine Bilgi (finans_tr) | 12.6 dk | 188 sn | 254 sn | 42 sn | 118 sn | 157 sn | 39 sn |
| Open World Insider klibi (gta_en) | 4.5 dk | — | 52 sn | 24 sn | 0 sn | 194 sn | 48 sn |

qwen3:8b'de senaryo adımı ~20–40 sn uzar.

## Kapasite ve günlük hedef

- **Bilgisayar sınırı:** en yavaş video ~13 dk. Gece 02:30–08:30 arası 6 saatte ~25 video üretilebilir.
  Yani darboğaz bilgisayar değil.
- **YouTube API kotası:** bir Google Cloud projesi günde 10.000 birim alır; bir yükleme 1.600 birim tutar.
  Bu yüzden **üç kanalın toplamı günde en fazla 6 yükleme** olabilir.
- **İzinli klipler:** yalnızca `config/izinler.yaml` içindeki kampanya yayıncıları kullanılır (şu an Dom
  ve Bobby VanRiper). Kampanyaya yeni klip düştükçe artar.
- **Sağlıklı sıklık:** yeni kanalda günde 1–2 Short iyidir. Daha fazlası izlenmeyi bölüştürür.

| Kanal | `gunluk_video` | Yayın saatleri (TR) |
|---|---|---|
| teknoloji_en | 2 | 17:00, 23:00 |
| finans_tr | 1 | 20:00 |
| gta_en | 2 (yarısı izinli klip) | 19:00, 02:00 |
| **Toplam** | **5** (1 yükleme acil kampanya klibine ayrılır) | |

Kota artırılırsa (Google'dan kota başvurusu ya da ikinci bir proje) `gunluk_video` değerleri artırılabilir.

## Otomatik onay ve kalite kontrolü

`config/kanallar.yaml` içinde bir kanalda `otomatik_onay: true` olursa, kalite kontrolünden (`ofis/kalite.py`) geçen video onay
beklemeden onaylanır. Ardından kanalın yayın saatine `publishAt` ile zamanlanır (önce gizli yüklenir, saatinde herkese açılır).
Bir madde bile geçmezse video onay masasına düşer ve kartta nedeni yazar. Kontrol maddeleri:

- video ve ses akışı var, süre 12–60 sn
- altyazı var (en az 3 satır)
- ses seviyesi -17 ile -11 LUFS arası (hedef -14)
- başlık ve kanca dolu, başlık ve senaryo kanal dilinde
- Gemini'nin uydurma iddia şüphesi yok
- senaryodaki yüzde/para/büyük sayılar konu ve kaynaklarda geçiyor

Kampanya klipleri her zaman masaya düşer. Gönderim süresi (30 dk) yayın anında başladığı için yayını sen başlatırsın (`yayinla`).
Bobby VanRiper kampanyası durduruldu (`aktif: false`). Dom'un ağırlığı 3. GTA'da videoların ~%30'u klip, gerisi haber/yorum.

## Zamanlayıcı (Windows Görev Zamanlayıcı)

| Görev | Zaman | Ne yapar |
|---|---|---|
| ShortsOfis - Gunluk uretim | her gece 02:30 | üretim + onaylananları yükleme + temizlik + günlük özet |
| ShortsOfis - Sabah telafi | her sabah 08:30 | yarım kalan işleri bitirir; hedef doluysa hiçbir şey üretmez |
| ShortsOfis - Ogle yukleme | her gün 14:00 | gün içinde onayladıklarını yükler |
| ShortsOfis - Haftalik rapor | pazartesi 09:00 | haftalık rapor |
| ShortsOfis - Kampanya hatirlatici | 5 dakikada bir | yayına giren kampanya klibi için 30 dk gönderim uyarısı |

Yeniden kurmak için: `powershell -ExecutionPolicy Bypass -File scripts\zamanla.ps1`

## Komutlar

```
python -m ofis doktor        # eksik var mı
python -m ofis gunluk        # zamanlayıcının çalıştırdığı tam gün
python -m ofis onay          # onay masası (tarayıcıda açılır)
python -m ofis yukle         # onaylananları yükle (zamanlanmış, gizli → saatinde açılır)
python -m ofis yayinla İŞ    # bir işi hemen herkese açık yükle (kampanya klibi için)
python -m ofis hatirlat      # 30 dk kampanya gönderim kontrolü
python -m ofis temizle       # biten işlerin ara dosyaları 3, videoları 30 gün sonra silinir
python -m ofis ozet          # veri/raporlar/gunluk_TARIH.md
```

## Kurallar (değişmez)

- Onaysız yükleme yok. Herkese açık yayın, kampanyaya katılma ve gönderme düğmelerine kullanıcı basar.
- Yalnızca izinli ya da lisanslı kaynak kullanılır. İzinsiz yayıncı videosu indirilmez.
- `client_secret.json`, `.env` ve `veri/tokenlar` asla commit edilmez.
