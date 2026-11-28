"""Senarist: seçilen fikirden seslendirme metni, başlık, açıklama ve etiket yazar.
Her videoda farklı bir format seçerek kalıp içerik riskini azaltır."""
from __future__ import annotations

import json
import random
import re as _re
from collections import Counter
from typing import Any

from ..cekirdek import Is, isler, gunluk_al
from .. import kaynak
from ..yapay_zeka import sor_json

log = gunluk_al("senarist")

DIL_ADI = {"tr": "Türkçe", "en": "English"}


def en_iyi_format(kanal_id: str, formatlar: list[str], en_az_video: int = 3) -> str | None:
    """Analistin icgoruler dosyasına göre en yüksek ortalama izlenmeli format (yeterli veri yoksa None)."""
    from ..cekirdek import VERI

    yol = VERI / "icgoruler" / f"{kanal_id}.json"
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if veri.get("video", 0) < en_az_video:
        return None
    ort = {f: n for f, n in (veri.get("format_ortalamalari") or {}).items() if f in formatlar}
    return max(ort, key=ort.get) if ort else None


def format_sec(k: dict[str, Any], mod: str) -> str:
    """Son videolarda en az kullanılan formatı seçer."""
    formatlar = k.get("formatlar") or ["kısa bilgi + yorum"]
    if mod == "izinli_klip":
        formatlar = k.get("klip_formatlari") or ["klibin bağlamı + yorum + ders"]
    # analistin haftalık notu: yeterli veri varsa %60 olasılıkla en çok izlenen format seçilir
    en_iyi = en_iyi_format(k["id"], formatlar)
    if en_iyi and random.random() < 0.6:
        return en_iyi
    son = [i.veri.get("format") for i in isler(kanal_id=k["id"])[-30:]]
    sayac = Counter(son)
    en_az = min(sayac.get(f, 0) for f in formatlar)
    return random.choice([f for f in formatlar if sayac.get(f, 0) == en_az])


def _noktala(cumle: str) -> str:
    """Noktalaması olmayan cümlenin sonuna nokta koyar (TTS duraksaması ve altyazı bölünmesi için)."""
    return cumle if cumle[-1:] in ".!?…\"'”’)" else cumle + "."


def senaryo_birlestir(s: dict[str, Any]) -> None:
    """Küçük modeller tek paragrafta kısa yazıyor; cümle listesi isteyip birleştiriyoruz."""
    cumleler = s.get("senaryo_cumleleri")
    if isinstance(cumleler, list) and cumleler:
        s["senaryo"] = " ".join(_noktala(str(c).strip()) for c in cumleler if str(c).strip())
    s["senaryo"] = str(s.get("senaryo", "")).strip()


KANCA_KALIPLARI = [
    "a direct question the viewer can't ignore",
    "a shocking number or fact (only if it is in the sources)",
    "\"you didn't know this\" / hidden detail",
    "contrast: what everyone thinks vs what is actually true",
    "a bold warning or mistake the viewer is making",
]


YARIM_SON = {"but", "and", "or", "the", "a", "an", "of", "to", "is", "really", "that", "this", "from", "with", "for",
             "in", "on", "at", "by", "about", "into", "than", "as", "has", "have", "had", "your", "my", "our",
             "their", "his", "her", "its", "next", "new", "big", "will", "can", "could", "would", "just", "are",
             "was", "were", "be", "not", "very", "so", "what", "who", "how", "why", "when", "where", "which",
             "ama", "ve", "ile", "için", "bu", "çünkü", "bir", "çok", "en", "daha", "senin", "bizim"}
KANCA_EN_COK = 7  # ekrandaki kanca en fazla 7 kelime (2026-11-28: 6'ya kesmek "Is AI toy safety a big" gibi yarım kanca üretti)


def _kanca_temizle(metin: str) -> str:
    return " ".join(str(metin or "").replace("#shorts", "").split()).strip().rstrip(",;:—-")


def kanca_duzelt(s: dict[str, Any]) -> str:
    """Ekrandaki kanca metni: en fazla 7 kelimelik TAM bir ifade. Uzunsa ilk cümle/yan cümle sınırından kesilir;
    sınır yoksa (yarım kalacaksa) başlık kullanılır. Kanca yoksa başlıktan türetilir."""
    kanca = _kanca_temizle(s.get("kanca_metni"))
    baslik = _kanca_temizle(s.get("baslik"))
    if not kanca:
        kanca = baslik
    sozler = kanca.split()
    if len(sozler) <= KANCA_EN_COK:
        return kanca
    for i in range(KANCA_EN_COK - 1, 1, -1):  # "Your chats are for sale. Here's..." -> "Your chats are for sale."
        if sozler[i].endswith((".", "!", "?", ",", ":", ";", "—")):
            return " ".join(sozler[: i + 1]).rstrip(",;:—-")
    if baslik and 2 <= len(baslik.split()) <= KANCA_EN_COK and baslik != kanca:
        return baslik
    sozler = sozler[:KANCA_EN_COK]
    while len(sozler) > 2 and (sozler[-1].lower().strip(".,!?…") in YARIM_SON or sozler[-2].endswith(",")):
        sozler.pop()
    return " ".join(sozler).rstrip(",;:—-")


ZAYIF_KANCALAR = ("you didn't know this", "you didn’t know this", "did you know", "watch this", "you won't believe",
                  "you won’t believe", "this is crazy", "wait for it", "check this out", "here's why", "here’s why",
                  "you missed this", "are you ready", "is this the end", "what if i told you", "you think you're safe",
                  "you think you’re safe", "don't miss this", "don’t miss this", "this changes everything",
                  "bunu biliyor muydun", "bunu bilmiyordun", "buna hazır mısın")


def zayif_kanca_mi(kanca: str) -> bool:
    """Genel, her videoya uyan kanca (somut detay yok) zayıftır."""
    k = kanca.lower().strip(" .!?")
    return any(k.startswith(z) or k == z for z in ZAYIF_KANCALAR)


def kanca_yarim_mi(kanca: str) -> bool:
    sozler = _kanca_temizle(kanca).split()
    return not sozler or len(sozler) > KANCA_EN_COK or sozler[-1].lower().strip(".,!?…") in YARIM_SON


def dogrula(s: dict[str, Any], k: dict[str, Any], tolerans: float = 0.85) -> list[str]:
    sorunlar = []
    kelime = len(str(s.get("senaryo", "")).split())
    alt, ust = k.get("kelime_araligi", [60, 120])
    if not (int(alt * tolerans) <= kelime <= int(ust * 1.15)):
        sorunlar.append(f"senaryo {kelime} kelime, {alt}-{ust} olmalı")
    if not s.get("baslik") or len(s["baslik"]) > 95:
        sorunlar.append("başlık boş ya da 95 karakterden uzun")
    if s.get("kanca_metni") and zayif_kanca_mi(str(s["kanca_metni"])):
        sorunlar.append("kanca_metni is generic; write a specific curiosity gap with a concrete detail from the "
                        "topic (a number, a name, a surprising outcome), 3-6 words")
    if s.get("kanca_metni") and (kanca_yarim_mi(kanca_duzelt(s))
                                 or len(_kanca_temizle(s["kanca_metni"]).split()) > KANCA_EN_COK):
        sorunlar.append("kanca_metni must be a COMPLETE punchy phrase of 3-7 words, not cut off mid-sentence")
    if not s.get("gorsel_kelimeler"):
        sorunlar.append("gorsel_kelimeler boş")
    if k.get("dil") == "en" and sum(c in "ğüşıöçĞÜŞİÖÇ" for c in str(s.get("baslik", "")) + str(s.get("senaryo", ""))) > 2:
        sorunlar.append("title and narration must be in English, not Turkish")
    return sorunlar


def genislet(metin: str, k: dict[str, Any], fikir: dict[str, Any]) -> str:
    """Kısa kalan senaryoyu, yeni bilgi uydurmadan, hedef uzunluğa getirir."""
    alt, ust = k.get("kelime_araligi", [60, 120])
    hedef = (alt + ust) // 2
    sistem = (f"You expand YouTube Shorts narrations. Write in {DIL_ADI.get(k['dil'], k['dil'])}. "
              "Do not invent facts or numbers. Respond with JSON only.")
    kullanici = (f"Topic: {fikir.get('konu')}\nAngle: {fikir.get('aci', '')}\n\n"
                 f"Narration ({len(metin.split())} words):\n{metin}\n\n"
                 f"Rewrite it to about {hedef} words (between {alt} and {ust}). Add context, why it matters to the "
                 "viewer, and one honest opinion. Keep the hook first and end with a question to the viewer.\n"
                 'JSON: {"senaryo_cumleleri": ["sentence", "..."]}')
    for _ in range(2):
        try:
            cevap = sor_json(sistem, kullanici, sicaklik=0.7)
        except Exception as e:  # genişletme olmazsa eldeki metinle devam
            log.warning("Genişletme başarısız: %s", e)
            return metin
        if isinstance(cevap, dict):
            senaryo_birlestir(cevap)
            if len(cevap["senaryo"].split()) > len(metin.split()):
                metin = cevap["senaryo"]
                if len(metin.split()) >= alt:
                    break
    return metin


TR_HARF = set("ğüşıöçĞÜŞİÖÇ")
# Türkçe harf içermeyen ama Türkçe olan sık görsel kelimeleri
TR_SIK = {"para", "tapu", "kitap", "ev", "araba", "banka", "kredi", "faiz", "altin", "borsa", "maas", "vergi",
          "kira", "fatura", "dijital", "ekonomi", "enflasyon", "yatirim", "yatkim", "butce", "sinav", "portfoy"}


def konuyu_cevir(fikir: dict[str, Any], k: dict[str, Any]) -> dict[str, Any]:
    """İngilizce kanalın konusu Türkçe geldiyse, küçük model Türkçe yazmasın diye önce konuyu çevirir."""
    if k.get("dil") != "en" or not (TR_HARF & set(str(fikir.get("konu", "")) + str(fikir.get("aci", "")))):
        return fikir
    try:
        cevap = sor_json("You translate Turkish to natural English. Respond with JSON only.",
                         f'Translate to English.\nkonu: {fikir.get("konu", "")}\naci: {fikir.get("aci", "")}\n'
                         'JSON: {"konu": "...", "aci": "..."}', sicaklik=0.2)
    except Exception as e:
        log.warning("Konu çevrilemedi: %s", e)
        return fikir
    if isinstance(cevap, dict) and cevap.get("konu") and not (TR_HARF & set(str(cevap["konu"]))):
        return {**fikir, "konu": str(cevap["konu"]), "aci": str(cevap.get("aci") or fikir.get("aci", ""))}
    return fikir


def gorsel_kelimeleri_ingilizce(kelimeler: list[str], dil: str = "en") -> list[str]:
    """Fotoğraf aramaları İngilizce yapılır; Türkçe kanalda veya Türkçe yazılmışsa çevrilir."""
    turkce = any(TR_HARF & set(w) or not w.isascii() or w.lower() in TR_SIK for w in kelimeler)
    if not kelimeler or (dil == "en" and not turkce):
        return kelimeler
    try:
        cevap = sor_json("You translate image search terms to English. Respond with JSON only.",
                         "Translate each term to a short, concrete English photo search term (same order).\n"
                         f"terms: {json.dumps(kelimeler, ensure_ascii=False)}\n"
                         'JSON: {"terms": ["...", "..."]}', sicaklik=0.2)
    except Exception as e:
        log.warning("Görsel kelimeleri çevrilemedi: %s", e)
        return kelimeler
    yeni = cevap.get("terms") if isinstance(cevap, dict) else None
    if isinstance(yeni, list) and yeni and all(isinstance(w, str) and w.strip() for w in yeni):
        return [w.strip().replace("_", " ") for w in yeni][:8]
    return kelimeler



def aciklama_temizle(metin: str) -> str:
    """Modelin açıklamaya koyduğu linkleri ve 'Source(s): ...' / 'Kaynak: ...' ifadelerini çıkarır."""
    metin = _re.sub(r"https?://\S+", "", metin)
    metin = _re.sub(r"(?im)^\s*(sources?|kaynaklar?)\s*:.*$", "", metin)
    metin = _re.sub(r"(?i)\s*(sources?|kaynaklar?)\s*:\s*[^.\n]*\.?", "", metin)
    return _re.sub(r"\n{3,}", "\n\n", metin).strip()


def klip_basligi(model_basligi: str, yayinci: str, klip_adi: str) -> str:
    """Model başlığı zayıfsa (yayıncı adı dışında 3 kelimeden az) "Yayıncı: klip adı" kalıbını kullanır."""
    yayinci = yayinci.split("(")[0].strip()
    anlamli = [w for w in _re.findall(r"[A-Za-z0-9']+", model_basligi)
               if w.lower() not in {"shorts", *yayinci.lower().split()}]
    if len(anlamli) >= 3:
        return model_basligi.strip()
    return f"{yayinci}: {klip_adi.strip()}" if klip_adi.strip() else model_basligi.strip()

def klip_metni_yaz(is_: Is, k: dict[str, Any]) -> None:
    """Yayıncı sesi korunan kampanya klipleri: seslendirme yazılmaz; sadece başlık, kanca, açıklama, etiket."""
    fikir = is_.veri
    dil_adi = DIL_ADI.get(k["dil"], k["dil"])
    sistem = (f"You write titles for a YouTube Shorts channel that posts permitted streamer clips. Write in {dil_adi}. "
              "Never invent what happens in the clip beyond the given description. No clickbait lies. JSON only.")
    kullanici = f"""Streamer: {fikir.get('yayinci')}
Clip description: {fikir.get('klip_aciklama', '')}
You do NOT know anything about the clip beyond its title/description. Use only those facts.
JSON fields:
- "baslik": title under 70 characters that names the streamer, ends with #shorts
- "kanca_metni": on-screen hook for the first 3 seconds, 3 to 6 words, built ONLY from words in the clip title, no numbers that are not in the title, no hashtags, no emojis
- "aciklama": 1-2 sentence description of the moment
- "etiketler": 5-10 tags"""
    s: Any = None
    for _ in range(3):
        s = sor_json(sistem, kullanici, sicaklik=0.8)
        if isinstance(s, dict) and s.get("baslik") and len(str(s["baslik"])) <= 95:
            break
    else:
        s = {"baslik": f"{fikir.get('yayinci', '')}: {fikir.get('klip_aciklama', '')}"[:60] + " #shorts"}
    # kanca klipte olmayan bir şey uydurmasın: başlıkla ortak kelimesi yoksa klip başlığı kullanılır
    import re as _re

    kaynak = str(fikir.get("klip_aciklama", "")).lower()
    sozler = [w for w in _re.findall(r"[a-z0-9]+", str(s.get("kanca_metni", "")).lower()) if len(w) > 2]
    if not sozler or not all(w in kaynak for w in sozler if w.isdigit()) or not any(w in kaynak for w in sozler):
        baslik_kismi = _re.search(r"'([^']+)'", str(fikir.get("klip_aciklama", "")))
        s["kanca_metni"] = (baslik_kismi.group(1) if baslik_kismi else str(fikir.get("yayinci", ""))).strip()
    etiketler = list(fikir.get("zorunlu_etiketler") or [])
    # açıklama modelden alınmaz (klipte olmayanı uydurabilir): klip başlığından kalıp cümle
    baslik_kismi = _re.search(r"'([^']+)'", str(fikir.get("klip_aciklama", "")))
    klip_adi = baslik_kismi.group(1) if baslik_kismi else str(fikir.get("klip_aciklama", ""))
    ozet = f"{str(fikir.get('yayinci', '')).split('(')[0].strip()}: {klip_adi} (GTA 6 stream clip)."
    aciklama = "\n\n".join(x for x in [fikir.get("kredi", ""), ozet, " ".join(etiketler)] if x)
    s["etiketler"] = [w for w in s.get("etiketler", []) if str(w).lower() in kaynak or " " not in str(w)][:8]
    is_.veri.update({
        "format": "yayıncı klibi (orijinal ses)",
        "baslik": klip_basligi(str(s.get("baslik", "")), str(fikir.get("yayinci", "")), klip_adi),
        "senaryo": "",
        "aciklama": aciklama,
        "etiketler": [str(e) for e in s.get("etiketler", [])][:15] + [e.lstrip("#") for e in etiketler],
        "gorsel_kelimeler": [],
        "kanca_metni": kanca_duzelt(s),
        "yapay_icerik": False,
    })
    log.info("%s: klip metni hazır: %s", is_.id, is_.veri["baslik"])



def sayilar_kaynakta(metin: str, kaynak_metni: str) -> bool:
    """Metindeki her sayı kaynak makalede geçiyor mu (başlık/kanca/açıklama için)."""
    import re

    def sade(x: str) -> str:
        return re.sub(r"(?<=\d)[.,](?=\d)", "", x)

    kaynak = sade(kaynak_metni)
    return all(sade(n.rstrip(".,")) in kaynak for n in re.findall(r"\d[\d.,]*", metin))


def gemini_ile_gelistir(s: dict[str, Any], k: dict[str, Any], kaynak_metni: str, is_id: str = "") -> dict[str, Any]:
    """Gemini varsa: senaryoyu akıcılaştırır, 5 kanca/başlık seçeneğinden en iyisini alır, SEO önerir.
    Her öneri kaynak doğrulamasından geçmezse Ollama'nın hâli korunur. Gemini yoksa s aynen döner."""
    from .. import gemini
    from ..kalite import kaynakla_karsilastir

    if not kaynak_metni or not gemini.hazir_mi():
        return s
    yeni = gemini.senaryoyu_akicilastir(s, k, kaynak_metni)
    if yeni:
        aday = {**s, "senaryo_cumleleri": yeni}
        senaryo_birlestir(aday)
        sorun = dogrula(aday, k) or kaynakla_karsilastir(aday["senaryo"], kaynak_metni)
        if not sorun:
            s = aday
            log.info("%s: senaryo Gemini ile akıcılaştırıldı", is_id)
        else:
            log.info("%s: Gemini senaryosu kullanılmadı (%s)", is_id, "; ".join(sorun))
    kb = gemini.kanca_ve_baslik(s, k, kaynak_metni)
    if (kb and not kanca_yarim_mi(kb["kanca_metni"]) and len(kb["baslik"]) <= 95
            and sayilar_kaynakta(kb["baslik"] + " " + kb["kanca_metni"], kaynak_metni)):
        s = {**s, **kb}
        log.info("%s: Gemini kanca/başlık: %s | %s", is_id, kb["kanca_metni"], kb["baslik"])
    seo = gemini.seo_onerisi({"baslik": s.get("baslik"), "senaryo": s.get("senaryo")}, k)
    if seo:
        if seo["etiketler"]:
            s = {**s, "etiketler": seo["etiketler"] + [e for e in s.get("etiketler", []) if e not in seo["etiketler"]]}
        if seo["aciklama"] and "http" not in seo["aciklama"] and sayilar_kaynakta(seo["aciklama"], kaynak_metni):
            s = {**s, "aciklama": seo["aciklama"]}
    return s


def gemini_ile_iyilestir(s: dict[str, Any], k: dict[str, Any], fikir: dict[str, Any], sistem: str,
                         kullanici: str, is_id: str = "", tur: int = 2) -> tuple[dict[str, Any], dict | None]:
    """Ollama yazdı; Gemini eleştirir, Ollama düzeltir (en fazla `tur` kez). Gemini yoksa s aynen döner."""
    from .. import gemini

    denetim = None
    for n in range(tur):
        denetim = gemini.senaryo_denetle(s, k, fikir)
        if denetim is None or (denetim["onay"] and not denetim["uydurma_suphesi"]):
            break
        geri = denetim["sorunlar"] + [f"Remove or mark as rumor: {x}" for x in denetim["uydurma_suphesi"]]
        log.info("%s: Gemini eleştirisi (tur %d, puan %s): %s", is_id, n + 1, denetim.get("puan"), "; ".join(geri))
        try:
            geri_metni = "\n- ".join(geri)
            yeni = sor_json(sistem, kullanici + "\n\nYour previous JSON:\n" + json.dumps(s, ensure_ascii=False)
                            + "\n\nEditor feedback, fix ALL of it and return the full JSON again:\n- " + geri_metni,
                            sicaklik=0.6)
        except Exception as e:
            log.info("%s: düzeltme alınamadı: %s", is_id, e)
            break
        if not isinstance(yeni, dict):
            break
        senaryo_birlestir(yeni)
        if dogrula(yeni, k):  # düzeltme kuralları bozduysa eskisi kalır
            break
        s = yeni
    else:
        denetim = gemini.senaryo_denetle(s, k, fikir) or denetim  # son hâlin notu (kalite kontrolü okur)
    return s, denetim

def yaz(is_: Is, k: dict[str, Any]) -> None:
    if is_.veri.get("mod") == "izinli_klip" and is_.veri.get("yayinci_sesi"):
        return klip_metni_yaz(is_, k)
    fikir = konuyu_cevir(is_.veri, k)
    mod = fikir.get("mod", "normal")
    fmt = fikir.get("format") or format_sec(k, mod)  # resmi konu kendi formatını getirir
    kalip = random.choice(KANCA_KALIPLARI)
    is_.veri["kanca_kalibi"] = kalip  # analist hangi kanca türünün tuttuğunu öğrensin
    klip_notu = ""
    if mod == "izinli_klip":
        klip_notu = (
            f"\nBu video, izin alınmış bir yayıncı klibi üzerine yorumdur. Yayıncı: {fikir.get('yayinci')}. "
            f"Klip açıklaması: {fikir.get('klip_aciklama', 'yok')}. Seslendirme klibi anlatmaz, "
            "klibe kendi yorumunu, bağlamını veya dersini ekler."
        )
    sistem = (
        f"You are the scriptwriter of a YouTube Shorts channel. Write everything in {DIL_ADI.get(k['dil'], k['dil'])}. "
        "Hook the viewer in the first sentence, give real value, add one original opinion or angle, end with a short "
        "question or call to comment. Never invent facts, numbers or quotes; if unsure, say it is a claim or rumor. "
        "No clickbait lies. Respond with JSON only."
    )
    kaynak_metni = kaynak.metin_oku(fikir)[:6000]
    if kaynak_metni:
        sistem += (
            " STRICT SOURCE RULE: use ONLY facts found in the SOURCE ARTICLE given by the user. Do not add any number, "
            "date, price, percentage, name, company, product or claim that is not written in the article. Your own "
            "opinion is allowed only as one clearly marked opinion sentence (e.g. 'I think...'). If the article "
            "describes a rumor, leak, report or unconfirmed claim, the narration must say so explicitly "
            "('rumor', 'reportedly', 'unconfirmed')."
        )
    dil_adi = DIL_ADI.get(k["dil"], k["dil"])
    kullanici = f"""OUTPUT LANGUAGE: {dil_adi}. The topic below may be written in another language; translate it.
Every JSON text value (title, hook, narration, description, tags) MUST be in {dil_adi}.
Channel niche: {k['nis']}
Topic: {fikir.get('konu')}
Angle: {fikir.get('aci', '')}
Sources: {', '.join(fikir.get('kaynaklar', [])) or 'none'}
Format for this video: {fmt}
Hook style for this video: {kalip}
Narration length: {k.get('kelime_araligi', [60, 120])[0]}-{k.get('kelime_araligi', [60, 120])[1]} words (25-40 seconds; shorter keeps viewers to the end).
Extra notes: {k.get('senarist_notu', '')}{klip_notu}
{f'''
SOURCE ARTICLE (the ONLY allowed facts; do not add anything that is not here):
"""
{kaynak_metni}
"""
''' if kaynak_metni else ''}
JSON fields:
- "baslik": title under 60 characters that creates curiosity (a question, a surprising fact from the article or a "why/how" angle) AND has the main keyword of the topic (product/game/company name) in the first 3 words; no clickbait lies; include #shorts at the end
- "kanca_metni": big on-screen hook text for the first 3 seconds, 3 to 6 words, punchy, in the hook style above, no hashtags, no emojis
- "senaryo_cumleleri": a list of 6 to 8 narration sentences, EACH sentence 9 to 14 words long. Sentence 1 is the spoken hook (same idea as kanca_metni, hook style above, no greeting, no "in this video"); it must create tension within the first second. Every next sentence must add new information or tension so viewers keep watching. LOOP: the last sentence must flow naturally back into sentence 1 when the video repeats (e.g. a short question or half-thought that sentence 1 answers), so viewers rewatch. Narration only, no stage directions, no labels like "Why this matters:", no emojis
- "aciklama": 2-3 sentence description; list the sources at the end
- "etiketler": 5-10 tags
- "gorsel_kelimeler": 6-8 short ENGLISH search terms for photos/footage, concrete and visual (objects, places, people doing things, brand products), in narration order
- "yapay_icerik": true if the video shows realistic AI-generated people/events, else false"""
    for deneme in range(3):
        s = sor_json(sistem, kullanici, sicaklik=0.85)
        if not isinstance(s, dict):
            continue
        senaryo_birlestir(s)
        if s["senaryo"] and len(s["senaryo"].split()) < k.get("kelime_araligi", [60, 120])[0]:
            s["senaryo"] = genislet(s["senaryo"], k, fikir)
        sorunlar = dogrula(s, k)
        if not sorunlar:
            break
        log.info("%s: senaryo düzeltiliyor (%s)", is_.id, "; ".join(sorunlar))
        kullanici += f"\n\nPrevious attempt had problems: {'; '.join(sorunlar)}. Fix them."
    else:
        raise ValueError(f"Senaryo 3 denemede kurallara uymadı: {sorunlar}")
    s = gemini_ile_gelistir(s, k, kaynak_metni, is_.id)
    s, denetim = gemini_ile_iyilestir(s, k, fikir, sistem, kullanici, is_.id)
    if denetim is not None:
        is_.veri["gemini_denetim"] = denetim
    kaynak_satiri = "\n".join(fikir.get("kaynaklar", []))
    aciklama = aciklama_temizle(str(s.get("aciklama", "")))  # modelin yazdığı link/kaynak satırları atılır
    if kaynak_satiri:  # yalnızca gerçekten kullanılan kaynak makale
        aciklama += "\n\n" + ("Kaynak" if k["dil"] == "tr" else "Source") + ":\n" + kaynak_satiri
    if k.get("aciklama_eki"):
        aciklama += "\n\n" + k["aciklama_eki"]
    if mod == "izinli_klip" and fikir.get("kredi"):
        aciklama = fikir["kredi"] + "\n\n" + aciklama
    is_.veri.update({
        "format": fmt,
        "baslik": s["baslik"].strip(),
        "senaryo": s["senaryo"].strip(),
        "aciklama": aciklama,
        "etiketler": [str(e) for e in s.get("etiketler", [])][:15],
        "gorsel_kelimeler": gorsel_kelimeleri_ingilizce(
            [str(g).replace("_", " ") for g in s.get("gorsel_kelimeler", [])][:8], k.get("dil", "en")),
        "kanca_metni": kanca_duzelt(s),
        "yapay_icerik": bool(s.get("yapay_icerik", False)),
    })
    log.info("%s: senaryo hazır: %s", is_.id, is_.veri["baslik"])
