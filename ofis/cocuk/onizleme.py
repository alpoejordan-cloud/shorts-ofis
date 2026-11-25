"""Çocuk kanalı önizlemeleri ve kanal görselleri (profil 800x800, banner 2560x1440) — aynı karakterlerle."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from ..cekirdek import KOK, RAPORLAR
from . import karakter, sahne

YAZI_TIPLERI = ["C:/Windows/Fonts/comicbd.ttf", "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def yazi_tipi(boyut: int):
    for yol in YAZI_TIPLERI:
        if Path(yol).exists():
            return ImageFont.truetype(yol, boyut)
    return ImageFont.load_default()


def _ortali_yazi(d: ImageDraw.ImageDraw, x: int, y: int, metin: str, boyut: int, renk=(255, 255, 255),
                 kenar=(60, 40, 90), kalinlik: int = 8):
    f = yazi_tipi(boyut)
    d.text((x, y), metin, font=f, fill=renk, anchor="mm", stroke_width=kalinlik, stroke_fill=kenar)


def kadro_gorseli(k: dict[str, Any], cikis: Path | None = None) -> Path:
    kadro = k.get("karakterler", [])
    img = sahne.arka_plan("cayir", 0).crop((100, 400, 100 + 1080, 400 + 1100)).copy()
    d = ImageDraw.Draw(img)
    _ortali_yazi(d, 540, 90, k.get("ad", k["id"]), 76)
    adet = len(kadro)
    for i, c in enumerate(kadro):
        x = int(1080 * (i + 0.5) / max(adet, 1))
        olcek = 0.62 if adet > 3 else 0.9
        spr = karakter.sprite(c, duygu="mutlu" if i % 2 == 0 else "heyecanli", olcek=olcek)
        img.paste(spr, (x - spr.width // 2, 930 - spr.height), spr)
        _ortali_yazi(d, x, 990, str(c.get("ad", c["id"])), 44, kalinlik=6)
    cikis = cikis or RAPORLAR / f"{k['id']}_karakterler.png"
    img.save(cikis)
    return cikis


def kanal_gorselleri(k: dict[str, Any], klasor: Path | None = None) -> list[Path]:
    """Profil fotoğrafı (ana karakter) ve kanal banner'ı (tüm kadro + kanal adı)."""
    klasor = klasor or KOK / "branding" / k["id"]
    klasor.mkdir(parents=True, exist_ok=True)
    kadro = k.get("karakterler", [])
    # profil: ana karakter yüzü, renkli daire üzerinde
    p = Image.new("RGB", (800, 800), (255, 214, 102))
    d = ImageDraw.Draw(p)
    d.ellipse([30, 30, 770, 770], fill=(120, 200, 250))
    spr = karakter.sprite(kadro[0], duygu="heyecanli", olcek=2.2)
    p.paste(spr, (400 - spr.width // 2, 70), spr)
    profil = klasor / "profil.png"
    p.save(profil)
    # banner: güvenli alan ortadaki 1546x423
    b = sahne.arka_plan("cayir", 0).resize((2560, int(1920 * 2560 / 1280))).crop((0, 2200, 2560, 3640))
    d = ImageDraw.Draw(b)
    _ortali_yazi(d, 1280, 560, k.get("ad", k["id"]), 120, kalinlik=12)
    alt = "Stories for little ones" if k.get("dil") == "en" else "Minikler için masallar"
    _ortali_yazi(d, 1280, 680, alt, 56, renk=(255, 236, 120), kalinlik=8)
    xs = [560, 790, 1770, 2000, 2230][: max(0, len(kadro) - 1)]
    for c, x in zip(kadro[1:], xs):
        s = karakter.sprite(c, olcek=0.72)
        b.paste(s, (x - s.width // 2, 935 - s.height), s)
    s = karakter.sprite(kadro[0], duygu="heyecanli", olcek=0.72)
    b.paste(s, (330 - s.width // 2, 935 - s.height), s)
    banner = klasor / "banner.png"
    b.save(banner)
    return [profil, banner]
