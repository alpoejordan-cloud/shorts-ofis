"""Kurgu: sahneleri 9:16 dikey videoya çevirir, sesi, müziği ve altyazıyı ekler (FFmpeg)."""
from __future__ import annotations

import random
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..cekirdek import KOK, Is, gunluk_al

log = gunluk_al("kurgu")
G, Y, FPS = 1080, 1920, 30
OLCEK = f"scale={G}:{Y}:force_original_aspect_ratio=increase,crop={G}:{Y},setsar=1,fps={FPS}"


def ffmpeg_yolu() -> str:
    yol = shutil.which("ffmpeg")
    if not yol:
        raise RuntimeError("FFmpeg bulunamadı. Kurulum betiğini (scripts/kurulum.ps1) çalıştır.")
    return yol


def calistir(arglar: list[str], klasor: Path) -> None:
    sonuc = subprocess.run([ffmpeg_yolu(), "-y", "-hide_banner", "-loglevel", "error", *arglar],
                           cwd=klasor, capture_output=True, text=True)
    if sonuc.returncode != 0:
        raise RuntimeError(f"FFmpeg hatası: {sonuc.stderr[-1500:]}")


def sahne_sureleri(adet: int, toplam: float, en_az: float = 2.5) -> list[float]:
    if adet <= 0:
        return []
    adet = max(1, min(adet, int(toplam // en_az) or 1))
    return [toplam / adet] * adet


def sahne_komutu(sahne: dict[str, Any], sure: float, cikis: str) -> list[str]:
    if sahne["tur"] == "desen":
        c0, c1 = sahne.get("renkler", ["0x0f2027", "0x2c5364"])
        kaynak = f"gradients=s={G}x{Y}:r={FPS}:c0={c0}:c1={c1}:speed=0.015:d={sure:.2f}"
        return ["-f", "lavfi", "-i", kaynak, "-t", f"{sure:.2f}", "-vf", "setsar=1,format=yuv420p",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", cikis]
    if sahne["tur"] == "resim":
        kare = int(sure * FPS)
        yakinlas = random.choice(["min(zoom+0.0009,1.12)", "if(eq(on,0),1.12,max(zoom-0.0009,1.0))"])
        filtre = (f"scale={G * 2}:{Y * 2}:force_original_aspect_ratio=increase,crop={G * 2}:{Y * 2},"
                  f"zoompan=z='{yakinlas}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={kare}:s={G}x{Y}:fps={FPS},setsar=1")
        return ["-loop", "1", "-i", sahne["yol"], "-t", f"{sure:.2f}", "-vf", filtre,
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", cikis]
    return ["-stream_loop", "-1", "-i", sahne["yol"], "-t", f"{sure:.2f}", "-vf", OLCEK,
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", cikis]


def final_komutu(sure: float, muzik: str | None, klip_sesi: tuple[str, float] | None,
                 muzik_seviyesi: float = 0.08) -> list[str]:
    girisler = ["-stream_loop", "-1", "-i", "ham_video.mp4", "-i", "ses.wav"]
    ses_zinciri = ["[1:a]volume=1.0[s0]"]
    karisim = ["[s0]"]
    sira = 2
    if muzik:
        girisler += ["-stream_loop", "-1", "-i", muzik]
        ses_zinciri.append(f"[{sira}:a]volume={muzik_seviyesi}[s{sira}]")
        karisim.append(f"[s{sira}]")
        sira += 1
    if klip_sesi:
        girisler += ["-i", klip_sesi[0]]
        ses_zinciri.append(f"[{sira}:a]volume={klip_sesi[1]}[s{sira}]")
        karisim.append(f"[s{sira}]")
        sira += 1
    if len(karisim) > 1:
        ses_zinciri.append(f"{''.join(karisim)}amix=inputs={len(karisim)}:duration=first:normalize=0[a]")
    else:
        ses_zinciri[0] = "[1:a]volume=1.0[a]"
    filtre = "[0:v]ass=altyazi.ass[v];" + ";".join(ses_zinciri)
    return girisler + [
        "-filter_complex", filtre, "-map", "[v]", "-map", "[a]", "-t", f"{sure:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "video.mp4",
    ]


def muzik_sec(k: dict[str, Any]) -> str | None:
    klasor = KOK / "muzik" / k.get("muzik_klasoru", k["id"])
    if not klasor.exists():
        klasor = KOK / "muzik"
    parcalar = [p for p in klasor.glob("*") if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg"}]
    return str(random.choice(parcalar).resolve()) if parcalar else None


def kurgula(is_: Is, k: dict[str, Any]) -> None:
    klasor = is_.klasor
    sure = min(float(is_.veri["sure"]) + 0.6, float(k.get("en_uzun_sure", 58)))
    sahneler = is_.veri["sahneler"]
    klip_sesi = None
    if is_.veri.get("mod") == "izinli_klip":
        klip = sahneler[0]
        sure = min(sure, float(klip.get("en_uzun", 30)) + 0.6) if klip.get("en_uzun") else sure
        sure = max(sure, float(is_.veri["sure"]) + 0.3)
        sureler = [sure]
        if klip.get("orijinal_ses"):
            klip_sesi = (str(Path(klip["yol"]).resolve()), float(klip["orijinal_ses"]))
    else:
        sureler = sahne_sureleri(len(sahneler), sure)
        sahneler = sahneler[: len(sureler)]

    parcalar = []
    for i, (sahne, s) in enumerate(zip(sahneler, sureler)):
        ad = f"parca_{i:02d}.mp4"
        if "yol" in sahne:
            sahne = {**sahne, "yol": str(Path(sahne["yol"]).resolve())}
        calistir(sahne_komutu(sahne, s, ad), klasor)
        parcalar.append(ad)
    (klasor / "liste.txt").write_text("".join(f"file '{p}'\n" for p in parcalar), encoding="utf-8")
    calistir(["-f", "concat", "-safe", "0", "-i", "liste.txt", "-c", "copy", "ham_video.mp4"], klasor)
    calistir(final_komutu(sure, muzik_sec(k), klip_sesi, k.get("muzik_seviyesi", 0.08)), klasor)
    for p in parcalar:
        (klasor / p).unlink(missing_ok=True)
    is_.veri["video"] = "video.mp4"
    log.info("%s: video hazır (%.1f sn)", is_.id, sure)
