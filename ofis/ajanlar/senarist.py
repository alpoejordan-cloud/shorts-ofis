"""Senarist: seçilen fikirden seslendirme metni, başlık, açıklama ve etiket yazar.
Her videoda farklı bir format seçerek kalıp içerik riskini azaltır."""
from __future__ import annotations

import random
from collections import Counter
from typing import Any

from ..cekirdek import Is, isler, gunluk_al
from ..yapay_zeka import sor_json

log = gunluk_al("senarist")

DIL_ADI = {"tr": "Türkçe", "en": "English"}


def format_sec(k: dict[str, Any], mod: str) -> str:
    """Son videolarda en az kullanılan formatı seçer."""
    formatlar = k.get("formatlar") or ["kısa bilgi + yorum"]
    if mod == "izinli_klip":
        formatlar = k.get("klip_formatlari") or ["klibin bağlamı + yorum + ders"]
    son = [i.veri.get("format") for i in isler(kanal_id=k["id"])[-30:]]
    sayac = Counter(son)
    en_az = min(sayac.get(f, 0) for f in formatlar)
    return random.choice([f for f in formatlar if sayac.get(f, 0) == en_az])


def senaryo_birlestir(s: dict[str, Any]) -> None:
    """Küçük modeller tek paragrafta kısa yazıyor; cümle listesi isteyip birleştiriyoruz."""
    cumleler = s.get("senaryo_cumleleri")
    if isinstance(cumleler, list) and cumleler:
        s["senaryo"] = " ".join(str(c).strip() for c in cumleler if str(c).strip())
    s["senaryo"] = str(s.get("senaryo", "")).strip()


KANCA_KALIPLARI = [
    "a direct question the viewer can't ignore",
    "a shocking number or fact (only if it is in the sources)",
    "\"you didn't know this\" / hidden detail",
    "contrast: what everyone thinks vs what is actually true",
    "a bold warning or mistake the viewer is making",
]


def kanca_duzelt(s: dict[str, Any]) -> str:
    """Ekrandaki kanca metni: en fazla 6 kelime. Yoksa başlıktan türetilir."""
    kanca = str(s.get("kanca_metni") or "").replace("#shorts", "").strip()
    if not kanca:
        kanca = str(s.get("baslik", "")).replace("#shorts", "").strip()
    sozler = kanca.split()
    return " ".join(sozler[:6])


def dogrula(s: dict[str, Any], k: dict[str, Any], tolerans: float = 0.85) -> list[str]:
    sorunlar = []
    kelime = len(str(s.get("senaryo", "")).split())
    alt, ust = k.get("kelime_araligi", [60, 120])
    if not (int(alt * tolerans) <= kelime <= int(ust * 1.15)):
        sorunlar.append(f"senaryo {kelime} kelime, {alt}-{ust} olmalı")
    if not s.get("baslik") or len(s["baslik"]) > 95:
        sorunlar.append("başlık boş ya da 95 karakterden uzun")
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


def yaz(is_: Is, k: dict[str, Any]) -> None:
    fikir = konuyu_cevir(is_.veri, k)
    mod = fikir.get("mod", "normal")
    fmt = format_sec(k, mod)
    kalip = random.choice(KANCA_KALIPLARI)
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
    dil_adi = DIL_ADI.get(k["dil"], k["dil"])
    kullanici = f"""OUTPUT LANGUAGE: {dil_adi}. The topic below may be written in another language; translate it.
Every JSON text value (title, hook, narration, description, tags) MUST be in {dil_adi}.
Channel niche: {k['nis']}
Topic: {fikir.get('konu')}
Angle: {fikir.get('aci', '')}
Sources: {', '.join(fikir.get('kaynaklar', [])) or 'none'}
Format for this video: {fmt}
Hook style for this video: {kalip}
Narration length: {k.get('kelime_araligi', [60, 120])[0]}-{k.get('kelime_araligi', [60, 120])[1]} words (about 25-45 seconds).
Extra notes: {k.get('senarist_notu', '')}{klip_notu}

JSON fields:
- "baslik": title under 70 characters, include #shorts at the end
- "kanca_metni": big on-screen hook text for the first 3 seconds, 3 to 6 words, punchy, in the hook style above, no hashtags, no emojis
- "senaryo_cumleleri": a list of 7 to 9 narration sentences, EACH sentence 10 to 16 words long. Sentence 1 is the spoken hook (same idea as kanca_metni, hook style above, no greeting, no "in this video"). Every next sentence must add new information or tension so viewers keep watching. The last one asks the viewer a question. Narration only, no stage directions, no emojis
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
    kaynak_satiri = "\n".join(fikir.get("kaynaklar", []))
    aciklama = s["aciklama"].strip()
    if kaynak_satiri and kaynak_satiri not in aciklama:
        aciklama += "\n\n" + ("Kaynaklar" if k["dil"] == "tr" else "Sources") + ":\n" + kaynak_satiri
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
        "gorsel_kelimeler": [str(g) for g in s.get("gorsel_kelimeler", [])][:8],
        "kanca_metni": kanca_duzelt(s),
        "yapay_icerik": bool(s.get("yapay_icerik", False)),
    })
    log.info("%s: senaryo hazır: %s", is_.id, is_.veri["baslik"])
