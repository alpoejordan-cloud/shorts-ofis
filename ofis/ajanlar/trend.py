"""Trend araştırmacı: YouTube, Google Trends ve Reddit'ten güncel konuları toplar,
kanalın nişine en uygun olanları seçer."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any

import requests

from ..cekirdek import VERI, gecmis_basliklar, gunluk_al, ortam
from ..yapay_zeka import sor_json

log = gunluk_al("trend")
UA = {"User-Agent": "shorts-ofis/0.1 (trend arastirma)"}


def youtube_populer(bolge: str, kategori: str | int | None, adet: int = 25) -> list[dict[str, str]]:
    anahtar = ortam("YOUTUBE_API_ANAHTARI")
    if not anahtar:
        log.warning("YOUTUBE_API_ANAHTARI yok, YouTube trendleri atlandı")
        return []
    parametre: dict[str, Any] = {
        "part": "snippet,statistics", "chart": "mostPopular",
        "regionCode": bolge, "maxResults": adet, "key": anahtar,
    }
    if kategori:
        parametre["videoCategoryId"] = str(kategori)
    r = requests.get("https://www.googleapis.com/youtube/v3/videos", params=parametre, timeout=30)
    r.raise_for_status()
    return [
        {
            "kaynak": "youtube",
            "baslik": v["snippet"]["title"],
            "link": f"https://youtube.com/watch?v={v['id']}",
            "guc": v.get("statistics", {}).get("viewCount", "0"),
        }
        for v in r.json().get("items", [])
    ]


def google_trends(bolge: str) -> list[dict[str, str]]:
    r = requests.get(f"https://trends.google.com/trending/rss?geo={bolge}", headers=UA, timeout=30)
    r.raise_for_status()
    kok = ET.fromstring(r.content)
    ns = {"ht": "https://trends.google.com/trending/rss"}
    sonuc = []
    for oge in kok.iter("item"):
        haber = oge.find("ht:news_item", ns)
        sonuc.append({
            "kaynak": "google_trends",
            "baslik": oge.findtext("title", ""),
            "link": haber.findtext("ht:news_item_url", "", ns) if haber is not None else "",
            "guc": oge.findtext("ht:approx_traffic", "", ns),
        })
    return sonuc


def reddit(altlar: list[str], adet: int = 15) -> list[dict[str, str]]:
    sonuc = []
    for alt in altlar:
        try:
            r = requests.get(f"https://www.reddit.com/r/{alt}/hot.json?limit={adet}", headers=UA, timeout=30)
            r.raise_for_status()
        except requests.RequestException as e:
            # Reddit izinsiz otomatik erişimi engelleyebiliyor; o zaman bu kaynak atlanır
            log.warning("Reddit okunamadı (%s), bu çalışmada Reddit atlanıyor", e)
            break
        for c in r.json().get("data", {}).get("children", []):
            d = c["data"]
            if d.get("stickied") or d.get("over_18"):
                continue
            sonuc.append({
                "kaynak": f"reddit/{alt}",
                "baslik": d["title"],
                "link": "https://reddit.com" + d["permalink"],
                "guc": str(d.get("score", 0)),
            })
    return sonuc


def ham_trendler(k: dict[str, Any]) -> list[dict[str, str]]:
    ayar = k.get("trend", {})
    toplam: list[dict[str, str]] = []
    islem = [
        ("youtube", lambda: youtube_populer(ayar["youtube"].get("bolge", "US"), ayar["youtube"].get("kategori"))),
        ("google_trends", lambda: google_trends(ayar["google_trends"].get("bolge", "US"))),
        ("reddit", lambda: reddit(ayar["reddit"])),
    ]
    for ad, fn in islem:
        if ad not in ayar:
            continue
        try:
            toplam += fn()
        except Exception as e:  # bir kaynak çökerse diğerleri devam eder
            log.warning("%s kaynağı hata verdi: %s", ad, e)
    return toplam


def analist_notlari(kanal_id: str) -> str:
    yol = VERI / "icgoruler" / f"{kanal_id}.json"
    if not yol.exists():
        return "Henüz veri yok."
    return yol.read_text(encoding="utf-8")[:2000]


DIL_ADI = {"tr": "Türkçe (Turkish)", "en": "English"}
TR_HARF = set("ğüşıöçĞÜŞİÖÇ")


def dil_uygun(fikir: dict[str, Any], k: dict[str, Any]) -> bool:
    """İngilizce kanalın fikrinde Türkçe harf olmamalı (özel adlar için 1 harfe tolerans)."""
    if k.get("dil") != "en":
        return True
    metin = str(fikir.get("konu", "")) + " " + str(fikir.get("aci", ""))
    return sum(c in TR_HARF for c in metin) <= 1


def fikir_bul(k: dict[str, Any], adet: int) -> list[dict[str, Any]]:
    """Kanal için `adet` tane video fikri döner."""
    ham = ham_trendler(k)
    if not ham:
        log.warning("%s: hiç trend bulunamadı, model kendi bilgisinden fikir üretecek", k["id"])
    liste = "\n".join(f"- [{t['kaynak']}] {t['baslik']} ({t['link']})" for t in ham[:80])
    gecmis = "\n".join(f"- {b}" for b in gecmis_basliklar(k["id"], 60))
    sistem = (
        "Sen bir YouTube Shorts kanalının trend araştırmacısısın. Sadece kanalın nişine uyan, "
        "bugün ilgi gören ve özgün yorum katılabilecek konuları seçersin. Siyaset, trajedi, "
        "çocuklara yönelik içerik, yetişkin içerik ve doğrulanamayan söylentileri seçmezsin. "
        "Cevabın sadece JSON olur."
    )
    kullanici = f"""Kanal nişi: {k['nis']}
Kanal dili: {k['dil']}

Bugünkü trendler:
{liste or '(trend listesi boş; nişte her zaman ilgi gören, zamansız bir konu öner)'}

Daha önce işlenen konular (tekrar etme):
{gecmis or '(yok)'}

Analistin notları (neyin tuttuğu):
{analist_notlari(k['id'])}

En iyi {adet} konuyu seç. JSON biçimi:
{{"fikirler": [{{"konu": "kısa konu", "aci": "videonun özgün bakış açısı", "neden": "neden şimdi ilgi görür", "kaynaklar": ["link1", "link2"]}}]}}

ÖNEMLİ: "konu" ve "aci" alanlarını kanalın dilinde yaz: {DIL_ADI.get(k['dil'], k['dil'])}.
Write "konu" and "aci" in {DIL_ADI.get(k['dil'], k['dil'])}."""
    fikirler: list[dict[str, Any]] = []
    for deneme in range(2):
        cevap = sor_json(sistem, kullanici, sicaklik=0.7)
        fikirler = cevap.get("fikirler", []) if isinstance(cevap, dict) else []
        fikirler = [f for f in fikirler if isinstance(f, dict) and f.get("konu")][:adet]
        if all(dil_uygun(f, k) for f in fikirler):
            break
        log.info("%s: fikirler kanal dilinde değil, yeniden isteniyor", k["id"])
        kullanici += f"\n\nPrevious answer was in the wrong language. konu and aci MUST be in {DIL_ADI.get(k['dil'], k['dil'])}."
    # son çare: yine yanlış dildeyse konu/açı çevrilir
    from .senarist import konuyu_cevir

    fikirler = [f if dil_uygun(f, k) else konuyu_cevir(f, k) for f in fikirler]
    log.info("%s: %d fikir bulundu", k["id"], len(fikirler))
    (VERI / "son_trendler").mkdir(exist_ok=True)
    (VERI / "son_trendler" / f"{k['id']}.json").write_text(
        json.dumps({"ham": ham[:80], "secilen": fikirler}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return fikirler
