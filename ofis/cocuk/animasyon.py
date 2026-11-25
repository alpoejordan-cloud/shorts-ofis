"""Animasyon: hikayeyi 1080x1920, 30 fps dikey videoya çevirir.

- Her sahne kendi mekanında; kamera yavaşça kayar, bulut/yıldız/kar/kelebek gibi küçük hareketler
- Karakterler sahneye zıplayarak girer, nefes alır gibi sallanır, göz kırpar
- Konuşan karakterin ağzı sesin şiddetine göre açılıp kapanır (dudak senkronu), konuşurken hoplar
- Duygular (mutlu, şaşkın, üzgün, heyecanlı) yüz ifadesine yansır
- Müzik konuşma sırasında kısılır; giriş "pop", sahne geçişi zil, sonda parıltı efekti
"""
from __future__ import annotations

import math
import random
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from ..ajanlar.kurgu import ffmpeg_yolu
from ..cekirdek import Is, gunluk_al, ortam
from ..olay import calisiyor
from . import karakter, muzik, sahne
from .ses import karakterler

log = gunluk_al("cocuk_animasyon")
FPS = 30
G, Y = sahne.G, sahne.Y
GIRIS_SN = 0.55
GECIS_SN = 0.28


def yerlesim(adet: int) -> tuple[list[int], float]:
    """Karakter sayısına göre yatay konumlar ve ölçek."""
    if adet <= 1:
        return [540], 1.75
    if adet == 2:
        return [290, 790], 1.5
    return [190, 540, 890][:adet], 1.12


def zarf(ses: np.ndarray, kare_sayisi: int) -> np.ndarray:
    """Her kare için sesin şiddeti (0-1): dudak senkronu ve müzik kısma için."""
    adim = muzik.HZ / FPS
    sonuc = np.zeros(kare_sayisi, np.float32)
    for i in range(kare_sayisi):
        p = ses[int(i * adim): int((i + 1) * adim)]
        sonuc[i] = float(np.sqrt(np.mean(p * p))) if len(p) else 0.0
    tepe = float(np.percentile(sonuc[sonuc > 0], 95)) if np.any(sonuc > 0) else 1.0
    return np.clip(sonuc / (tepe or 1.0), 0, 1)


def goz_kirpma_anlari(sure: float, tohum: str) -> list[float]:
    rnd, t, anlar = random.Random(tohum), 0.5, []
    while t < sure:
        t += rnd.uniform(2.0, 4.8)
        anlar.append(t)
    return anlar


_GOLGE: dict[int, Image.Image] = {}


def golge(genislik: int) -> Image.Image:
    if genislik not in _GOLGE:
        img = Image.new("RGBA", (genislik, genislik // 5), (0, 0, 0, 0))
        ImageDraw.Draw(img).ellipse([0, 0, genislik - 1, genislik // 5 - 1], fill=(0, 0, 0, 60))
        _GOLGE[genislik] = img
    return _GOLGE[genislik]


def _kolay(x: float) -> float:
    return 1 - (1 - min(max(x, 0.0), 1.0)) ** 3


def mix_yaz(is_: Is, k: dict[str, Any], ses: np.ndarray, kz: np.ndarray, toplam: float, klasor: Path) -> None:
    n = int(toplam * muzik.HZ)
    ses = np.pad(ses, (0, max(0, n - len(ses))))[:n]
    m = muzik.muzik_uret(toplam, is_.id)
    m = np.pad(m, (0, max(0, n - len(m))))[:n]
    # konuşurken müzik kısılır (yumuşak geçiş)
    konusma = np.repeat((kz > 0.08).astype(np.float32), int(muzik.HZ / FPS) + 1)[:n]
    konusma = np.pad(konusma, (0, max(0, n - len(konusma))))
    pencere = int(0.25 * muzik.HZ)
    yumusak = np.convolve(konusma, np.ones(pencere) / pencere, mode="same")
    kazanc = float(k.get("muzik_seviyesi", 0.2)) * (1 - 0.55 * yumusak)
    karisim = ses + m * kazanc
    efekt = float(k.get("efekt_seviyesi", 0.35))

    def ekle(p: np.ndarray, t: float):
        i = int(t * muzik.HZ)
        if 0 <= i < n:
            karisim[i:i + len(p)] += p[: n - i] * efekt

    for si, sz in enumerate(is_.veri["sahne_zamanlari"]):
        if si > 0:
            ekle(muzik.zil(), sz["bas"])
        for j in range(len(is_.veri["sahneler_hikaye"][si].get("karakterler", []))):
            ekle(muzik.pop(), sz["bas"] + 0.08 + j * 0.12)
    ekle(muzik.parilti(), max(toplam - 1.7, 0))
    tepe = float(np.max(np.abs(karisim))) or 1.0
    muzik.wav_yaz(karisim / max(tepe, 1.0) * 0.95, klasor / "karisim.wav")


def kareler(is_: Is, k: dict[str, Any], kz: np.ndarray):
    """Videonun karelerini sırayla üretir (PIL Image, RGB)."""
    kadro = karakterler(k)
    sahneler = is_.veri["sahneler_hikaye"]
    satirlar = is_.veri["satir_zamanlari"]
    toplam = float(is_.veri["sure"])
    kirpma = {c: goz_kirpma_anlari(toplam, f"{is_.id}-{c}") for c in kadro}
    for si, (sh, sz) in enumerate(zip(sahneler, is_.veri["sahne_zamanlari"])):
        canli = sahne.Canlandirici(sh.get("yer", "cayir"), hash((is_.id, si)) & 0xFFFF, sz["son"] - sz["bas"])
        ids = [c for c in sh.get("karakterler", []) if c in kadro][:3]
        xs, olcek = yerlesim(len(ids))
        sahne_satirlari = [s for s in satirlar if s["sahne"] == si]
        bas_kare, son_kare = int(round(sz["bas"] * FPS)), int(round(sz["son"] * FPS))
        if si == len(sahneler) - 1:
            son_kare = int(math.ceil(toplam * FPS))
        for kn in range(bas_kare, son_kare):
            t = kn / FPS
            yerel = t - sz["bas"]
            img = canli.kare(yerel)
            aktif = next((s for s in sahne_satirlari if s["bas"] - 0.05 <= t <= s["son"] + 0.05), None)
            onceki = [s for s in sahne_satirlari if s["bas"] <= t]
            anlatici_duygu = next((s["duygu"] for s in reversed(onceki) if s["kim"] not in kadro), "mutlu")
            for ci, (cid, x) in enumerate(zip(ids, xs)):
                c = kadro[cid]
                konusuyor = aktif is not None and aktif["kim"] == cid
                if konusuyor:
                    duygu = aktif["duygu"]
                else:
                    kendi = next((s["duygu"] for s in reversed(onceki) if s["kim"] == cid), None)
                    duygu = kendi or anlatici_duygu
                agiz = konusuyor and kn < len(kz) and kz[kn] > 0.22 and (kz[kn] > 0.55 or kn % 4 < 3)
                goz = not any(0 <= t - a < 0.13 for a in kirpma[cid])
                spr = karakter.sprite(c, agiz_acik=agiz, goz_acik=goz, duygu=duygu, olcek=olcek)
                if x > 540:
                    spr = ImageOps.mirror(spr)
                # hareket: giriş zıplaması, nefes, konuşurken hoplama
                faz = ci * 1.7
                dy = 6 * math.sin(2 * math.pi * 0.6 * t + faz)
                if konusuyor:
                    hop = 26 if duygu == "heyecanli" else 15
                    dy -= hop * abs(math.sin(2 * math.pi * 2.2 * (t - aktif["bas"])))
                dx = 0.0
                g = (yerel - ci * 0.12) / GIRIS_SN
                if si > 0 and g < 1:
                    yon = -1 if x <= 540 else 1
                    dx = yon * 700 * (1 - _kolay(g))
                    dy -= 120 * math.sin(math.pi * min(max(g, 0), 1))
                elif si == 0 and yerel < 0.25:  # ilk sahne: anında "pop"
                    o = 0.6 + 0.4 * _kolay(yerel / 0.25)
                    spr = spr.resize((max(1, int(spr.width * o)), max(1, int(spr.height * o))))
                ezilme = 1 + (0.035 * math.sin(2 * math.pi * 4.4 * (t - aktif["bas"])) if konusuyor else
                              0.012 * math.sin(2 * math.pi * 0.6 * t + faz))
                if abs(ezilme - 1) > 0.004:
                    spr = spr.resize((spr.width, max(1, int(spr.height * ezilme))))
                ayak = sahne.ZEMIN + 10
                gol = golge(int(spr.width * 0.62))
                img.paste(gol, (int(x + dx - gol.width / 2), ayak - gol.height // 2), gol)
                img.paste(spr, (int(x + dx - spr.width / 2), int(ayak - spr.height + dy)), spr)
            if si == len(sahneler) - 1 and toplam - t < 1.8:  # final parıltısı
                d = ImageDraw.Draw(img)
                rnd = random.Random(kn // 3)
                for _ in range(16):
                    px, py, r = rnd.uniform(60, G - 60), rnd.uniform(500, 1400), rnd.uniform(8, 20)
                    d.polygon([(px, py - r), (px + r * 0.3, py - r * 0.3), (px + r, py), (px + r * 0.3, py + r * 0.3),
                               (px, py + r), (px - r * 0.3, py + r * 0.3), (px - r, py), (px - r * 0.3, py - r * 0.3)],
                              fill=(255, 230, 120))
            # sahne geçişi: krem renge kısa açılış/kapanış
            a = 0.0
            if si > 0 and yerel < GECIS_SN:
                a = 1 - yerel / GECIS_SN
            elif si < len(sahneler) - 1 and sz["son"] - t < GECIS_SN:
                a = 1 - (sz["son"] - t) / GECIS_SN
            if a > 0.01:
                img = Image.blend(img, Image.new("RGB", img.size, (255, 248, 232)), min(a, 1.0) * 0.9)
            yield img


def canlandir(is_: Is, k: dict[str, Any]) -> None:
    klasor = is_.klasor
    toplam = float(is_.veri["sure"])
    ses = muzik.wav_oku(klasor / "ses.wav")
    kare_sayisi = int(math.ceil(toplam * FPS))
    kz = zarf(ses, kare_sayisi)
    mix_yaz(is_, k, ses, kz, toplam, klasor)
    n = ortam("FFMPEG_IS_PARCACIGI", "2")
    komut = [ffmpeg_yolu(), "-y", "-hide_banner", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{G}x{Y}", "-r", str(FPS), "-i", "-",
             "-i", "karisim.wav",
             "-filter_complex", "[0:v]ass=altyazi.ass[v];[1:a]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-threads", n, "-shortest",
             "-movflags", "+faststart", "video.mp4"]
    surec = subprocess.Popen(komut, cwd=klasor, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    sayac = 0
    try:
        with calisiyor(None, f"animasyonu çiziyor ({kare_sayisi} kare)", yz="ffmpeg"):
            for img in kareler(is_, k, kz):
                surec.stdin.write(img.tobytes())  # type: ignore[union-attr]
                sayac += 1
        surec.stdin.close()  # type: ignore[union-attr]
    except BrokenPipeError:
        pass
    hata = surec.stderr.read().decode("utf-8", "ignore") if surec.stderr else ""
    if surec.wait() != 0:
        raise RuntimeError(f"FFmpeg animasyon hatası: {hata[-1500:]}")
    (klasor / "karisim.wav").unlink(missing_ok=True)
    is_.veri.update({"video": "video.mp4", "kare_sayisi": sayac, "muzik": "otomatik müzik kutusu (özgün)"})
    log.info("%s: animasyon hazır (%.1f sn, %d kare, %d sahne)", is_.id, toplam, sayac,
             len(is_.veri["sahneler_hikaye"]))


def sahne_hazirla(is_: Is, k: dict[str, Any]) -> None:
    """Görsel aşaması: çizilecek mekanları ve karakterleri önceden çizip önbelleğe alır (hata erken çıksın)."""
    kadro = karakterler(k)
    for sh in is_.veri["sahneler_hikaye"]:
        sahne.arka_plan(sh.get("yer", "cayir"), 0)
        for cid in sh.get("karakterler", []):
            if cid in kadro:
                karakter.sprite(kadro[cid])
    is_.veri["sahneler"] = [{"tur": "animasyon", "yer": sh.get("yer")} for sh in is_.veri["sahneler_hikaye"]]
