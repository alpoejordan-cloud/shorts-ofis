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
    return [y for y in liste if str(y.get("izin_belgesi", "")).strip() and y.get("klasor")
            and y.get("aktif", True) is not False]


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
                    # kampanyanın istediği bilgilendirme (ör. "Clip from @streamer's stream"), ilk 2 sn ekranda
                    "acilis_notu": str(y.get("acilis_notu") or "").strip(),
                    "kampanya": y.get("izin_belgesi", ""),
                    # yayinci_sesi: seslendirme yok, yayıncının kendi sesi korunur (kampanya kuralı)
                    "yayinci_sesi": bool(y.get("yayinci_sesi", False)),
                    "kapanis_notu": str(y.get("kapanis_notu") or "").strip(),
                    "zorunlu_etiketler": [str(e) for e in (y.get("zorunlu_etiketler") or [])],
                })
    if not adaylar:
        return None
    # agirlik: izinler.yaml'da yayıncı başına öncelik (varsayılan 1)
    agirlik = {y["ad"]: float(y.get("agirlik", 1) or 1) for y in izinli_yayincilar()}
    return random.choices(adaylar, weights=[agirlik.get(a["yayinci"], 1.0) for a in adaylar])[0]


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


UA = {"User-Agent": "ShortsOfis/1.0 (automated shorts editor)"}


def acik_resim(arama: str, adet: int = 4) -> list[dict[str, Any]]:
    """Openverse (anahtar gerekmez): ticari kullanıma ve değiştirmeye izin veren CC lisanslı fotoğraflar.
    Kaynak ve lisans açıklamaya yazılır."""
    r = requests.get("https://api.openverse.org/v1/images/",
                     params={"q": arama[:100], "license_type": "commercial,modification", "page_size": 20,
                             "mature": "false"}, headers=UA, timeout=30)
    r.raise_for_status()
    sonuc = []
    for v in r.json().get("results", []):
        en, boy = v.get("width") or 0, v.get("height") or 0
        if max(en, boy) < 1000 or min(en, boy) < 600 or not v.get("url"):
            continue
        lisans = f"CC {str(v.get('license', '')).upper()} {v.get('license_version', '')}".strip()
        sonuc.append({"id": f"ov-{v['id']}", "link": v["url"], "sayfa": v.get("foreign_landing_url", ""),
                      "sahip": v.get("creator") or "unknown", "baslik": v.get("title") or "", "lisans": lisans})
        if len(sonuc) >= adet:
            break
    return sonuc


def wikimedia_resim(arama: str, adet: int = 4) -> list[dict[str, Any]]:
    """Wikimedia Commons (anahtar gerekmez): yalnız CC BY / CC BY-SA / CC0 / kamu malı fotoğraflar."""
    import re

    r = requests.get("https://commons.wikimedia.org/w/api.php", params={
        "action": "query", "generator": "search", "gsrsearch": f"{arama[:80]} filetype:bitmap", "gsrnamespace": 6,
        "gsrlimit": 15, "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1600, "format": "json",
    }, headers=UA, timeout=30)
    r.raise_for_status()
    sayfalar = sorted((r.json().get("query", {}).get("pages", {}) or {}).values(), key=lambda p: p.get("index", 0))
    sonuc = []
    for p in sayfalar:
        bilgi = (p.get("imageinfo") or [{}])[0]
        meta = bilgi.get("extmetadata", {})
        lisans = str(meta.get("LicenseShortName", {}).get("value", ""))
        l = lisans.upper()
        if not (l.startswith(("CC BY", "CC0")) or "PUBLIC DOMAIN" in l) or "NC" in l.split("-") or "ND" in l:
            continue
        en, boy = bilgi.get("width") or 0, bilgi.get("height") or 0
        url = bilgi.get("thumburl") or bilgi.get("url")
        if max(en, boy) < 1000 or min(en, boy) < 600 or not url:
            continue
        sahip = re.sub(r"<[^>]+>", "", str(meta.get("Artist", {}).get("value", ""))).strip() or "unknown"
        sonuc.append({"id": f"wm-{p.get('pageid')}", "link": url, "sayfa": bilgi.get("descriptionurl", ""),
                      "sahip": sahip[:80], "baslik": str(p.get("title", "")).replace("File:", ""), "lisans": lisans})
        if len(sonuc) >= adet:
            break
    return sonuc


def foto_adaylari(arama: str) -> list[dict[str, Any]]:
    """Önce Openverse (bir kez yeniden dener), olmazsa Wikimedia Commons."""
    for kaynak, deneme in ((acik_resim, 2), (wikimedia_resim, 1)):
        for _ in range(deneme):
            try:
                sonuc = kaynak(arama)
            except requests.RequestException as e:
                log.warning("%s hatası (%s): %s", kaynak.__name__, arama, e)
                continue
            if sonuc:
                return sonuc
            break
    return []


def resim_indir(url: str, hedef: Path) -> Path:
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    if not r.headers.get("Content-Type", "").startswith("image/") or len(r.content) < 20000:
        raise RuntimeError("geçerli resim değil")
    hedef.write_bytes(r.content)
    return hedef


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


# ---- Kendi oyun kaydın (ör. GTA gameplay) ----

def oyun_kaydi_sahneleri(k: dict[str, Any], tohum: str, adet: int | None = None) -> list[dict[str, Any]]:
    """klipler/oyun_kayitlari gibi bir klasördeki uzun kayıtlardan, daha önce kullanılmamış
    rastgele anlar seçer. Her an ayrı bir sahne olur (kesme başına farklı görüntü)."""
    klasor_adi = k.get("oyun_kayit_klasoru")
    if not klasor_adi:
        return []
    klasor = KOK / klasor_adi
    dosyalar = sorted(p for p in klasor.glob("*") if p.suffix.lower() in VIDEO_UZANTI) if klasor.exists() else []
    if not dosyalar:
        return []
    from .kurgu import olcu

    kayit = VERI / "oyun_kullanilan.json"
    kullanilan = json.loads(kayit.read_text()) if kayit.exists() else {}
    rnd = random.Random(tohum)
    adet = adet or int(k.get("oyun_sahne_adedi", 16))
    pencere = 4.0
    sahneler = []
    for _ in range(adet * 4):
        if len(sahneler) >= adet:
            break
        dosya = rnd.choice(dosyalar)
        sure = olcu(str(dosya))[2]
        if sure < pencere * 2:
            continue
        bas = round(rnd.uniform(5.0, max(sure - pencere - 5.0, 5.0)), 1)
        dilim = f"{dosya.name}:{int(bas // pencere)}"
        if dilim in kullanilan.get(k["id"], []):
            continue
        kullanilan.setdefault(k["id"], []).append(dilim)
        sahneler.append({"tur": "video", "yol": str(dosya), "bas": bas})
    # kayıt tükenirse baştan kullanmaya izin ver
    if len(sahneler) < adet // 2:
        kullanilan[k["id"]] = []
    kayit.write_text(json.dumps(kullanilan))
    return sahneler


def gorsel_guc(yol: str) -> float:
    """Resmin ilk saniye gücü: renk canlılığı (Hasler-Süsstrunk) x netlik (Laplace varyansı). OpenCV yoksa 0."""
    try:
        import cv2
        import numpy as np

        img = cv2.imread(yol)
        if img is None:
            return 0.0
        img = cv2.resize(img, (320, int(320 * img.shape[0] / max(img.shape[1], 1))))
        b, g, r = [c.astype("float") for c in cv2.split(img)]
        rg, yb = np.abs(r - g), np.abs(0.5 * (r + g) - b)
        renk = np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2)
        netlik = cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        return float(renk * np.log1p(netlik))
    except Exception:
        return 0.0


def en_guclu_basa(sahneler: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """İlk 1 saniyede en çarpıcı görsel görünsün: resimler arasından en güçlüsü başa alınır (klip/video sırası korunur)."""
    if not sahneler or sahneler[0].get("tur") == "video" and sahneler[0].get("en_uzun", 0) > 5:
        return sahneler  # kampanya/yayıncı klibi: sıraya dokunma
    adaylar = [(gorsel_guc(s["yol"]), n) for n, s in enumerate(sahneler) if s.get("tur") == "resim" and s.get("yol")]
    if not adaylar:
        return sahneler
    _, en_iyi = max(adaylar)
    return [sahneler[en_iyi]] + [s for n, s in enumerate(sahneler) if n != en_iyi]


def topla(is_: Is, k: dict[str, Any]) -> None:
    sahneler: list[dict[str, Any]] = []
    lisans: list[str] = []
    gorsel_klasoru = is_.klasor / "gorseller"
    gorsel_klasoru.mkdir(exist_ok=True)

    oyun_sahneleri = oyun_kaydi_sahneleri(k, is_.id)
    resmi = []
    if k.get("resmi_havuz") and is_.veri.get("mod") != "izinli_klip":
        from .. import resmi_havuz

        metin = " ".join(str(is_.veri.get(a, "")) for a in ("konu", "senaryo", "baslik", "kanca_metni"))
        resmi = resmi_havuz.sahneler_sec(metin, int(k.get("hedef_gorsel", 7)), tohum=hash(is_.id) & 0xFFFF)
    if resmi:
        # varsayılan: yayıncının resmi medyası (Openverse/desen yalnızca havuz boşsa yedek)
        sahneler.extend(resmi)
        lisans.append("Görseller: Rockstar Games resmi medya (rockstargames.com/VI/media). "
                      "Grand Theft Auto VI © Rockstar Games / Take-Two Interactive.")
    elif oyun_sahneleri and is_.veri.get("mod") != "izinli_klip":
        sahneler.extend(oyun_sahneleri)
        lisans.append("Oyun görüntüsü: kanal sahibinin kendi oyun kaydı")
    elif is_.veri.get("mod") == "izinli_klip":
        hedef = gorsel_klasoru / ("klip" + Path(is_.veri["klip_yolu"]).suffix)
        shutil.copy2(is_.veri["klip_yolu"], hedef)
        sahneler.append({"tur": "video", "yol": str(hedef), "en_uzun": is_.veri.get("en_uzun_sn", 30),
                         # yayıncı sesi modunda klip sesi zaten ana ses (ses.wav), ayrıca karıştırılmaz
                         "orijinal_ses": 0 if is_.veri.get("yayinci_sesi") else k.get("klip_orijinal_ses", 0.25)})
        lisans.append(is_.veri.get("kredi", ""))
    else:
        kullanilan_pexels = set(json.loads((VERI / "pexels_kullanilan.json").read_text())
                                if (VERI / "pexels_kullanilan.json").exists() else [])
        acik_dosya = VERI / "acik_resim_kullanilan.json"
        kullanilan_acik = set(json.loads(acik_dosya.read_text()) if acik_dosya.exists() else [])
        krediler: list[str] = []
        hedef_foto = int(k.get("hedef_gorsel", 6))
        kelimeler = list(is_.veri.get("gorsel_kelimeler", []))
        foto_havuzu: dict[str, list[dict[str, Any]]] = {}

        def foto_ekle(kelime: str, sira: int) -> bool:
            if kelime not in foto_havuzu:
                foto_havuzu[kelime] = foto_adaylari(kelime)
            for secim in foto_havuzu[kelime]:
                if secim["id"] in kullanilan_acik:
                    continue
                kullanilan_acik.add(secim["id"])
                try:
                    yol = resim_indir(secim["link"], gorsel_klasoru / f"{sira:02d}_foto_{secim['id']}.jpg")
                except Exception as e:
                    log.warning("Fotoğraf indirilemedi (%s): %s", secim["link"], e)
                    continue
                sahneler.append({"tur": "resim", "yol": str(yol)})
                kredi = f"\"{secim['baslik']}\" by {secim['sahip']} ({secim['lisans']}) {secim['sayfa']}".strip()
                lisans.append("Fotoğraf: " + kredi)
                krediler.append(kredi)
                return True
            return False

        for sira, kelime in enumerate(kelimeler):
            adaylar = [a for a in stok_video(kelime) if a["id"] not in kullanilan_pexels]
            if adaylar:
                secim = adaylar[0]
                yol = indir(secim["link"], gorsel_klasoru / f"{sira:02d}_stok_{secim['id']}.mp4")
                sahneler.append({"tur": "video", "yol": str(yol)})
                lisans.append(f"Stok video {secim['id']} by {secim['sahip']} {secim['sayfa']}")
                kullanilan_pexels.add(secim["id"])
                continue
            # stok video yoksa: CC lisanslı gerçek fotoğraf (Openverse, yedek Wikimedia Commons)
            foto_ekle(kelime, sira)
        # hâlâ azsa aynı aramalardan ikinci fotoğraflar
        for sira, kelime in enumerate(kelimeler):
            if len(sahneler) >= hedef_foto:
                break
            foto_ekle(kelime, sira + 50)
        (VERI / "pexels_kullanilan.json").write_text(json.dumps(sorted(kullanilan_pexels)))
        acik_dosya.write_text(json.dumps(sorted(kullanilan_acik)))
        if krediler and is_.veri.get("aciklama") is not None and "Image credits" not in is_.veri["aciklama"]:
            is_.veri["aciklama"] += "\n\nImage credits:\n" + "\n".join(krediler)

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
                    if "402" in str(e) or "429" in str(e):
                        break  # servis bugün ücretsiz istek kabul etmiyor; boşuna bekleme
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

    # Hiçbir kaynak yeterli görüntü vermediyse, internet gerektirmeyen hareketli renk geçişleri eklenir
    en_az = int(k.get("en_az_sahne", 4))
    paletler = [("0x0f2027", "0x2c5364"), ("0x41295a", "0x2f0743"), ("0x134e5e", "0x71b280"),
                ("0x1d2b64", "0xf8cdda"), ("0x232526", "0x414345"), ("0x8e0e00", "0x1f1c18")]
    random.shuffle(paletler)
    eklenen_desen = 0
    while len(sahneler) < en_az and eklenen_desen < len(paletler):
        c0, c1 = paletler[eklenen_desen]
        sahneler.append({"tur": "desen", "renkler": [c0, c1]})
        eklenen_desen += 1
    if eklenen_desen:
        log.info("%s: %d sahne renk geçişiyle tamamlandı (stok/AI görsel yetersiz)", is_.id, eklenen_desen)

    if not sahneler:
        raise RuntimeError(
            "Hiç görsel bulunamadı (yapay zeka görsel servisi de cevap vermedi). İnternet bağlantısını kontrol et, "
            ".env içine PEXELS_API_ANAHTARI veya PIXABAY_API_ANAHTARI ekle ya da "
            f"gorseller/{k['id']}/ klasörüne görsel koy."
        )
    sahneler = en_guclu_basa(sahneler)
    is_.veri.update({"sahneler": sahneler, "lisanslar": lisans})
    log.info("%s: %d sahne hazır", is_.id, len(sahneler))
