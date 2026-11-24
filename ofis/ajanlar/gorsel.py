"""Görsel sorumlusu: videonun arka plan görüntülerini toplar.

Kurallar:
- Sadece lisansı uygun kaynaklar: Pexels/Pixabay, senin klasöre koyduğun görseller ve
  izin belgesi kayıtlı yayıncıların klipleri.
- İzin belgesi boş olan yayıncının klibi ASLA kullanılmaz.
"""
from __future__ import annotations

import json
import random
import shutil
from pathlib import Path
from typing import Any

import requests

from ..cekirdek import KOK, VERI, Is, gunluk_al, isler, ortam, yaml_oku

log = gunluk_al("gorsel")
VIDEO_UZANTI = {".mp4", ".mov", ".mkv", ".webm"}
RESIM_UZANTI = {".jpg", ".jpeg", ".png", ".webp"}


# ---- İzinli yayıncı klipleri ----

def izinli_yayincilar() -> list[dict[str, Any]]:
    liste = yaml_oku("izinler.yaml").get("izinli_yayincilar", []) or []
    return [y for y in liste if str(y.get("izin_belgesi", "")).strip() and y.get("klasor")]


def kullanilmis_klipler() -> set[str]:
    return {i.veri.get("klip_yolu", "") for i in isler()} - {""}


def klip_sec(k: dict[str, Any]) -> dict[str, Any] | None:
    """İzinli ve daha önce kullanılmamış bir klip seçer; yoksa None."""
    kullanilan = kullanilmis_klipler()
    adaylar = []
    for y in izinli_yayincilar():
        if y.get("kanallar") and k["id"] not in y["kanallar"]:
            continue
        klasor = KOK / y["klasor"]
        if not klasor.exists():
            continue
        for dosya in sorted(klasor.iterdir()):
            if dosya.suffix.lower() in VIDEO_UZANTI and str(dosya) not in kullanilan:
                aciklama_dosyasi = dosya.with_suffix(".txt")
                adaylar.append({
                    "yayinci": y["ad"],
                    "klip_yolu": str(dosya),
                    "klip_aciklama": aciklama_dosyasi.read_text(encoding="utf-8").strip()
                    if aciklama_dosyasi.exists() else dosya.stem.replace("_", " "),
                    "kredi": (y.get("kredi_metni") or "Klip: {ad} ({url}), izinle kullanılmıştır.").format(
                        ad=y["ad"], url=y.get("kanal_url", "")
                    ),
                    "en_uzun_sn": y.get("en_uzun_sn", 30),
                })
    return random.choice(adaylar) if adaylar else None


# ---- Pexels ----

def pexels_video(arama: str, adet: int = 3) -> list[dict[str, Any]]:
    anahtar = ortam("PEXELS_API_ANAHTARI")
    if not anahtar:
        return []
    r = requests.get(
        "https://api.pexels.com/videos/search",
        params={"query": arama, "orientation": "portrait", "size": "medium", "per_page": adet},
        headers={"Authorization": anahtar}, timeout=30,
    )
    r.raise_for_status()
    sonuc = []
    for v in r.json().get("videos", []):
        dosyalar = [f for f in v.get("video_files", []) if (f.get("height") or 0) >= 1280 and f.get("link")]
        if not dosyalar:
            continue
        en_iyi = min(dosyalar, key=lambda f: abs((f.get("height") or 0) - 1920))
        sonuc.append({"id": v["id"], "link": en_iyi["link"], "sayfa": v.get("url", ""),
                      "sahip": v.get("user", {}).get("name", ""), "sure": v.get("duration", 0)})
    return sonuc


def pixabay_video(arama: str, adet: int = 3) -> list[dict[str, Any]]:
    anahtar = ortam("PIXABAY_API_ANAHTARI")
    if not anahtar:
        return []
    r = requests.get("https://pixabay.com/api/videos/",
                     params={"key": anahtar, "q": arama[:100], "per_page": max(3, adet), "safesearch": "true"},
                     timeout=30)
    r.raise_for_status()
    sonuc = []
    for v in r.json().get("hits", []):
        secenek = [x for x in v.get("videos", {}).values() if x.get("url") and (x.get("height") or 0) >= 720]
        if not secenek:
            continue
        en_iyi = max(secenek, key=lambda x: x.get("height") or 0)
        sonuc.append({"id": f"pixabay-{v['id']}", "link": en_iyi["url"], "sayfa": v.get("pageURL", ""),
                      "sahip": v.get("user", ""), "sure": v.get("duration", 0)})
    return sonuc[:adet]


def stok_video(arama: str) -> list[dict[str, Any]]:
    """Önce Pexels, sonra Pixabay; anahtar yoksa boş döner."""
    for kaynak in (pexels_video, pixabay_video):
        try:
            sonuc = kaynak(arama)
        except requests.RequestException as e:
            log.warning("%s hatası (%s): %s", kaynak.__name__, arama, e)
            continue
        if sonuc:
            return sonuc
    return []


def ai_gorsel(istem: str, hedef: Path, seed: int = 0) -> Path:
    """Ücretsiz Pollinations servisiyle 1080x1920 görsel üretir (anahtar gerekmez).
    Adres .env içindeki AI_GORSEL_ADRESI ile değiştirilebilir."""
    from urllib.parse import quote

    taban = ortam("AI_GORSEL_ADRESI", "https://image.pollinations.ai/prompt/")
    url = f"{taban}{quote(istem)}?width=1080&height=1920&nologo=true&seed={seed}"
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    if not r.headers.get("Content-Type", "").startswith("image/") or len(r.content) < 5000:
        raise RuntimeError("servis görsel döndürmedi")
    hedef.write_bytes(r.content)
    return hedef


def indir(url: str, hedef: Path) -> Path:
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(hedef, "wb") as f:
            for parca in r.iter_content(1 << 16):
                f.write(parca)
    return hedef


def yerel_gorseller(k: dict[str, Any]) -> list[Path]:
    klasor = KOK / "gorseller" / k["id"]
    if not klasor.exists():
        return []
    return [p for p in sorted(klasor.iterdir()) if p.suffix.lower() in RESIM_UZANTI | VIDEO_UZANTI]


def topla(is_: Is, k: dict[str, Any]) -> None:
    sahneler: list[dict[str, Any]] = []
    lisans: list[str] = []
    gorsel_klasoru = is_.klasor / "gorseller"
    gorsel_klasoru.mkdir(exist_ok=True)

    if is_.veri.get("mod") == "izinli_klip":
        hedef = gorsel_klasoru / ("klip" + Path(is_.veri["klip_yolu"]).suffix)
        shutil.copy2(is_.veri["klip_yolu"], hedef)
        sahneler.append({"tur": "video", "yol": str(hedef), "en_uzun": is_.veri.get("en_uzun_sn", 30),
                         "orijinal_ses": k.get("klip_orijinal_ses", 0.25)})
        lisans.append(is_.veri.get("kredi", ""))
    else:
        kullanilan_pexels = set(json.loads((VERI / "pexels_kullanilan.json").read_text())
                                if (VERI / "pexels_kullanilan.json").exists() else [])
        for sira, kelime in enumerate(is_.veri.get("gorsel_kelimeler", [])):
            adaylar = [a for a in stok_video(kelime) if a["id"] not in kullanilan_pexels]
            if not adaylar:
                continue
            secim = adaylar[0]
            yol = indir(secim["link"], gorsel_klasoru / f"{sira:02d}_stok_{secim['id']}.mp4")
            sahneler.append({"tur": "video", "yol": str(yol)})
            lisans.append(f"Stok video {secim['id']} by {secim['sahip']} {secim['sayfa']}")
            kullanilan_pexels.add(secim["id"])
        (VERI / "pexels_kullanilan.json").write_text(json.dumps(sorted(kullanilan_pexels)))

        # yapay zeka görselleri (izin gerektirmez; her video için yeni üretilir)
        ai_adet = int(k.get("ai_gorsel_adedi", 0))
        if len(sahneler) < 3:  # stok video anahtarı yoksa veya az bulunduysa yapay zeka tamamlar
            ai_adet = max(ai_adet, 5 - len(sahneler))
        if ai_adet:
            kelimeler = is_.veri.get("gorsel_kelimeler") or [is_.veri.get("konu", "")]
            istemler = [kelimeler[n % len(kelimeler)] for n in range(ai_adet)]
            uretilen = 0
            for sira, istem in enumerate(istemler):
                hedef = gorsel_klasoru / f"ai_{sira:02d}.jpg"
                tam_istem = f"{istem}, {k.get('ai_stil', 'cinematic, vertical composition, highly detailed')}"
                try:
                    ai_gorsel(tam_istem, hedef, seed=abs(hash((is_.id, sira))) % 10**6)
                except Exception as e:
                    log.warning("AI görsel üretilemedi (%s): %s", istem, e)
                    continue
                konum = min(len(sahneler), sira * 2)
                sahneler.insert(konum, {"tur": "resim", "yol": str(hedef)})
                lisans.append(f"Yapay zeka görseli: {tam_istem}")
                uretilen += 1
            if uretilen:
                is_.veri["yapay_icerik"] = True  # YouTube'a sentetik içerik olarak bildirilir

        # senin koyduğun görseller (ör. GTA ekran görüntüleri) varsa araya eklenir
        yereller = yerel_gorseller(k)
        random.shuffle(yereller)
        for p in yereller[: k.get("yerel_gorsel_adedi", 3)]:
            tur = "resim" if p.suffix.lower() in RESIM_UZANTI else "video"
            sahneler.insert(min(len(sahneler), 1 + len(sahneler) // 2), {"tur": tur, "yol": str(p)})
            lisans.append(f"Yerel görsel: {p.name}")

    if not sahneler:
        raise RuntimeError(
            "Hiç görsel bulunamadı (yapay zeka görsel servisi de cevap vermedi). İnternet bağlantısını kontrol et, "
            ".env içine PEXELS_API_ANAHTARI veya PIXABAY_API_ANAHTARI ekle ya da "
            f"gorseller/{k['id']}/ klasörüne görsel koy."
        )
    is_.veri.update({"sahneler": sahneler, "lisanslar": lisans})
    log.info("%s: %d sahne hazır", is_.id, len(sahneler))
