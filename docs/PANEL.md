# Ofis kontrol paneli

Bütün ofisi tek ekrandan izlediğin ve yönettiğin sayfa. Senin bilgisayarında çalışır, yalnızca bu
bilgisayardan açılır (http://127.0.0.1:8770). Anahtar ve şifreler panelde asla görünmez, sadece "var / yok" yazar.

## Açmak

`panel.bat` dosyasına çift tıkla. Tarayıcı kendiliğinden açılır. Siyah pencere açık kaldığı sürece panel çalışır.
Komutla: `.venv\Scripts\python.exe -m ofis panel`

Panel çok hafiftir (video üretmez, sadece dosyaları okur); gün boyu açık kalabilir.

## Ekranlar

| Ekran | Ne gösterir, ne yaparsın |
| --- | --- |
| Canlı Ofis | Her ajanın masası: şu an ne yaptığı, hangi videoda, ne kadar sürdü. 5 yapay zekanın kartı: o an hangisi kimin için ne yapıyor. Saniye saniye canlı akış. |
| Üretim Hattı | Her video hangi aşamada (fikir, senaryo, ses, görsel, video, onay, yükleme, YouTube), kanal filtresiyle. |
| Onay Masası | Videoyu izle, Onayla (saatinde yayın), Hemen yayınla ya da Reddet. Kalite kontrolünün ve Gemini'nin notları. Content Rewards gönderim uyarıları. |
| Yayın Takvimi | Zamanlanmış yayınlar, yayındakiler, son 14 günün üretim/yayın grafiği. |
| Kanallar ve Ayarlar | Kanal aç/kapat, otomatik onay aç/kapat, günlük video sayısı. Elle çalıştır (üret, yükle, rapor). Görev Zamanlayıcı görevlerini gör, aç/kapat. Yapay zekaların ve anahtarların durumu. |
| Raporlar | İzlenme, beğeni, kanal başına en iyi videolar, haftalık rapor ve günlük özet. |
| Hatalar ve Günlük | 3 denemede olmayan işler (Tekrar dene düğmesi), reddedilenler, aranabilir ofis günlüğü. |

## Yapay zekalar

| Yapay zeka | Nerede | Görevi |
| --- | --- | --- |
| Ollama (qwen3:8b) | Bu bilgisayar | Ana yazar: fikirler ve senaryolar |
| Google Gemini | Google, ücretsiz katman | Eleştirmen: haber puanlama, kanca/başlık, akıcılık, SEO, denetim |
| Kokoro-82M | Bu bilgisayar | İngilizce seslendirme |
| Piper | Bu bilgisayar | Türkçe seslendirme, İngilizce yedek ses |
| faster-whisper | Bu bilgisayar | Sesi dinleyip kelime kelime altyazı zamanı |

## Nasıl canlı görüyor

Ajanlar ve yapay zekalar çalışırken her adımın başını ve sonunu `veri/olaylar/GÜN.jsonl` dosyasına yazar.
Panel bu dosyayı 2 saniyede bir okur. Ayar değişiklikleri `config/kanallar.yaml` içinde yalnızca ilgili satırı
değiştirir (önceki hâli `config/kanallar.yaml.yedek`).

Telefondan aynı ağda bakmak istersen `.env` içine `PANEL_ADRESI=0.0.0.0` yaz (dikkat: ağdaki herkes açabilir).
