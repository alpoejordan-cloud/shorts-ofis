# YouTube API kota artırma: hazırlık notu

Formu doldurmak ve göndermek sana ait. Bu not yalnızca hazırlık içindir.

**Form:** https://support.google.com/youtube/contact/yt_api_form
("YouTube Data API Servisleri – Denetim ve Kota Artırma Formu"). Ücret yok. Ek kota isteyen herkes
önce uygunluk denetiminden (YouTube API Hizmet Şartları ve Geliştirici Politikaları) geçer. Yanıt
genellikle birkaç gün ile birkaç hafta arasında gelir.

## Şu anki durum
- Varsayılan kota: Google Cloud projesi başına günde 10.000 birim. Bir yükleme (videos.insert) 1.600 birim, yani günde ~6 yükleme.
- Kota Pasifik saatiyle gece yarısı sıfırlanır (TR 11:00, ABD yaz saatinde 10:00).
- Sistem bu sınıra göre çalışır (`GUNLUK_YUKLEME_SINIRI=6`, kota günü sayımı). Fazla videolar sonraki günün slotlarına kalır.

## Formun bölümleri ve hazırlanacak cevaplar
1. **İstek türü:** "Ek kota istemek için uygunluk denetimini tamamlama".
2. **Kuruluş ve iletişim:** bireysel içerik üreticisi; ad, e-posta, ülke.
3. **İş modeli:** kendi 3 YouTube kanalım için kişisel yükleme otomasyonu. Üçüncü kişilere hizmet ya da satış yok.
4. **API istemcisi:**
   - Google Cloud proje numarası: Cloud Console → proje ayarları.
   - OAuth istemcisi: masaüstü uygulaması, yalnızca kendi hesaplarım.
   - Kullanılan izinler: `youtube.upload` ve `youtube.readonly`.
5. **Kullanım ve kota:**
   - Kullanılan çağrılar: videos.insert, videos.list, channels.list.
   - Günde 2 kanalda 4–6, ileride 3 kanalda 9 video.
   - Önerilen istek: günde 20.000 birim.
   - Gerekçe: zamanlanmış yayın (publishAt) ve her video için tek yükleme. Toplu okuma ya da kazıma yok.
6. **Ek kanıt:** istemcinin çalışırken ekran görüntüleri ya da kısa ekran kaydı.
   - Örnekler: onay masası (`python -m ofis onay`), yükleme günlüğü (`veri/gunluk`), panel.
   - Gizlilik politikası URL'si istenirse: tek kullanıcılı kişisel araç olduğunu belirt.
7. **Onaylar:** Hizmet Şartları ve Geliştirici Politikaları kutuları işaretlenir, sonra gönderilir.

## Kota artmadan yapılabilecekler
- İkinci bir Google Cloud projesi açıp kanallardan birini ona bağlamak. Her proje ayrıca 10.000 birim alır.
  Proje oluşturmak ve OAuth onayı sana ait adımlar; sistemde kanal başına ayrı `client_secret` desteği gerekir.
