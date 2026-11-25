"""Kaynak haber: her video fikri gerçek bir makaleye bağlanır, senarist yalnızca o metinle yazar.

- RSS akışlarından son haberleri toplar (kanal ayarı `trend.rss` ile değiştirilebilir).
- Makale metnini trafilatura (Apache-2.0) ile çeker, veri/kaynak_metin/ altında saklar.
- Konu ile makale uyuşmuyorsa fikir elenir.
Metin yalnızca bilgi doğrulaması için yerelde tutulur, videoda yeniden yayınlanmaz.
"""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Any

from .cekirdek import VERI, gunluk_al

log = gunluk_al("kaynak")
KLASOR = VERI / "kaynak_metin"
UA = "Mozilla/5.0 (compatible; shorts-ofis/0.2; haber dogrulama)"
EN_AZ_METIN = 400
EN_ESKI_SAAT = 48  # haber tazeliği: son 48 saat, en yenisi önce

RSS_VARSAYILAN: dict[str, dict[str, Any]] = {
    "teknoloji_en": {"akislar": ["https://www.theverge.com/rss/index.xml", "https://techcrunch.com/feed/",
                                 "https://www.engadget.com/rss.xml",
                                 "https://feeds.arstechnica.com/arstechnica/technology-lab"],
                     "filtre": []},
    "gta_en": {"akislar": ["https://www.pcgamer.com/rss/", "https://www.gamesradar.com/feeds/all/",
                           "https://www.eurogamer.net/feed", "https://www.videogameschronicle.com/feed/",
                           "https://www.thegamer.com/feed/"],
               "filtre": ["gta", "grand theft auto", "rockstar"]},
    "gta_tr": {"akislar": ["https://www.pcgamer.com/rss/", "https://www.gamesradar.com/feeds/all/"],
               "filtre": ["gta", "grand theft auto", "rockstar"]},
    "finans_tr": {"akislar": ["https://www.bloomberght.com/rss", "https://www.aa.com.tr/tr/rss/default?cat=ekonomi",
                              "https://www.ntv.com.tr/ekonomi.rss"],
                  "filtre": []},
}

# Kanala uygun olmayan konular: haber başlığı/özetinde geçerse makale hiç listelenmez, metinde yoğunsa fikir elenir.
YASAK_KONU: dict[str, str] = {
    "siyaset": r"\b(elections?|electoral|president(?:ial)?|congress|senate|senator|parliament|white house|trump|"
               r"biden|democrats?|republicans?|prime minister|minister|campaign rally|tariffs?|sanctions?|"
               r"seçim\w*|cumhurbaşkan\w*|bakan\w*|meclis\w*|milletvekil\w*|muhalefet\w*|iktidar\w*|"
               r"partisi\w*|partiler\w*|partili\w*)\b",
    "savaş": r"\b(wars?|warfare|military|army|missiles?|airstrikes?|troops|invasion|ceasefire|drones? strikes?|"
             r"israel\w*|iran\w*|ukrain\w*|russia\w*|gaza|hamas|hezbollah|pentagon|nato|"
             r"savaş\w*|asker\w*|füze\w*|saldırı\w*|ateşkes\w*|ordu\w*|işgal\w*)\b",
    "korsanlık": r"\b(pira(?:cy|ted|te)|illegal(?:ly)?|illicit|leaked builds?|cracked (?:version|copy|build)|"
                 r"crack(?:ing)? group|torrents?|warez|recomp\w*|unofficial ports?|korsan\w*|yasa ?dışı\w*|"
                 r"kaçak\w*)\b",
    "suç": r"\b(murder(?:ed|er|ers|s)?|homicide|mass shooting|stabb(?:ed|ing)|arrest(?:ed|s)?|indicted|convicted|"
           r"kidnap\w*|cinayet\w*|öldürdü\w*|öldürül\w*|tutuklan\w*|gözaltı\w*|bıçakla\w*|silahlı saldırı\w*)\b",
    "sağlık": r"\b(cancer|vaccines?|cures?|disease|diagnos\w*|clinical trials?|covid|obesity drugs?|ozempic|"
              r"kanser\w*|aşı(?:sı|ları|lar|lama\w*)?|tedavi\w*|hastalı\w*|ilaç\w*)\b",
}
# finans kanalında belirli hisse/coin tavsiyesi sayılabilecek haberler
YASAK_FINANS = (r"\b(bitcoin|btc|ethereum|altcoin\w*|kripto\w*|coin\w*|memecoin\w*|hedef fiyat\w*|al tavsiye\w*|"
                r"sat tavsiye\w*|hisse önerisi|model portföy\w*|price target|buy rating|top stocks? to buy)\b")


def yasak_konu(metin: str, k: dict[str, Any] | None = None, esik: int = 1) -> str | None:
    """Metinde yasak konu geçiyorsa konunun adı, yoksa None. esik: aynı konudan en az kaç eşleşme."""
    kucuk = metin.replace("İ", "i").lower()
    for ad, desen in YASAK_KONU.items():
        if len(re.findall(desen, kucuk)) >= esik:
            return ad
    if k and k.get("id", "").startswith("finans") and len(re.findall(YASAK_FINANS, kucuk)) >= esik:
        return "hisse/coin tavsiyesi"
    return None


DURAK = {
    "the", "and", "for", "with", "this", "that", "from", "what", "why", "how", "new", "now", "your", "you", "are",
    "was", "will", "its", "into", "about", "after", "over", "more", "just", "than", "they", "their", "has", "have",
    "gets", "could", "would", "says", "said", "here", "there", "game", "games", "news", "update", "explained",
    "için", "ile", "bir", "bu", "ve", "veya", "daha", "çok", "gibi", "nasıl", "neden", "olan", "olarak", "yeni",
}


def kelimeler(metin: str) -> set[str]:
    metin = metin.replace("İ", "i").replace("I", "ı").lower() if re.search(r"[ğışçöüİ]", metin) else metin.lower()
    return {w for w in re.findall(r"[^\W_]+", metin) if len(w) > 2 and w not in DURAK}


def makaleler(k: dict[str, Any], adet: int = 60) -> list[dict[str, str]]:
    """Kanalın RSS akışlarından son haberler: [{baslik, link, ozet, kaynak}]."""
    import feedparser

    ayar = dict(RSS_VARSAYILAN.get(k.get("id", ""), {"akislar": [], "filtre": []}))
    ozel = (k.get("trend") or {}).get("rss")
    if ozel:
        ayar = {"akislar": ozel.get("akislar", ayar["akislar"]), "filtre": ozel.get("filtre", ayar["filtre"])}
    sinir = time.time() - EN_ESKI_SAAT * 3600
    sonuc, gorulen = [], set()
    for adres in ayar["akislar"]:
        try:
            akis = feedparser.parse(adres, agent=UA)
        except Exception as e:
            log.warning("RSS okunamadı %s: %s", adres, e)
            continue
        for g in akis.entries[:40]:
            link, baslik = g.get("link", ""), re.sub(r"\s+", " ", g.get("title", "")).strip()
            zaman = g.get("published_parsed") or g.get("updated_parsed")
            if not link or not baslik or link in gorulen or (zaman and time.mktime(zaman) < sinir):
                continue
            ozet = re.sub(r"<[^>]+>", " ", g.get("summary", ""))
            ozet = re.sub(r"\s+", " ", ozet).strip()[:300]
            if ayar["filtre"] and not any(f in (baslik + " " + ozet).lower() for f in ayar["filtre"]):
                continue
            yasak = yasak_konu(baslik + " " + ozet, k)
            if yasak:
                log.info("Konu filtresi (%s): %s", yasak, baslik)
                continue
            gorulen.add(link)
            yas = round((time.time() - time.mktime(zaman)) / 3600) if zaman else EN_ESKI_SAAT - 1
            sonuc.append({"kaynak": re.sub(r"^https?://(www\.)?", "", adres).split("/")[0],
                          "baslik": baslik, "link": link, "ozet": ozet, "yas_saat": yas})
    sonuc.sort(key=lambda m: m["yas_saat"])  # en taze haber önce
    log.info("%s: %d güncel makale bulundu (son %d saat)", k.get("id"), len(sonuc), EN_ESKI_SAAT)
    return sonuc[:adet]


def metin_yolu(link: str) -> Path:
    return KLASOR / (hashlib.sha1(link.encode("utf-8")).hexdigest()[:16] + ".txt")


def metin_al(link: str) -> str:
    """Makalenin ana metni (önbellekli). Alınamazsa boş metin."""
    yol = metin_yolu(link)
    if yol.exists():
        return yol.read_text(encoding="utf-8")
    try:
        import trafilatura

        html = trafilatura.fetch_url(link)
        metin = trafilatura.extract(html, include_comments=False, include_tables=False) if html else None
    except Exception as e:
        log.warning("Makale metni alınamadı %s: %s", link, e)
        metin = None
    if not metin or len(metin) < EN_AZ_METIN:
        return ""
    KLASOR.mkdir(parents=True, exist_ok=True)
    yol.write_text(f"{link}\n\n{metin}", encoding="utf-8")
    return yol.read_text(encoding="utf-8")


def uyusuyor(konu: str, makale_basligi: str, metin: str, oran: float = 0.5) -> bool:
    """Konunun anlamlı kelimelerinin en az yarısı makale başlığı + metninde geçiyor mu."""
    konu_k = kelimeler(konu)
    if not konu_k:
        return False
    havuz = kelimeler(makale_basligi + " " + metin)
    ortak = {w for w in konu_k if w in havuz or any(h.startswith(w[:5]) for h in havuz if len(w) >= 5)}
    return len(ortak) >= max(1, round(len(konu_k) * oran))


def fikre_bagla(fikir: dict[str, Any], makale: dict[str, str]) -> dict[str, Any] | None:
    """Fikri makaleye bağlar (metin, link). Metin yoksa ya da konu uyuşmuyorsa None."""
    metin = metin_al(makale["link"])
    if not metin:
        log.info("Elendi (makale metni yok): %s", makale["link"])
        return None
    yasak = yasak_konu(metin, esik=3)  # başlık temiz ama metin yasak konuya dayanıyorsa
    if yasak:
        log.info("Elendi (konu filtresi: %s): %s", yasak, makale["baslik"])
        return None
    if not uyusuyor(str(fikir.get("konu", "")), makale["baslik"], metin):
        log.info("Elendi (konu makaleyle uyuşmuyor): %s <> %s", fikir.get("konu"), makale["baslik"])
        return None
    return {**fikir, "kaynaklar": [makale["link"]], "kaynak_baslik": makale["baslik"],
            "kaynak_metin": str(metin_yolu(makale["link"]))}


def metin_oku(fikir: dict[str, Any]) -> str:
    yol = fikir.get("kaynak_metin")
    return Path(yol).read_text(encoding="utf-8") if yol and Path(yol).exists() else ""
