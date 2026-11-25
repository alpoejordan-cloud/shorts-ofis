"""Çocuk hikayesi seslendirmesi: anlatıcı ve her karakter kendi sesiyle konuşur.

- İngilizce: Kokoro sesleri, Türkçe: Piper sesleri (mevcut seslendirme ajanı kullanılır)
- Karakter sesleri perde kaydırmayla (pitch) çizgi film tınısına getirilir, hız aynı kalır
- Satırlar arası kısa sessizlik, sahne geçişlerinde nefes payı; toplam süre 58 sn'yi geçmez
- Altyazı: metin senaryodan gelir (yanlış kelime çıkmaz), her konuşanın kelimesi kendi renginde parlar
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from ..ajanlar import seslendirme
from ..ajanlar.kurgu import ffmpeg_yolu
from ..cekirdek import Is, gunluk_al
from . import karakter, muzik

log = gunluk_al("cocuk_ses")
HZ = muzik.HZ
ILK_GIRIS = 0.35   # ilk sahne: kanca hemen başlasın
SAHNE_GIRIS = 0.75  # diğer sahneler: karakterler zıplayarak girerken
SATIR_ARASI = 0.32
SAHNE_SONU = 0.45
FINAL_SONU = 1.8   # "The End" ve parıltı
EN_UZUN = 58.0


def karakterler(k: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(c["id"]): c for c in k.get("karakterler", [])}


def konusan_sesi(kim: str, k: dict[str, Any]) -> tuple[str, float, float]:
    """(ses modeli, perde çarpanı, hız) — anlatıcı ya da karakter."""
    if kim in karakterler(k):
        c = karakterler(k)[kim]
        return str(c.get("ses") or k["ses"]), float(c.get("perde", 1.15)), float(c.get("hiz", k.get("ses_hizi", 1.0)))
    return str(k["ses"]), float(k.get("anlatici_perde", 1.0)), float(k.get("ses_hizi", 0.95))


def _donustur(giris: Path, cikis: Path, perde: float, tempo: float = 1.0) -> None:
    """Perde kaydırma (hız sabit) + 44.1 kHz mono."""
    filtre = []
    if abs(perde - 1.0) > 0.01:
        filtre += [f"asetrate={HZ}*{perde:.3f}", f"aresample={HZ}", f"atempo={1 / perde:.4f}"]
    if abs(tempo - 1.0) > 0.01:
        filtre.append(f"atempo={tempo:.4f}")
    filtre.append("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03")
    filtre.append("areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse")
    komut = [ffmpeg_yolu(), "-y", "-v", "error", "-i", str(giris), "-af", f"aresample={HZ}," + ",".join(filtre),
             "-ac", "1", "-ar", str(HZ), "-c:a", "pcm_s16le", str(cikis)]
    sonuc = subprocess.run(komut, capture_output=True, text=True)
    if sonuc.returncode != 0:
        raise RuntimeError(f"FFmpeg ses hatası: {sonuc.stderr[-800:]}")


def satiri_seslendir(metin: str, kim: str, k: dict[str, Any], klasor: Path, no: int) -> np.ndarray:
    ses, perde, hiz = konusan_sesi(kim, k)
    ham = klasor / f"satir_{no:02d}_ham.wav"
    seslendirme.sentezle(metin, ses, ham, hiz=hiz, yedek=k.get("ses_yedek"))
    son = klasor / f"satir_{no:02d}.wav"
    _donustur(ham, son, perde)
    ham.unlink(missing_ok=True)
    dizi = muzik.wav_oku(son)
    son.unlink(missing_ok=True)
    return dizi


def zamanlama(sahneler: list[dict[str, Any]], sureler: list[list[float]], tempo: float = 1.0
              ) -> tuple[list[dict[str, Any]], list[dict[str, float]], float]:
    """Satır sürelerinden satır ve sahne zamanlarını çıkarır (sesten bağımsız, test edilebilir)."""
    satirlar, sahne_z, t = [], [], 0.0
    for si, (sahne, ss) in enumerate(zip(sahneler, sureler)):
        bas = t
        t += ILK_GIRIS if si == 0 else SAHNE_GIRIS
        for li, (satir, d) in enumerate(zip(sahne["satirlar"], ss)):
            d = d / tempo
            satirlar.append({"sahne": si, "kim": satir["kim"], "metin": satir["metin"],
                             "duygu": satir.get("duygu", "mutlu"), "bas": round(t, 3), "son": round(t + d, 3)})
            t += d + (SATIR_ARASI if li + 1 < len(ss) else 0)
        t += FINAL_SONU if si == len(sahneler) - 1 else SAHNE_SONU
        sahne_z.append({"bas": round(bas, 3), "son": round(t, 3)})
    return satirlar, sahne_z, t


def kelime_zamanlari(satirlar: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Her satırın kelimeleri satır süresine uzunluklarına göre yayılır (metin senaryodan, hatasız)."""
    sonuc = []
    for s in satirlar:
        for z in seslendirme.tahmini_zamanlar(s["metin"], s["son"] - s["bas"]):
            sonuc.append({"kelime": z["kelime"], "bas": round(s["bas"] + z["bas"], 3),
                          "son": round(s["bas"] + z["son"], 3), "kim": s["kim"]})
    return sonuc


def _ass_renk(hex_renk: str) -> str:
    r, g, b = karakter._hex(hex_renk)
    return f"&H00{b:02X}{g:02X}{r:02X}"


def konusan_rengi(kim: str, k: dict[str, Any]) -> str:
    c = karakterler(k).get(kim)
    if not c:
        return "&H0000E5FF"  # anlatıcı: sarı
    renk = c.get("yazi_renk") or c.get("renk") or karakter.VARSAYILAN_RENK.get(c.get("tur", ""), "#FFE500")
    rgb = karakter._hex(renk)
    if sum(rgb) > 600:  # beyaz tavşan gibi açık renkler beyaz yazıda kaybolmasın
        rgb = (255, 140, 180)
    rgb = karakter._ton(rgb, 1.25)
    return _ass_renk("#%02X%02X%02X" % rgb)


def ass_yaz(kelimeler: list[dict[str, Any]], cikis: Path, k: dict[str, Any], kanca: str, toplam: float,
            son_yazi: str) -> None:
    seslendirme._DIL["dil"] = k.get("dil", "en")  # Türkçe büyük harf (i -> İ) doğru olsun
    stil = k.get("altyazi") or {}
    yazi = stil.get("yazi_tipi", "Comic Sans MS")
    boyut = int(stil.get("boyut", 90))
    satirlar = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        f"Style: Ana,{yazi},{boyut},&H00FFFFFF,&H000000FF,&H00402B2B,&H80000000,-1,0,0,0,100,100,1,0,1,9,3,2,60,60,200,1",
        f"Style: Kanca,{yazi},96,&H00FFFFFF,&H000000FF,&H00B04A7A,&H00000000,-1,0,0,0,100,100,1,0,3,26,0,8,70,70,250,1",
        f"Style: Son,{yazi},120,&H0000E5FF,&H000000FF,&H00402B2B,&H00000000,-1,0,0,0,100,100,2,0,1,12,4,8,60,60,360,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    t = seslendirme._ass_zaman
    temiz = seslendirme._temiz
    gruplar: list[list[dict[str, Any]]] = []
    for w in kelimeler:  # konuşan değişince yeni grup; 3 kelime / ~16 harf sınırı
        son = gruplar[-1] if gruplar else None
        if (son and son[-1]["kim"] == w["kim"] and len(son) < 3 and w["bas"] - son[-1]["son"] < 0.25
                and sum(len(x["kelime"]) for x in son) + len(w["kelime"]) <= 16):
            son.append(w)
        else:
            gruplar.append([w])
    for gi, g in enumerate(gruplar):
        bitis = g[-1]["son"] + 0.05
        if gi + 1 < len(gruplar):
            bitis = min(bitis + 0.25, gruplar[gi + 1][0]["bas"] - 0.04)
        vurgu = konusan_rengi(g[0]["kim"], k)
        for j, w in enumerate(g):
            bas = g[0]["bas"] if j == 0 else w["bas"]
            son = g[j + 1]["bas"] if j + 1 < len(g) else bitis
            metin = " ".join(
                (f"{{\\c{vurgu}\\t(0,80,\\fscx116\\fscy116)\\t(80,160,\\fscx106\\fscy106)}}{temiz(x['kelime'])}"
                 "{\\c&H00FFFFFF&\\fscx100\\fscy100}") if n == j else temiz(x["kelime"])
                for n, x in enumerate(g))
            giris = "{\\fad(60,0)}" if j == 0 else ""
            satirlar.append(f"Dialogue: 0,{t(bas)},{t(max(son, bas + 0.05))},Ana,,0,0,0,,{giris}{metin}")
    if kanca:
        satirlar.append(f"Dialogue: 2,0:00:00.00,{t(2.8)},Kanca,,0,0,0,,"
                        f"{{\\fad(0,250)\\t(0,160,\\fscx112\\fscy112)\\t(160,320,\\fscx100\\fscy100)}}{temiz(kanca)}")
    if son_yazi:
        satirlar.append(f"Dialogue: 2,{t(max(toplam - 1.7, 0))},{t(toplam)},Son,,0,0,0,,"
                        f"{{\\fad(200,0)\\t(0,200,\\fscx120\\fscy120)\\t(200,400,\\fscx100\\fscy100)}}{temiz(son_yazi)}")
    cikis.write_text("\n".join(satirlar) + "\n", encoding="utf-8")


def seslendir(is_: Is, k: dict[str, Any]) -> None:
    sahneler = is_.veri["sahneler_hikaye"]
    klasor = is_.klasor
    parcalar: list[list[np.ndarray]] = []
    no = 0
    for sahne in sahneler:
        sp = []
        for satir in sahne["satirlar"]:
            sp.append(satiri_seslendir(satir["metin"], satir["kim"], k, klasor, no))
            no += 1
        parcalar.append(sp)
    sureler = [[len(p) / HZ for p in sp] for sp in parcalar]
    _, _, toplam = zamanlama(sahneler, sureler)
    tempo = 1.0
    if toplam > EN_UZUN:  # biraz hızlandırarak 58 sn'ye sığdır (en fazla %15)
        konusma = sum(map(sum, sureler))
        tempo = konusma / max(konusma - (toplam - EN_UZUN), 0.1)
        if tempo > 1.15:
            raise ValueError(f"hikaye çok uzun ({toplam:.0f} sn); daha kısa yazılmalı")
        log.info("%s: süre %.1f sn, konuşma %%%.0f hızlandırılıyor", is_.id, toplam, (tempo - 1) * 100)
    satirlar, sahne_z, toplam = zamanlama(sahneler, sureler, tempo)
    ses = np.zeros(int((toplam + 0.2) * HZ), np.float32)
    for s, (si, li) in zip(satirlar, [(a, b) for a, sp in enumerate(parcalar) for b in range(len(sp))]):
        p = parcalar[si][li]
        if tempo != 1.0:  # basit yeniden örnekleme yerine FFmpeg atempo: perdeyi korur
            gecici = klasor / "tempo_gir.wav"
            muzik.wav_yaz(p, gecici)
            _donustur(gecici, klasor / "tempo_cik.wav", 1.0, tempo)
            p = muzik.wav_oku(klasor / "tempo_cik.wav")
            for x in ("tempo_gir.wav", "tempo_cik.wav"):
                (klasor / x).unlink(missing_ok=True)
        i = int(s["bas"] * HZ)
        ses[i:i + len(p)] += p[: len(ses) - i]
    tepe = float(np.max(np.abs(ses))) or 1.0
    ses = ses / tepe * 0.89
    muzik.wav_yaz(ses, klasor / "ses.wav")
    kelimeler = kelime_zamanlari(satirlar)
    ass_yaz(kelimeler, klasor / "altyazi.ass", k, str(is_.veri.get("kanca_metni", "")), toplam,
            "The End" if k.get("dil") == "en" else "Son")
    is_.veri.update({"ses": "ses.wav", "altyazi": "altyazi.ass", "sure": round(toplam, 2),
                     "satir_zamanlari": satirlar, "sahne_zamanlari": sahne_z,
                     "kelime_zamanlari": [{kk: v for kk, v in w.items() if kk != "kim"} for w in kelimeler]})
    log.info("%s: %d satır, %d ses, %.1f sn", is_.id, len(satirlar),
             len({s["kim"] for s in satirlar}), toplam)
