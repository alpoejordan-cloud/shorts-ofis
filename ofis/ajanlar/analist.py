"""Analist: yüklenen videoların izlenmelerini toplar, haftalık rapor yazar ve
neyin tuttuğunu trend araştırmacısına not olarak bırakır."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import Any

from ..cekirdek import RAPORLAR, VERI, Is, gunluk_al, isler, kanallar

log = gunluk_al("analist")


def istatistik_topla() -> int:
    from .yukleyici import servis

    guncellenen = 0
    for k in kanallar():
        yuklenen = [i for i in isler("yuklendi", k["id"]) if i.veri.get("youtube_id")]
        if not yuklenen:
            continue
        try:
            yt = servis(k["id"])
        except RuntimeError as e:
            log.warning("%s: %s", k["id"], e)
            continue
        for bas in range(0, len(yuklenen), 50):
            parca = yuklenen[bas : bas + 50]
            cevap = yt.videos().list(part="statistics,status", id=",".join(i.veri["youtube_id"] for i in parca)).execute()
            bulunan = {v["id"]: v for v in cevap.get("items", [])}
            for i in parca:
                v = bulunan.get(i.veri["youtube_id"])
                if not v:
                    continue
                s = v.get("statistics", {})
                i.veri["istatistik"] = {
                    "izlenme": int(s.get("viewCount", 0)),
                    "begeni": int(s.get("likeCount", 0)),
                    "yorum": int(s.get("commentCount", 0)),
                    "gizlilik": v.get("status", {}).get("privacyStatus"),
                    "tarih": datetime.now().isoformat(timespec="minutes"),
                }
                i.kaydet()
                guncellenen += 1
    return guncellenen


def ozet(kanal_isleri: list[Is]) -> dict[str, Any]:
    olculen = [i for i in kanal_isleri if "istatistik" in i.veri]
    if not olculen:
        return {"video": 0}
    izl = lambda i: i.veri["istatistik"]["izlenme"]  # noqa: E731
    sirali = sorted(olculen, key=izl, reverse=True)
    formatlar: dict[str, list[int]] = defaultdict(list)
    kancalar: dict[str, list[int]] = defaultdict(list)
    kaynaklar: dict[str, list[int]] = defaultdict(list)
    gorseller: dict[str, list[int]] = defaultdict(list)
    for i in olculen:
        gorseller[i.veri.get("gorsel_modu", "fotograf")].append(izl(i))
        formatlar[i.veri.get("format", "?")].append(izl(i))
        if i.veri.get("kanca_kalibi"):
            kancalar[i.veri["kanca_kalibi"]].append(izl(i))
        for lnk in i.veri.get("kaynaklar", [])[:1]:
            kaynaklar[lnk.split("/")[2] if "//" in lnk else lnk].append(izl(i))
    sonuc = {
        "video": len(olculen),
        "toplam_izlenme": sum(map(izl, olculen)),
        "ortalama_izlenme": round(mean(map(izl, olculen))),
        "en_iyi": [{"baslik": i.veri["baslik"], "izlenme": izl(i), "konu": i.veri.get("konu"),
                    "format": i.veri.get("format"), "sure": i.veri.get("sure")} for i in sirali[:5]],
        "en_kotu": [{"baslik": i.veri["baslik"], "izlenme": izl(i), "konu": i.veri.get("konu")} for i in sirali[-3:]],
        "format_ortalamalari": {f: round(mean(v)) for f, v in formatlar.items()},
        "kanca_ortalamalari": {f: round(mean(v)) for f, v in kancalar.items()},
        "kaynak_ortalamalari": {f: round(mean(v)) for f, v in kaynaklar.items()},
        "gorsel_ortalamalari": {f: round(mean(v)) for f, v in gorseller.items()},
    }
    sonuc["oneriler"] = oneriler(sonuc)
    return sonuc


def oneriler(o: dict[str, Any], en_az: int = 3) -> list[str]:
    """Trend araştırmacısı ve senaristin okuyacağı kısa dersler (yeterli veri varsa)."""
    if o.get("video", 0) < en_az:
        return ["Henüz yeterli veri yok (en az 3 ölçülen video); çeşitli format ve konular dene."]
    notlar = []
    for ad, anahtar in (("format", "format_ortalamalari"), ("kanca türü", "kanca_ortalamalari"),
                        ("kaynak site", "kaynak_ortalamalari"), ("görsel türü", "gorsel_ortalamalari")):
        d = o.get(anahtar) or {}
        if len(d) >= 2:
            en_iyi, en_kotu = max(d, key=d.get), min(d, key=d.get)
            notlar.append(f"En iyi {ad}: '{en_iyi}' (ort. {d[en_iyi]:,} izlenme); en zayıf: '{en_kotu}' ({d[en_kotu]:,}).")
    if o.get("en_iyi"):
        konular = ", ".join(str(v.get("konu")) for v in o["en_iyi"][:3])
        notlar.append(f"En çok izlenen konular: {konular}. Benzer konuları öne al.")
    return notlar


def rapor_yaz() -> str:
    try:
        istatistik_topla()
    except Exception as e:
        log.warning("İstatistik toplanamadı: %s", e)
    satirlar = [f"# Haftalık rapor, {datetime.now():%d.%m.%Y}", ""]
    (VERI / "icgoruler").mkdir(exist_ok=True)
    for k in kanallar():
        o = ozet(isler(kanal_id=k["id"]))
        hepsi = isler(kanal_id=k["id"])
        sayim = defaultdict(int)
        for i in hepsi:
            sayim[i.durum] += 1
        satirlar += [f"## {k.get('ad') or k['id']}", "",
                     "Durumlar: " + ", ".join(f"{d}: {n}" for d, n in sorted(sayim.items())), ""]
        if o["video"]:
            satirlar += [f"Ölçülen video: {o['video']}, toplam izlenme: {o['toplam_izlenme']:,}, "
                         f"ortalama: {o['ortalama_izlenme']:,}", "", "En iyi videolar:"]
            satirlar += [f"- {v['baslik']}: {v['izlenme']:,}" for v in o["en_iyi"]]
            satirlar += ["", "Format ortalamaları:"]
            satirlar += [f"- {f}: {n:,}" for f, n in sorted(o["format_ortalamalari"].items(), key=lambda x: -x[1])]
        else:
            satirlar.append("Henüz ölçülen video yok.")
        satirlar.append("")
        (VERI / "icgoruler" / f"{k['id']}.json").write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding="utf-8")
    metin = "\n".join(satirlar)
    yol = RAPORLAR / f"{datetime.now():%Y-%m-%d}.md"
    yol.write_text(metin, encoding="utf-8")
    log.info("Rapor yazıldı: %s", yol)
    return metin
