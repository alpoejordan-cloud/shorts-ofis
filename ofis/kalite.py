"""Otomatik onaydan önce kalite kontrolü. Bir madde bile geçmezse video yüklenmez, onay masasına düşer.

Kontroller: video ve ses akışı var mı, süre, altyazı, ses seviyesi (-14 LUFS civarı), dil, kanca,
başlık, uydurma iddia şüphesi (Gemini notu + doğrulanmamış sayı taraması).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .cekirdek import VERI, Is, gunluk_al

log = gunluk_al("kalite")

EN_KISA_SN, EN_UZUN_SN = 12.0, 60.0
LUFS_ARALIGI = (-17.0, -11.0)
TR_HARF = set("ğışçöüĞİŞÇÖÜ")
TR_SOZ = {"ve", "bir", "bu", "için", "ile", "çok", "ama", "daha", "gibi", "değil", "neden", "nasıl", "sen", "biz"}
EN_SOZ = {"the", "and", "is", "you", "this", "that", "of", "to", "in", "for", "what", "why", "how", "it"}

# modelin senaryoya sızdırdığı yapı etiketleri ("Why this matters:", "One honest opinion:")
SAHNE_ETIKETI = re.compile(r"(?:^|[.!?]\s+)((?:why this matters|one honest opinion|hook|intro|outro|cta|"
                           r"neden önemli|kanca|giriş|kapanış)\s*:)", re.I)


def klasor(is_: Is) -> Path:
    return VERI / "cikti" / is_.kanal / is_.id


def _ffprobe(yol: Path) -> dict[str, Any]:
    probe = shutil.which("ffprobe")
    if not probe:
        return {}
    s = subprocess.run([probe, "-v", "error", "-show_entries", "stream=codec_type:format=duration",
                        "-of", "json", str(yol)], capture_output=True, text=True)
    try:
        return json.loads(s.stdout)
    except json.JSONDecodeError:
        return {}


def ses_seviyesi(yol: Path) -> float | None:
    """Videonun bütünleşik ses seviyesi (LUFS)."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    s = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", str(yol), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    eslesen = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", s.stderr)
    return float(eslesen[-1]) if eslesen else None


def dil_tutuyor_mu(metin: str, dil: str) -> bool:
    kelimeler = re.findall(r"[^\W\d_]+", metin.lower())
    if len(kelimeler) < 4:
        return True
    tr = sum(w in TR_SOZ for w in kelimeler) + 2 * sum(c in TR_HARF for c in metin)
    en = sum(w in EN_SOZ for w in kelimeler)
    return en >= tr if dil == "en" else tr >= en


def kontrol(is_: Is, k: dict[str, Any]) -> list[str]:
    """Geçmeyen maddelerin listesi (boşsa video otomatik yüklenebilir)."""
    v, sorunlar = is_.veri, []
    video = klasor(is_) / str(v.get("video", "video.mp4"))
    if not video.exists():
        return ["video dosyası yok"]
    bilgi = _ffprobe(video)
    turler = {a.get("codec_type") for a in bilgi.get("streams", [])}
    if bilgi and "audio" not in turler:
        sorunlar.append("videoda ses yok")
    sure = float((bilgi.get("format") or {}).get("duration") or v.get("sure") or 0)
    if not EN_KISA_SN <= sure <= EN_UZUN_SN:
        sorunlar.append(f"süre {sure:.1f} sn ({EN_KISA_SN:.0f}-{EN_UZUN_SN:.0f} olmalı)")

    altyazi = klasor(is_) / "altyazi.ass"
    satir = altyazi.read_text(encoding="utf-8", errors="ignore").count("Dialogue:") if altyazi.exists() else 0
    if satir < 3:
        sorunlar.append("altyazı yok veya çok az")

    lufs = ses_seviyesi(video)
    if lufs is not None and not LUFS_ARALIGI[0] <= lufs <= LUFS_ARALIGI[1]:
        sorunlar.append(f"ses seviyesi {lufs:.1f} LUFS (hedef -14)")

    baslik = str(v.get("baslik", "")).strip()
    if not baslik or len(baslik) > 100:
        sorunlar.append("başlık boş veya 100 karakterden uzun")
    kanca = str(v.get("kanca_metni", "")).strip()
    if not kanca or len(kanca.split()) > 9:
        sorunlar.append("kanca metni yok veya çok uzun")

    dil = k.get("dil", "en")
    # yayıncı klibinde senaryo yoktur; dil kontrolü başlık + açıklamada yapılır
    for ad, metin in (("başlık", baslik), ("senaryo", str(v.get("senaryo", "")))):
        if metin and not dil_tutuyor_mu(metin, dil):
            sorunlar.append(f"{ad} kanal dilinde ({dil}) görünmüyor")

    denetim = v.get("gemini_denetim") or {}
    if denetim.get("uydurma_suphesi"):
        sorunlar.append("uydurma şüphesi (Gemini): " + "; ".join(denetim["uydurma_suphesi"][:3]))
    if v.get("mod") != "izinli_klip":
        from .kaynak import metin_oku

        senaryo = str(v.get("senaryo", ""))
        kaynak_metni = metin_oku(v)
        if denetim and not denetim.get("onay"):
            sorunlar.append("Gemini onaylamadı: " + "; ".join(denetim.get("sorunlar", [])[:3]))
        if not kaynak_metni:
            # kaynak makale yoksa iddialar hiçbir şeyle karşılaştırılamaz: otomatik yayın yok
            sorunlar.append("kaynak makale metni yok: iddialar doğrulanamadı")
        else:
            sorunlar += kaynakla_karsilastir(senaryo + " " + str(v.get("kanca_metni", "")), kaynak_metni)
        etiket = SAHNE_ETIKETI.findall(senaryo)
        if etiket:
            sorunlar.append("seslendirmede başlık etiketi okunuyor: " + ", ".join(etiket[:3]))
    return sorunlar


SOYLENTI_KAYNAK = re.compile(r"\b(rumou?rs?|leak(?:s|ed)?|reportedly|unconfirmed|insider|speculat\w*|söylenti\w*|"
                             r"sızıntı\w*|iddia\w*)\b", re.I)
SOYLENTI_SENARYO = re.compile(r"\b(rumou?rs?|leak(?:s|ed)?|reportedly|unconfirmed|allegedly|according to|claims?|"
                              r"report(?:s|ed)?|söylenti\w*|sızıntı\w*|iddia\w*|habere göre|bildirildi)\b", re.I)
SERBEST_AD = {"i", "i'm", "i'd", "i'll", "i've", "ai", "shorts", "youtube", "comment", "comments", "follow"}


def _sayi(metin: str) -> str:
    return re.sub(r"(?<=\d)[.,](?=\d)", "", metin)


def _kucuk(metin: str) -> str:
    return metin.replace("İ", "i").replace("I", "ı").lower() if re.search(r"[ğışçöüİ]", metin) else metin.lower()


def kaynakla_karsilastir(senaryo: str, kaynak_metni: str) -> list[str]:
    """Senaryodaki sayılar ve özel isimler kaynak makalede geçiyor mu; söylenti söylenti diye anılmış mı."""
    sorunlar = []
    kaynak_sayi = _sayi(kaynak_metni)
    sayilar = [n.rstrip(".,") for n in re.findall(r"\d[\d.,]*", senaryo)]
    eksik_sayi = [n for n in dict.fromkeys(sayilar) if _sayi(n) not in kaynak_sayi]
    if eksik_sayi:
        sorunlar.append("kaynakta geçmeyen sayı: " + ", ".join(eksik_sayi[:5]))

    kaynak_kucuk = _kucuk(kaynak_metni)
    eksik_ad = []
    for cumle in re.split(r"(?<=[.!?])\s+", senaryo):
        for n, kelime in enumerate(re.findall(r"[^\s,;:!?()\"“”]+", cumle)):
            kelime = re.split(r"['’]", kelime.strip(".-—"))[0]
            if n == 0 or len(kelime) < 2 or not kelime[0].isupper() or _kucuk(kelime) in SERBEST_AD:
                continue  # cümle başı büyük harf özel isim sayılmaz
            if _kucuk(kelime) not in kaynak_kucuk:
                eksik_ad.append(kelime)
    if eksik_ad:
        sorunlar.append("kaynakta geçmeyen isim: " + ", ".join(list(dict.fromkeys(eksik_ad))[:5]))

    if len(SOYLENTI_KAYNAK.findall(kaynak_metni)) >= 2 and not SOYLENTI_SENARYO.search(senaryo):
        sorunlar.append("kaynak söylenti/sızıntı anlatıyor ama senaryo bunu 'rumor/reportedly' diye belirtmiyor")
    return sorunlar
