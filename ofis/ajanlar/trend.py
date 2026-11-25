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



def gemini_beyin_firtinasi(fikirler: list[dict[str, Any]], k: dict[str, Any], sistem: str, kullanici: str,
                           adet: int, tur: int = 2) -> list[dict[str, Any]]:
    """Ollama fikir önerdi; Gemini puanlar/eleştirir, Ollama zayıfları değiştirir (en fazla 2 tur)."""
    from .. import gemini

    for n in range(tur):
        if not fikirler:
            break
        degerler = gemini.fikirleri_elestir(fikirler, k)
        if not degerler:
            break
        zayif = []
        for d in degerler:
            try:
                no, puan = int(d.get("no", 0)) - 1, float(d.get("puan", 10))
            except (TypeError, ValueError):
                continue
            if not 0 <= no < len(fikirler):
                continue
            fikirler[no]["gemini_puan"] = puan
            if d.get("daha_iyi_aci") and puan >= 6:
                fikirler[no]["aci"] = str(d["daha_iyi_aci"])
            if puan < 6:
                zayif.append(f"#{no + 1} {fikirler[no].get('konu')}: {d.get('elestiri', '')}")
        if not zayif:
            break
        log.info("%s: Gemini zayıf buldu (tur %d): %s", k["id"], n + 1, " | ".join(zayif))
        try:
            cevap = sor_json(sistem, kullanici + "\n\nAn editor rejected these ideas:\n" + "\n".join(zayif)
                             + f"\nReturn {adet} ideas again in the same JSON, replacing the rejected ones with "
                             "better topics from the trend list. Keep the good ones.", sicaklik=0.7)
        except Exception:
            break
        yeni = cevap.get("fikirler", []) if isinstance(cevap, dict) else []
        yeni = [f for f in yeni if isinstance(f, dict) and f.get("konu")][:adet]
        if yeni:
            fikirler = yeni
    return fikirler

def fikir_bul(k: dict[str, Any], adet: int) -> list[dict[str, Any]]:
    """Kanal için en fazla `adet` video fikri döner. Her fikir gerçek bir haber makalesine bağlıdır
    (kaynaklar = o makalenin linki, kaynak_metin = saklanan metin). Makaleyle uyuşmayan fikir elenir."""
    from .. import kaynak
    from ..cekirdek import isler
    from .senarist import konuyu_cevir

    try:
        makale = kaynak.makaleler(k)
    except Exception as e:
        log.warning("%s: haber akışları okunamadı: %s", k["id"], e)
        makale = []
    kullanilmis = {lnk for i in isler(kanal_id=k["id"]) for lnk in i.veri.get("kaynaklar", [])}
    makale = [m for m in makale if m["link"] not in kullanilmis][:50]
    if not makale:
        # kaynaksız fikir = uydurma riski: bugün bu kanal için üretim yapılmaz
        log.warning("%s: güncel kaynak makale yok, fikir üretilmedi", k["id"])
        return []
    liste = "\n".join(f"{n + 1}. [{m['kaynak']}] {m['baslik']} | {m['ozet'][:180]}" for n, m in enumerate(makale))
    gecmis = "\n".join(f"- {b}" for b in gecmis_basliklar(k["id"], 60))
    dil_adi = DIL_ADI.get(k["dil"], k["dil"])
    sistem = (
        "Sen bir YouTube Shorts kanalının haber editörüsün. Her fikir, listedeki TEK bir haber makalesine dayanır; "
        "makalede olmayan bir konu veya iddia uydurmazsın. Sadece kanalın nişine uyan, bugün ilgi gören ve özgün "
        "yorum katılabilecek haberleri seçersin. Siyaset, trajedi, suç, çocuklara yönelik ve yetişkin içerik seçmezsin. "
        "Cevabın sadece JSON olur."
    )
    istenen = adet + 2  # bazıları makaleyle uyuşmayıp elenebilir
    kullanici = f"""Kanal nişi: {k['nis']}
Kanal dili: {k['dil']}

Bugünkü haber makaleleri (numaralı):
{liste}

Daha önce işlenen konular (tekrar etme):
{gecmis or '(yok)'}

Analistin notları (neyin tuttuğu):
{analist_notlari(k['id'])}

En iyi {istenen} haberi seç. "konu" makalenin asıl konusunu aynı anahtar kelimelerle özetler.
JSON biçimi:
{{"fikirler": [{{"makale_no": 3, "konu": "makalenin konusu", "aci": "videonun özgün bakış açısı", "neden": "neden şimdi ilgi görür"}}]}}

ÖNEMLİ: "konu" ve "aci" alanlarını kanalın dilinde yaz: {dil_adi}.
Write "konu" and "aci" in {dil_adi}. Every idea MUST use one makale_no from the list."""
    fikirler: list[dict[str, Any]] = []
    for deneme in range(2):
        cevap = sor_json(sistem, kullanici, sicaklik=0.6)
        fikirler = cevap.get("fikirler", []) if isinstance(cevap, dict) else []
        fikirler = [f for f in fikirler if isinstance(f, dict) and f.get("konu")][:istenen]
        if all(dil_uygun(f, k) for f in fikirler):
            break
        log.info("%s: fikirler kanal dilinde değil, yeniden isteniyor", k["id"])
        kullanici += f"\n\nPrevious answer was in the wrong language. konu and aci MUST be in {dil_adi}."
    fikirler = gemini_beyin_firtinasi(fikirler, k, sistem, kullanici, istenen)
    fikirler = [f if dil_uygun(f, k) else konuyu_cevir(f, k) for f in fikirler]

    secilen: list[dict[str, Any]] = []
    for f in fikirler:
        try:
            no = int(f.get("makale_no", 0)) - 1
        except (TypeError, ValueError):
            continue
        if not 0 <= no < len(makale) or any(s["kaynaklar"] == [makale[no]["link"]] for s in secilen):
            continue
        bagli = kaynak.fikre_bagla(f, makale[no])
        if bagli:
            secilen.append(bagli)
        if len(secilen) >= adet:
            break
    log.info("%s: %d fikir kaynak makaleye bağlandı (%d aday)", k["id"], len(secilen), len(fikirler))
    (VERI / "son_trendler").mkdir(exist_ok=True)
    (VERI / "son_trendler" / f"{k['id']}.json").write_text(
        json.dumps({"makaleler": makale, "adaylar": fikirler, "secilen": secilen}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return secilen
