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


def dogrula(s: dict[str, Any], k: dict[str, Any]) -> list[str]:
    sorunlar = []
    kelime = len(str(s.get("senaryo", "")).split())
    alt, ust = k.get("kelime_araligi", [60, 120])
    if not (alt <= kelime <= ust):
        sorunlar.append(f"senaryo {kelime} kelime, {alt}-{ust} olmalı")
    if not s.get("baslik") or len(s["baslik"]) > 95:
        sorunlar.append("başlık boş ya da 95 karakterden uzun")
    if not s.get("gorsel_kelimeler"):
        sorunlar.append("gorsel_kelimeler boş")
    return sorunlar


def yaz(is_: Is, k: dict[str, Any]) -> None:
    fikir = is_.veri
    mod = fikir.get("mod", "normal")
    fmt = format_sec(k, mod)
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
    kullanici = f"""Channel niche: {k['nis']}
Topic: {fikir.get('konu')}
Angle: {fikir.get('aci', '')}
Sources: {', '.join(fikir.get('kaynaklar', [])) or 'none'}
Format for this video: {fmt}
Narration length: {k.get('kelime_araligi', [60, 120])[0]}-{k.get('kelime_araligi', [60, 120])[1]} words (about 25-45 seconds).
Extra notes: {k.get('senarist_notu', '')}{klip_notu}

JSON fields:
- "baslik": title under 70 characters, include #shorts at the end
- "senaryo": the narration text only, no stage directions, no emojis
- "aciklama": 2-3 sentence description; list the sources at the end
- "etiketler": 5-10 tags
- "gorsel_kelimeler": 4-6 short ENGLISH search terms for stock footage matching the narration in order
- "yapay_icerik": true if the video shows realistic AI-generated people/events, else false"""
    for deneme in range(3):
        s = sor_json(sistem, kullanici, sicaklik=0.85)
        if not isinstance(s, dict):
            continue
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
        "gorsel_kelimeler": [str(g) for g in s.get("gorsel_kelimeler", [])][:6],
        "yapay_icerik": bool(s.get("yapay_icerik", False)),
    })
    log.info("%s: senaryo hazır: %s", is_.id, is_.veri["baslik"])
