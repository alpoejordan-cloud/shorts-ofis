"""Çocuk kanalları: hikayeli 2D animasyon üretim hattı (tamamen yerel ve ücretsiz).

hikaye (Ollama yazar, Gemini cilalar ve çocuk güvenliği denetler)
  -> ses (çok sesli seslendirme: anlatıcı + her karakterin kendi sesi, müzik kutusu müziği, efektler)
  -> sahne planı (karakterlerin giriş/konuşma/göz kırpma zamanları)
  -> animasyon (Pillow ile çizilen karakterler ve arka planlar, FFmpeg ile 1080x1920 video)

Karakterler ve arka planlar kodla çizilir: telifli karakter yok, internet/GPU gerekmez,
her videoda aynı karakterler aynı görünür (dizi hissi).
"""

KANAL_TURU = "cocuk_animasyon"


def cocuk_kanali_mi(k: dict) -> bool:
    return k.get("tur") == KANAL_TURU
