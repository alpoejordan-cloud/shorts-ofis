# Shorts Ofis

3 YouTube Shorts kanalı için trend bulan, senaryo yazan, seslendiren, kurgulayan ve yükleyen bir
"ofis". Tamamen ücretsiz ve açık kaynak araçlarla, senin bilgisayarında çalışır.

## Çalışanlar

| Ajan | Dosya | Görevi |
| --- | --- | --- |
| Müdür | `ofis/mudur.py` | Her gün işi açar, ajandan ajana taşır, hatada tekrar dener, yarım işi sürdürür |
| Doktor | `ofis/doktor.py` | Eksik kurulum ve ayarları bulur, nasıl düzeltileceğini söyler |
| Trend araştırmacı | `ofis/ajanlar/trend.py` | YouTube, Google Trends ve Reddit'ten kanalın nişine uyan konuları seçer |
| Senarist | `ofis/ajanlar/senarist.py` | Başlık, seslendirme metni, açıklama, etiket; her videoda farklı format |
| Seslendirme | `ofis/ajanlar/seslendirme.py` | Piper ile ses, Whisper ile kelime kelime altyazı |
| Görsel sorumlusu | `ofis/ajanlar/gorsel.py` | Pexels stok videoları, senin görsellerin, izinli yayıncı klipleri |
| Kurgu | `ofis/ajanlar/kurgu.py` | 1080x1920 video, altyazı, ses ve müzik (FFmpeg) |
| Onay masası | `ofis/ajanlar/onay.py` | Tarayıcıda videoları izleyip onayladığın sayfa |
| Yükleyici | `ofis/ajanlar/yukleyici.py` | YouTube API ile yükler, kanalın yayın saatine zamanlar |
| Analist | `ofis/ajanlar/analist.py` | İzlenmeleri toplar, haftalık rapor yazar, neyin tuttuğunu trend ajanına bildirir |

Akış: `fikir → senaryo → ses → gorsel → video → onay_bekliyor → onaylandi → yuklendi`

## Kanallar

`config/kanallar.yaml`: teknoloji (İngilizce), finans (Türkçe), GTA (İngilizce; Türkçe sürüm hazır, kapalı).

## Kurulum

[docs/KURULUM.md](docs/KURULUM.md) adım adım anlatıyor.

## Kurallar (değiştirme)

- Başkasının videosu izinsiz kullanılmaz. Yayıncı klipleri sadece `config/izinler.yaml` içinde
  `izin_belgesi` dolu olan yayıncılardan alınır. İzin mesajı şablonu: [docs/IZIN_MESAJI.md](docs/IZIN_MESAJI.md).
- Görseller sadece lisanslı kaynaklardan (Pexels, senin dosyaların). Müzik için YouTube Ses Kütüphanesi'nden
  indirdiğin parçaları `muzik/` klasörüne koy.
- Gerçekçi yapay zeka içeriği YouTube'a "değiştirilmiş/sentetik içerik" olarak bildirilir.
- Finans videoları yatırım tavsiyesi vermez.

## Komutlar

```
python -m ofis doktor | sesleri-indir | yetkilendir KANAL | uret | onay | yukle | rapor | gunluk | durum
```

## Test

```
python -m pytest -q
```
