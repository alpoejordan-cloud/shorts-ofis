"""SEO: her yüklemede başlık, açıklama ve etiketleri YouTube Shorts aramasına göre düzenler.

Kurallar (tüm kanallar, otomatik):
- Başlık en fazla 60 karakter, ana anahtar kelime başta, sonda #shorts.
- Açıklama: ilk satır anahtar kelimeli kısa özet; 2-3 cümle; kampanya kredisi/linki/zorunlu etiketleri
  korunur (kampanya kuralı her zaman kazanır); sonda 3-5 hashtag.
- Etiketler (tags): 10-15 ilgili etiket, toplam en fazla 500 karakter.
Kanal ayarında `seo:` bloğu varsa (ana_anahtar, etiketler, hashtagler) varsayılanların yerine geçer.
"""
from __future__ import annotations

import re
from typing import Any

VARSAYILAN: dict[str, dict[str, Any]] = {
    "teknoloji_en": {"ana_anahtar": "AI",
                     "etiketler": ["AI news", "tech news", "artificial intelligence", "technology", "tech explained",
                                   "gadgets", "AI tools", "tech shorts"],
                     "hashtagler": ["#AI", "#TechNews"]},
    "finans_tr": {"ana_anahtar": "Para",
                  "etiketler": ["kişisel finans", "para yönetimi", "ekonomi", "birikim", "bütçe", "tasarruf",
                                "enflasyon", "finans"],
                  "hashtagler": ["#finans", "#para"]},
    "gta_en": {"ana_anahtar": "GTA 6",
               "etiketler": ["GTA 6", "GTA VI", "Grand Theft Auto VI", "GTA 6 gameplay", "GTA 6 funny moments",
                             "GTA 6 clips", "gaming", "open world games"],
               "hashtagler": ["#GTA6", "#GTAVI", "#gaming"]},
}
BASLIK_SINIR = 60
ETIKET_KARAKTER = 500


def ayar(k: dict[str, Any]) -> dict[str, Any]:
    temel = dict(VARSAYILAN.get(k.get("id", ""), {"ana_anahtar": "", "etiketler": [], "hashtagler": []}))
    temel.update(k.get("seo") or {})
    return temel


def _kes(metin: str, sinir: int) -> str:
    if len(metin) <= sinir:
        return metin
    kesik = metin[:sinir].rsplit(" ", 1)[0].rstrip(" -:|,")
    return kesik or metin[:sinir]


def baslik(ham: str, k: dict[str, Any]) -> str:
    ana = ayar(k)["ana_anahtar"]
    govde = re.sub(r"#shorts", "", ham, flags=re.IGNORECASE).strip(" -|")
    govde = re.sub(r"\s+", " ", govde)
    if ana and ana.lower() not in govde.lower() and not (ana == "GTA 6" and "gta vi" in govde.lower()):
        govde = f"{ana}: {govde}"
    elif ana and not govde.lower().startswith(ana.lower()):
        # anahtar kelime var ama başta değil: başa al (anlam bozulmadan, "X | başlık")
        konum = govde.lower().find(ana.lower())
        if konum > 25:
            govde = f"{ana} | {govde}"
    return _kes(govde, BASLIK_SINIR - len(" #shorts")) + " #shorts"


def _hashtagler(veri: dict[str, Any], k: dict[str, Any]) -> list[str]:
    sonuc: list[str] = []
    for h in list(veri.get("zorunlu_etiketler") or []) + list(ayar(k)["hashtagler"]):
        h = "#" + h.lstrip("#").replace(" ", "")
        if h.lower() not in {x.lower() for x in sonuc}:
            sonuc.append(h)
    return sonuc[:5]


def aciklama(veri: dict[str, Any], k: dict[str, Any], son_baslik: str) -> str:
    ana = ayar(k)["ana_anahtar"]
    zorunlu = [str(e) for e in (veri.get("zorunlu_etiketler") or [])]
    kredi = str(veri.get("kredi") or "").strip()
    # mevcut açıklamadan kredi ve hashtag satırlarını ayıkla; asıl metni al
    satirlar = [s.strip() for s in str(veri.get("aciklama", "")).splitlines()]
    govde_satirlari = [s for s in satirlar if s and s != kredi and not re.fullmatch(r"(#\S+\s*)+", s)]
    cumleler = re.split(r"(?<=[.!?])\s+", " ".join(govde_satirlari[:3]).strip()) if govde_satirlari else []
    ozet = son_baslik.replace("#shorts", "").strip()
    ilk = ozet if (not ana or ana.lower() in ozet.lower()) else f"{ana}: {ozet}"
    govde = " ".join(c for c in cumleler[:3] if c and c.lower() != ilk.lower())
    parcalar = [ilk + ("." if not ilk.endswith((".", "!", "?")) else "")]
    if govde:
        parcalar.append(govde)
    # kalan satırlar (kaynaklar, lisanslar, müzik/görsel kredileri) aynen korunur
    kalan = "\n".join(s for s in satirlar[3:] if s and s != kredi and not re.fullmatch(r"(#\S+\s*)+", s))
    if kredi:
        parcalar.append(kredi)  # kampanya kredisi/linki: kampanya kuralı, her zaman korunur
    if kalan:
        parcalar.append(kalan)
    hashtag = _hashtagler(veri, k)
    eksik = [z for z in zorunlu if z.lower() not in " ".join(hashtag).lower()]
    parcalar.append(" ".join(hashtag + eksik))
    return "\n\n".join(parcalar)[:4900]


def etiketler(veri: dict[str, Any], k: dict[str, Any]) -> list[str]:
    adaylar: list[str] = []
    if veri.get("yayinci"):
        adaylar.append(str(veri["yayinci"]).split("(")[0].strip())
    adaylar += [str(e) for e in (veri.get("zorunlu_etiketler") or [])]
    adaylar += list(ayar(k)["etiketler"]) + [str(e) for e in (veri.get("etiketler") or [])]
    sonuc: list[str] = []
    toplam = 0
    for e in adaylar:
        e = re.sub(r"\s+", " ", e.lstrip("#")).strip()
        if not e or e.lower() in {x.lower() for x in sonuc} or len(e) > 60:
            continue
        maliyet = len(e) + 2 + (2 if " " in e else 0)  # YouTube virgül ve tırnakları da sayar
        if toplam + maliyet > ETIKET_KARAKTER or len(sonuc) >= 15:
            break
        sonuc.append(e)
        toplam += maliyet
    return sonuc


def uygula(veri: dict[str, Any], k: dict[str, Any]) -> dict[str, Any]:
    """YouTube snippet alanlarını döner (title, description, tags, dil, kategori)."""
    b = baslik(str(veri.get("baslik", "")), k)
    return {
        "title": b,
        "description": aciklama(veri, k, b),
        "tags": etiketler(veri, k),
        "categoryId": str(k.get("youtube_kategori", 22)),
        "defaultLanguage": k["dil"],
        "defaultAudioLanguage": k["dil"],
    }
