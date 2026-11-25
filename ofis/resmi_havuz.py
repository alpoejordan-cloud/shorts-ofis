"""Resmi görsel havuzu: yalnızca yayıncının (Rockstar Games) kendi sitesinden resmi olarak indirilebilen
ekran görüntüleri ve kısa klipler. YouTube'dan veya başkalarının oynanış videolarından hiçbir şey alınmaz.

Kaynak: https://www.rockstargames.com/VI/media ("Download and share official videos, screenshots, and more").
Politika (https://support.rockstargames.com, "Policy on posting copyrighted Rockstar Games material"):
ticari olmayan kullanıma göz yumulur; spoiler, tek başına ara sahne, sızıntı, hile ve resmi olmayan port tanıtımı yasak.
Kanal para kazanmaya başlarsa Take-Two içerik kaldırabilir: bu not KAYNAKLAR.txt'ye de yazılır.

Klasör: gorseller/gta_resmi/{ekran/<Places|People>/<Ad>/*.jpg, video/*.mp4}, havuz.json, KAYNAKLAR.txt
Kur:  python -m ofis havuz-kur
"""
from __future__ import annotations

import json
import random
import re
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from .cekirdek import KOK, gunluk_al

log = gunluk_al("resmi_havuz")
KLASOR = KOK / "gorseller" / "gta_resmi"
MEDYA_SAYFASI = "https://www.rockstargames.com/VI/media"
INDIRMELER = {
    "ekran": "https://media-rockstargames-com.akamaized.net/VI/downloads/screenshots/GTAVI_Screenshots.zip",
    "video": "https://media-rockstargames-com.akamaized.net/VI/downloads/videos/GTAVI_Videos.zip",
}
RESMI_METIN = "https://www.rockstargames.com/VI/only-in-leonida"
POLITIKA = ("https://support.rockstargames.com/articles/7bNaeoMFTV0iUDGhStTXvz/"
            "policy-on-posting-copyrighted-rockstar-games-material")
KLIP_EN_UZUN = 3.0  # resmi kliplerden en fazla 3 sn, sesi tamamen kapalı (müzik Content ID riski)
GENEL = ["Vice City", "Jason and Lucia"]  # eşleşme yoksa kullanılan genel sahneler


def kur(klasor: Path = KLASOR) -> dict[str, Any]:
    """İndirilmiş resmi zip'leri (klasor/_zip) etiketli klasörlere açar, havuz.json ve KAYNAKLAR.txt yazar."""
    import requests

    zip_klasor = klasor / "_zip"
    zip_klasor.mkdir(parents=True, exist_ok=True)
    ogeler: list[dict[str, Any]] = []
    for tur, url in INDIRMELER.items():
        zip_yolu = zip_klasor / url.rsplit("/", 1)[-1]
        if not zip_yolu.exists():
            log.info("İndiriliyor (resmi): %s", url)
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(zip_yolu, "wb") as f:
                    for parca in r.iter_content(1 << 20):
                        f.write(parca)
        with zipfile.ZipFile(zip_yolu) as z:
            for ad in z.namelist():
                if ad.endswith("/") or ".." in ad:
                    continue
                parcalar = ad.replace("\\", "/").split("/")
                dosya = parcalar[-1]
                if not dosya or dosya.startswith("."):
                    continue
                if tur == "ekran":
                    kategori = parcalar[0] if len(parcalar) > 2 else "Genel"
                    etiket = parcalar[1] if len(parcalar) > 2 else "GTA VI"
                    hedef = klasor / "ekran" / kategori / etiket / dosya
                else:
                    kategori = "Video"
                    etiket = re.sub(r"_Video_Clip$|^GTAVI_", "", Path(dosya).stem).replace("_", " ")
                    hedef = klasor / "video" / dosya
                hedef.parent.mkdir(parents=True, exist_ok=True)
                if not hedef.exists():
                    hedef.write_bytes(z.read(ad))
                ogeler.append({"yol": str(hedef.relative_to(KOK)).replace("\\", "/"),
                               "tur": "resim" if tur == "ekran" else "video",
                               "kategori": kategori, "etiket": etiket, "kaynak": url})
    veri = {"olusturma": date.today().isoformat(), "kaynak_sayfa": MEDYA_SAYFASI, "politika": POLITIKA,
            "ogeler": ogeler}
    (klasor / "havuz.json").write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    kaynaklar_yaz(klasor, ogeler)
    log.info("Resmi havuz hazır: %d öğe", len(ogeler))
    return veri


def kaynaklar_yaz(klasor: Path, ogeler: list[dict[str, Any]]) -> None:
    satirlar = [
        "RESMİ GÖRSEL HAVUZU: KAYNAK VE LİSANS NOTLARI",
        f"Oluşturma: {date.today().isoformat()}",
        f"Kaynak sayfa: {MEDYA_SAYFASI} (Rockstar: 'Download and share official videos, screenshots, and more')",
        f"Politika: {POLITIKA}",
        "Not: Rockstar/Take-Two ticari olmayan hayran kullanımına göz yumar; spoiler, tek başına ara sahne, sızıntı,",
        "hile ve resmi olmayan port tanıtımı yasaktır. Kanal para kazanırsa içerik kaldırılabilir.",
        f"Kullanım kuralı (bu sistem): klipler en fazla {KLIP_EN_UZUN:.0f} sn, ses tamamen kapalı;",
        "seslendirme ve yorum bize ait; bilgiler yalnızca resmi metin ya da güvenilir haber kaynağından.",
        "",
        "DOSYA | TÜR | ETİKET | İNDİRME ADRESİ",
    ]
    satirlar += [f"{o['yol']} | {o['tur']} | {o['kategori']}/{o['etiket']} | {o['kaynak']}" for o in ogeler]
    (klasor / "KAYNAKLAR.txt").write_text("\n".join(satirlar) + "\n", encoding="utf-8")


def havuz(klasor: Path = KLASOR) -> list[dict[str, Any]]:
    try:
        return json.loads((klasor / "havuz.json").read_text(encoding="utf-8"))["ogeler"]
    except (OSError, ValueError, KeyError):
        return []


def etiketler(klasor: Path = KLASOR) -> list[str]:
    return sorted({o["etiket"] for o in havuz(klasor) if o["tur"] == "resim"})


def sahneler_sec(metin: str, adet: int = 7, klasor: Path = KLASOR, tohum: int | None = None) -> list[dict[str, Any]]:
    """Senaryo/konuda geçen yer ve kişilerin resmi görsellerini seçer; her sahneye ekranda gösterilecek
    etiketi ekler. En fazla bir kısa resmi klip (sessiz, ≤3 sn) eklenir."""
    rnd = random.Random(tohum)
    ogeler = havuz(klasor)
    if not ogeler:
        return []
    kucuk = metin.lower()
    resimler = [o for o in ogeler if o["tur"] == "resim"]
    eslesen = [o for o in resimler if _anildi(o["etiket"], kucuk)]
    genel = [o for o in resimler if o["etiket"] in GENEL]
    secilen: list[dict[str, Any]] = []
    for grup in (eslesen, genel, resimler):
        aday = [o for o in grup if o not in secilen]
        rnd.shuffle(aday)
        # çeşitlilik: her turda her etiketten en fazla bir görsel (anılan herkes/her yer görünsün)
        while aday and len(secilen) < adet:
            tur_etiket: set[str] = set()
            for o in list(aday):
                if len(secilen) >= adet:
                    break
                if o["etiket"] not in tur_etiket:
                    secilen.append(o)
                    aday.remove(o)
                    tur_etiket.add(o["etiket"])
        if len(secilen) >= adet:
            break
    sahneler = [{"tur": "resim", "yol": str(KOK / o["yol"]), "etiket": _etiket_metni(o)} for o in secilen]
    klipler = [o for o in ogeler if o["tur"] == "video" and _anildi(o["etiket"], kucuk)]
    if klipler:
        k = rnd.choice(klipler)
        sahneler.insert(1, {"tur": "video", "yol": str(KOK / k["yol"]), "bas": 0.0, "en_uzun": KLIP_EN_UZUN,
                            "etiket": k["etiket"]})
    return sahneler


def _anildi(etiket: str, kucuk_metin: str) -> bool:
    parcalar = [p for p in re.split(r"\s+and\s+|\s+", etiket.lower()) if len(p) > 3]
    return etiket.lower() in kucuk_metin or any(re.search(rf"\b{re.escape(p)}\b", kucuk_metin) for p in parcalar)


def _etiket_metni(o: dict[str, Any]) -> str:
    return ("PLACE: " if o["kategori"] == "Places" else "CHARACTER: ") + o["etiket"].upper()


# ---- "GTA 6'da en önemli yerler / karakterler" formatı: kaynak yalnızca Rockstar'ın resmi sayfası ----
KONULAR = [
    ("Jason Duval", "Who is Jason Duval in GTA 6? The official backstory"),
    ("Lucia Caminos", "Who is Lucia Caminos in GTA 6? The official backstory"),
    ("Cal Hampton", "Cal Hampton: Jason's paranoid friend in GTA 6"),
    ("Boobie Ike", "Boobie Ike: the Vice City legend of GTA 6"),
    ("DreQuan Priest", "DreQuan Priest and Only Raw Records in GTA 6"),
    ("Real Dimez", "Real Dimez: GTA 6's rap duo explained"),
    ("Raul Bautista", "Raul Bautista: GTA 6's reckless bank robber"),
    ("Brian Heder", "Brian Heder: GTA 6's old-school drug runner"),
    ("YERLER", "GTA 6: the must-see places of Leonida"),
]


def resmi_metin() -> str:
    """Rockstar'ın 'Only in Leonida' sayfası + resmi medya paketindeki yer adları (kaynak metin)."""
    from .kaynak import metin_al

    metin = metin_al(RESMI_METIN)
    yerler = sorted({o["etiket"] for o in havuz() if o["kategori"] == "Places"})
    if metin and yerler:
        metin += ("\n\nOfficial location names in the Rockstar GTA VI media pack (" + MEDYA_SAYFASI + "): "
                  + ", ".join(yerler) + ". Leonida is the state; Vice City is its city.")
    return metin


def fikir_uret(kanal_id: str) -> dict[str, Any] | None:
    """Daha önce işlenmemiş bir resmi karakter/yer konusu seçer; kaynak metni resmi sayfadır."""
    from .cekirdek import isler
    from .kaynak import metin_yolu

    metin = resmi_metin()
    if not metin or not havuz():
        return None
    islenen = {str(i.veri.get("resmi_konu")) for i in isler(kanal_id=kanal_id)}
    for anahtar, konu in KONULAR:
        if anahtar in islenen:
            continue
        yol = metin_yolu(RESMI_METIN + "#resmi")
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(metin, encoding="utf-8")
        aci = ("official facts only, as a quick 'what you need to know' explainer; name each place on screen"
               if anahtar == "YERLER" else
               f"official backstory of {anahtar} from Rockstar, what makes the character interesting; no spoilers")
        return {"konu": konu, "aci": aci, "neden": "official GTA 6 info, evergreen search interest",
                "kaynaklar": [RESMI_METIN], "kaynak_baslik": "Rockstar Games: Only in Leonida",
                "kaynak_metin": str(yol), "resmi_konu": anahtar, "format": "GTA 6 en önemli yerler/karakterler"}
    return None
