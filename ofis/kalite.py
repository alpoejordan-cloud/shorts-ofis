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
# yıl, saniye gibi zararsız sayılar hariç "iddia" olabilecek sayılar: yüzde, para, büyük rakamlar
IDDIA_SAYI = re.compile(r"(?:%\s?\d[\d.,]*|\d[\d.,]*\s?(?:%|percent|yüzde|\$|dolar|dollars?|euro|tl|lira|million|"
                        r"billion|milyon|milyar|bin)|\$\s?\d[\d.,]*|yüzde\s?\d[\d.,]*)", re.I)


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


def dogrulanmamis_sayilar(is_: Is) -> list[str]:
    """Senaryodaki yüzde/para/büyük sayı iddialarından konu, açı ve kaynaklarda geçmeyenler."""
    v = is_.veri
    senaryo = str(v.get("senaryo", ""))
    kaynak = " ".join(str(v.get(a, "")) for a in ("konu", "aci", "neden", "klip_aciklama")).lower()
    kaynak += " " + " ".join(map(str, v.get("kaynaklar", []))).lower()
    supheli = []
    for iddia in IDDIA_SAYI.findall(senaryo):
        rakam = re.sub(r"[^\d]", "", iddia)
        if rakam and rakam not in re.sub(r"[^\d ]", "", kaynak):
            supheli.append(iddia.strip())
    return supheli


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
        # seslendirmeli videoda gerçek kontrol ikinci yapay zekadadır: Gemini onayı yoksa otomatik yayın yok
        if not denetim:
            sorunlar.append("Gemini denetimi yok (anahtar yok ya da kota doldu): uydurma iddia kontrol edilemedi")
        elif not denetim.get("onay"):
            sorunlar.append("Gemini onaylamadı: " + "; ".join(denetim.get("sorunlar", [])[:3]))
        etiket = SAHNE_ETIKETI.findall(str(v.get("senaryo", "")))
        if etiket:
            sorunlar.append("seslendirmede başlık etiketi okunuyor: " + ", ".join(etiket[:3]))
        supheli = dogrulanmamis_sayilar(is_)
        if supheli:
            sorunlar.append("kaynakta geçmeyen sayı/iddia: " + ", ".join(supheli[:4]))
    return sorunlar
