"""Doktor: sistemin çalışması için gereken her şeyi kontrol eder ve eksikleri
Türkçe olarak, nasıl düzeltileceğiyle birlikte söyler."""
from __future__ import annotations

import importlib.util
import shutil

from .ajanlar.gorsel import izinli_yayincilar
from .ajanlar.seslendirme import ses_yolu
from .ajanlar.yukleyici import istemci_dosyasi, token_yolu
from .cekirdek import kanallar, ortam
from .yapay_zeka import calisiyor_mu


def kontrol() -> list[tuple[str, bool, bool, str]]:
    """(ad, tamam_mı, zorunlu_mu, açıklama/çözüm) listesi döner."""
    s: list[tuple[str, bool, bool, str]] = []
    for paket, modul in [("piper-tts", "piper"), ("faster-whisper", "faster_whisper"),
                         ("google-api-python-client", "googleapiclient"),
                         ("google-auth-oauthlib", "google_auth_oauthlib")]:
        var = importlib.util.find_spec(modul) is not None
        s.append((f"Python paketi {paket}", var, True, "pip install -r requirements.txt"))
    s.append(("FFmpeg", bool(shutil.which("ffmpeg")), True, "scripts/kurulum.ps1 çalıştır (winget install Gyan.FFmpeg)"))
    tamam, mesaj = calisiyor_mu()
    s.append(("Yapay zeka (Ollama)", tamam, True, mesaj))
    for k in kanallar():
        s.append((f"Ses modeli {k['ses']} ({k['id']})", ses_yolu(k["ses"]).exists(), True,
                  "python -m ofis sesleri-indir"))
        if k.get("ses_yedek"):
            s.append((f"Yedek ses {k['ses_yedek']} ({k['id']})", ses_yolu(k["ses_yedek"]).exists(), False,
                      "python -m ofis sesleri-indir"))
    if any(str(k["ses"]).startswith("kokoro:") for k in kanallar()):
        s.append(("Python paketi kokoro-onnx (kaliteli İngilizce ses)",
                  importlib.util.find_spec("kokoro_onnx") is not None, False,
                  "pip install -r requirements.txt (yoksa Piper yedek sesi kullanılır)"))
    from .gemini import baglanti_testi

    g_tamam, g_mesaj = baglanti_testi()
    s.append(("Gemini (konu puanlama, kanca/başlık, senaryo, SEO, denetim)", g_tamam, False, g_mesaj))
    s.append(("OpenCV (yüz kamerası tespiti)", importlib.util.find_spec("cv2") is not None, False,
              "pip install -r requirements.txt (yoksa kampanya klipleri tam dikey kırpılır)"))
    s.append(("Stok video anahtarı (Pexels veya Pixabay)",
              bool(ortam("PEXELS_API_ANAHTARI") or ortam("PIXABAY_API_ANAHTARI")), False,
              "İsteğe bağlı: yoksa görüntüler yapay zekayla üretilir. Pixabay anahtarı: pixabay.com/api/docs (giriş yapınca sayfada görünür)"))
    s.append(("YouTube API anahtarı (trendler için)", bool(ortam("YOUTUBE_API_ANAHTARI")), False,
              ".env dosyasına YOUTUBE_API_ANAHTARI=... ekle; yoksa trendler Google Trends ve Reddit'ten gelir"))
    s.append(("Google OAuth dosyası", istemci_dosyasi().exists(), False,
              "config/client_secret.json koy (rehber: docs/KURULUM.md, adım 4). Yükleme için şart."))
    for k in kanallar():
        s.append((f"YouTube izni: {k['id']}", token_yolu(k["id"]).exists(), False,
                  f"python -m ofis yetkilendir {k['id']}"))
    gta_gibi = [k for k in kanallar() if "izinli_klip" in k.get("kaynak_modlari", [])]
    if gta_gibi:
        s.append(("İzin belgesi olan yayıncı", bool(izinli_yayincilar()), False,
                  "config/izinler.yaml dosyasına yazılı izni olan yayıncıyı ekle; o zamana kadar haber/yorum üretilir"))
    return s


def yazdir() -> int:
    eksik_zorunlu = 0
    print("\nShorts Ofis sağlık kontrolü\n" + "-" * 40)
    for ad, tamam, zorunlu, cozum in kontrol():
        isaret = "TAMAM " if tamam else ("EKSİK " if zorunlu else "İSTEĞE")
        print(f"[{isaret}] {ad}")
        if not tamam:
            print(f"          -> {cozum}")
            eksik_zorunlu += zorunlu
    print("-" * 40)
    print("Her şey hazır, üretim yapılabilir." if not eksik_zorunlu else f"{eksik_zorunlu} zorunlu eksik var.")
    return eksik_zorunlu
