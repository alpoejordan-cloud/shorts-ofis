"""Kanal görselleri: her kanal için YouTube banner'ı (2560x1440) ve profil fotoğrafı (800x800).

Tamamen özgün çizimler; oyun logosu, marka veya telifli görsel kullanılmaz.
Banner'daki yazılar YouTube'un her cihazda görünen güvenli alanında (ortadaki 1546x423) durur.
Çalıştır:  .venv\\Scripts\\python.exe scripts\\marka_uret.py
Çıktı:     marka\\<kanal_id>\\banner.png, profil.png
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

KOK = Path(__file__).resolve().parent.parent
CIKTI = KOK / "marka"
FONT = Path("C:/Windows/Fonts")
BW, BH = 2560, 1440
GUVENLI = (BW // 2 - 773, BH // 2 - 211, BW // 2 + 773, BH // 2 + 211)


def font(ad: str, boyut: int) -> ImageFont.FreeTypeFont:
    for aday in (ad, "seguibl.ttf", "ariblk.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(str(FONT / aday), boyut)
        except OSError:
            continue
    return ImageFont.load_default()


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def gradyan(w: int, h: int, renkler: list[str], aci: float = 90) -> Image.Image:
    """Çok duraklı doğrusal gradyan (aci: 90 = yukarıdan aşağı)."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    r = math.radians(aci)
    t = (x * math.cos(r) + y * math.sin(r))
    t = (t - t.min()) / (t.max() - t.min() + 1e-6)
    duraklar = np.linspace(0, 1, len(renkler))
    cikis = np.zeros((h, w, 3), np.float32)
    for kanal in range(3):
        cikis[..., kanal] = np.interp(t, duraklar, [hex_rgb(c)[kanal] for c in renkler])
    return Image.fromarray(cikis.clip(0, 255).astype(np.uint8), "RGB")


def isilti(taban: Image.Image, katman: Image.Image, yaricap: int = 18, guc: int = 2) -> Image.Image:
    """Neon parıltı: katmanı bulanıklaştırıp altına ekler."""
    sonuc = taban.convert("RGBA")
    parlak = katman.filter(ImageFilter.GaussianBlur(yaricap))
    for _ in range(guc):
        sonuc = Image.alpha_composite(sonuc, parlak)
    return Image.alpha_composite(sonuc, katman)


def yazi_katmani(boyut: tuple[int, int], parcalar: list[tuple[str, ImageFont.FreeTypeFont, str, tuple[int, int], str]]):
    k = Image.new("RGBA", boyut, (0, 0, 0, 0))
    d = ImageDraw.Draw(k)
    for metin, f, renk, (x, y), hiza in parcalar:
        d.text((x, y), metin, font=f, fill=renk, anchor=hiza)
    return k


def golge(taban: Image.Image, katman: Image.Image, kayma: int = 8, bulanik: int = 10, opaklik: int = 160):
    a = katman.split()[3].point(lambda v: v * opaklik // 255)
    g = Image.new("RGBA", katman.size, (0, 0, 0, 0))
    g.putalpha(a)
    g = g.filter(ImageFilter.GaussianBlur(bulanik))
    sonuc = taban.convert("RGBA")
    sonuc.alpha_composite(g, (kayma, kayma))
    return Image.alpha_composite(sonuc, katman)


def daire_maske(boyut: int) -> Image.Image:
    m = Image.new("L", (boyut, boyut), 0)
    ImageDraw.Draw(m).ellipse((0, 0, boyut - 1, boyut - 1), fill=255)
    return m


# ---------------------------------------------------------------- Teknoloji (EN)

def devre_cizgileri(w: int, h: int, renk: tuple[int, int, int], adet: int, tohum: int) -> Image.Image:
    rnd = random.Random(tohum)
    k = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(k)
    for _ in range(adet):
        x, y = rnd.randrange(0, w), rnd.randrange(0, h)
        nokta = [(x, y)]
        for _ in range(rnd.randint(2, 5)):
            if rnd.random() < 0.5:
                x += rnd.choice([-1, 1]) * rnd.randint(60, 260)
            else:
                y += rnd.choice([-1, 1]) * rnd.randint(40, 160)
            nokta.append((x, y))
        a = rnd.randint(40, 110)
        d.line(nokta, fill=(*renk, a), width=3, joint="curve")
        ex, ey = nokta[-1]
        d.ellipse((ex - 7, ey - 7, ex + 7, ey + 7), outline=(*renk, a + 60), width=3)
    return k


def teknoloji_banner() -> Image.Image:
    img = gradyan(BW, BH, ["#050816", "#0b1a3a", "#0e2a6b", "#071029"], aci=20)
    devre = devre_cizgileri(BW, BH, (64, 196, 255), 90, 7)
    img = isilti(img, devre, 6, 1)
    # sağda kronometre halkası
    cx, cy, r = BW // 2 + 560, BH // 2, 190
    halka = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    d = ImageDraw.Draw(halka)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(0, 229, 255, 255), width=14)
    d.arc((cx - r - 34, cy - r - 34, cx + r + 34, cy + r + 34), 200, 330, fill=(124, 92, 255, 255), width=10)
    for i in range(60):
        a = math.radians(i * 6 - 90)
        uzun = 26 if i % 5 == 0 else 12
        d.line((cx + (r - 30) * math.cos(a), cy + (r - 30) * math.sin(a),
                cx + (r - 30 - uzun) * math.cos(a), cy + (r - 30 - uzun) * math.sin(a)),
               fill=(180, 240, 255, 230), width=4 if i % 5 == 0 else 2)
    d.text((cx, cy + 6), "30", font=font("seguibl.ttf", 170), fill=(255, 255, 255, 255), anchor="mm")
    d.text((cx, cy + 120), "SEC", font=font("bahnschrift.ttf", 44), fill=(0, 229, 255, 255), anchor="mm")
    img = isilti(img, halka, 22, 2)
    yazi = yazi_katmani((BW, BH), [
        ("TECH IN 30", font("seguibl.ttf", 170), "#ffffff", (BW // 2 - 760, BH // 2 - 40), "ls"),
        ("AI & tech news explained in 30 seconds", font("bahnschrift.ttf", 60), "#9fe8ff",
         (BW // 2 - 756, BH // 2 + 50), "ls"),
        ("NEW SHORT EVERY DAY", font("seguibl.ttf", 44), "#00e5ff", (BW // 2 - 756, BH // 2 + 150), "ls"),
    ])
    return golge(img, yazi).convert("RGB")


def teknoloji_profil() -> Image.Image:
    s = 800
    img = gradyan(s, s, ["#0e2a6b", "#050816"], aci=60)
    k = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(k)
    d.ellipse((90, 90, 710, 710), outline=(0, 229, 255, 255), width=22)
    d.arc((50, 50, 750, 750), 200, 330, fill=(124, 92, 255, 255), width=16)
    for i in range(12):
        a = math.radians(i * 30 - 90)
        d.line((400 + 270 * math.cos(a), 400 + 270 * math.sin(a), 400 + 240 * math.cos(a), 400 + 240 * math.sin(a)),
               fill=(180, 240, 255, 255), width=8)
    d.text((400, 390), "30", font=font("seguibl.ttf", 300), fill=(255, 255, 255, 255), anchor="mm")
    d.text((400, 560), "TECH", font=font("seguibl.ttf", 70), fill=(0, 229, 255, 255), anchor="mm")
    return isilti(img, k, 16, 2).convert("RGB")


# ---------------------------------------------------------------- Finans (TR)

def para_desen(w: int, h: int, tohum: int) -> Image.Image:
    rnd = random.Random(tohum)
    k = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(k)
    # yükselen grafik çizgisi
    noktalar, y = [], h * 0.78
    for x in range(0, w + 80, 80):
        y = max(h * 0.25, min(h * 0.9, y - rnd.uniform(-35, 55)))
        noktalar.append((x, y))
    d.line(noktalar, fill=(255, 214, 102, 70), width=8, joint="curve")
    alan = noktalar + [(w, h), (0, h)]
    d.polygon(alan, fill=(255, 214, 102, 18))
    # ince ızgara
    for x in range(0, w, 120):
        d.line((x, 0, x, h), fill=(255, 255, 255, 10), width=1)
    for y2 in range(0, h, 120):
        d.line((0, y2, w, y2), fill=(255, 255, 255, 10), width=1)
    return k


def madeni_para(boyut: int, simge: str = "₺") -> Image.Image:
    k = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    altin = gradyan(boyut, boyut, ["#fff1b8", "#f5c542", "#c8901a", "#f7d774"], aci=45).convert("RGBA")
    altin.putalpha(daire_maske(boyut))
    k.alpha_composite(altin)
    d = ImageDraw.Draw(k)
    p = boyut // 14
    d.ellipse((p, p, boyut - p, boyut - p), outline=(150, 100, 10, 200), width=max(boyut // 60, 3))
    d.text((boyut // 2, boyut // 2 + boyut // 40), simge, font=font("seguibl.ttf", int(boyut * 0.56)),
           fill=(120, 78, 0, 255), anchor="mm")
    return k


def finans_banner() -> Image.Image:
    img = gradyan(BW, BH, ["#022c22", "#064e3b", "#065f46", "#022c22"], aci=15).convert("RGBA")
    img = Image.alpha_composite(img, para_desen(BW, BH, 3))
    para = madeni_para(340)
    golgeli = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    for (x, y, olcek) in [(BW // 2 + 560, BH // 2 - 250, 1.0), (BW // 2 + 790, BH // 2 - 30, 0.7)]:
        p = para.resize((int(340 * olcek), int(340 * olcek)), Image.LANCZOS)
        golgeli.alpha_composite(p, (x, y))
    img = golge(img, golgeli, 14, 18, 150)
    yazi = yazi_katmani((BW, BH), [
        ("CEBİNE BİLGİ", font("seguibl.ttf", 160), "#ffffff", (BW // 2 - 760, BH // 2 - 40), "ls"),
        ("Para, bütçe ve ekonomi: 60 saniyede, sade Türkçe", font("bahnschrift.ttf", 58), "#bbf7d0",
         (BW // 2 - 756, BH // 2 + 48), "ls"),
        ("HER GÜN YENİ VİDEO", font("seguibl.ttf", 44), "#fcd34d", (BW // 2 - 756, BH // 2 + 148), "ls"),
    ])
    return golge(img, yazi).convert("RGB")


def finans_profil() -> Image.Image:
    s = 800
    img = gradyan(s, s, ["#065f46", "#022c22"], aci=60).convert("RGBA")
    para = madeni_para(560)
    img = golge(img, Image.new("RGBA", (s, s)).copy() if False else _ortala(para, s), 12, 16, 160)
    return img.convert("RGB")


def _ortala(parca: Image.Image, s: int) -> Image.Image:
    k = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    k.alpha_composite(parca, ((s - parca.width) // 2, (s - parca.height) // 2))
    return k


# ---------------------------------------------------------------- GTA tarzı oyun kanalı (EN)

def palmiye(d: ImageDraw.ImageDraw, x: int, taban: int, boy: int, renk, egim: float = 0.15) -> None:
    ust = (x + int(boy * egim), taban - boy)
    for i in range(16):  # gövde
        t0, t1 = i / 16, (i + 1) / 16
        x0 = x + (ust[0] - x) * t0 ** 1.5
        x1 = x + (ust[0] - x) * t1 ** 1.5
        y0, y1 = taban - boy * t0, taban - boy * t1
        g = int(boy * 0.035 * (1 - t0 * 0.5))
        d.polygon([(x0 - g, y0), (x0 + g, y0), (x1 + g * 0.9, y1), (x1 - g * 0.9, y1)], fill=renk)
    for aci in (-160, -135, -110, -70, -45, -20, 10, 200):  # yapraklar
        a = math.radians(aci)
        uzun = boy * 0.42
        uc = (ust[0] + uzun * math.cos(a), ust[1] + uzun * math.sin(a) + uzun * 0.35)
        orta = (ust[0] + uzun * 0.55 * math.cos(a), ust[1] + uzun * 0.55 * math.sin(a) - uzun * 0.05)
        kal = boy * 0.03
        d.polygon([ust, (orta[0], orta[1] - kal), uc, (orta[0], orta[1] + kal)], fill=renk)


def gunes_ve_izgara(w: int, h: int, ufuk: int, gunes_r: int, gx: int) -> Image.Image:
    k = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gunes = gradyan(gunes_r * 2, gunes_r * 2, ["#ffe66d", "#ff9f43", "#ff2e88"], aci=90).convert("RGBA")
    maske = daire_maske(gunes_r * 2)
    md = ImageDraw.Draw(maske)
    for i in range(7):  # retro şeritler
        y = gunes_r + 20 + i * (gunes_r // 7)
        md.rectangle((0, y, gunes_r * 2, y + 6 + i * 3), fill=0)
    gunes.putalpha(maske)
    k.alpha_composite(gunes, (gx - gunes_r, ufuk - gunes_r * 2 + 30))
    d = ImageDraw.Draw(k)
    d.rectangle((0, ufuk, w, h), fill=(18, 4, 38, 255))
    for i in range(-30, 31):  # perspektif ızgara
        d.line((w // 2 + i * 40, ufuk, w // 2 + i * 260, h), fill=(255, 46, 136, 150), width=3)
    y, aralik = ufuk, 10
    while y < h:
        d.line((0, y, w, y), fill=(255, 46, 136, 150), width=3)
        aralik *= 1.35
        y += int(aralik)
    return k


def oyun_banner() -> Image.Image:
    img = gradyan(BW, BH, ["#1a0533", "#5b1066", "#c2185b", "#ff7043", "#ffb74d"], aci=90).convert("RGBA")
    ufuk = int(BH * 0.70)
    img = isilti(img, gunes_ve_izgara(BW, BH, ufuk, 300, BW // 2 + 470), 25, 1)
    silu = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    d = ImageDraw.Draw(silu)
    rnd = random.Random(5)
    x = 0
    while x < BW:  # şehir silüeti
        gen, boy = rnd.randint(60, 140), rnd.randint(80, 330)
        if BW // 2 - 820 < x < BW // 2 + 260:  # yazının arkası alçak kalsın, okunurluk
            boy = rnd.randint(30, 110)
        else:
            boy = int(boy * 1.3)
        d.rectangle((x, ufuk - boy, x + gen, ufuk), fill=(20, 4, 40, 255))
        x += gen + rnd.randint(0, 20)
    for px, b, e in [(BW // 2 - 980, 620, 0.12), (BW // 2 - 900, 470, -0.1), (BW // 2 + 900, 560, -0.14),
                     (BW // 2 + 1010, 430, 0.1)]:
        palmiye(d, px, ufuk + 6, b, (16, 2, 30, 255), e)
    img = Image.alpha_composite(img, silu)
    neon = yazi_katmani((BW, BH), [
        ("VICE SIGNAL", font("seguibl.ttf", 170), "#ffffff", (BW // 2 - 760, BH // 2 - 40), "ls"),
    ])
    pembe = Image.new("RGBA", (BW, BH), (255, 46, 136, 0))
    pembe.putalpha(neon.split()[3])
    img = isilti(img, pembe, 26, 2)
    img = Image.alpha_composite(img, neon)
    alt = yazi_katmani((BW, BH), [
        ("GTA news, hidden details & rumor checks", font("bahnschrift.ttf", 60), "#ffe0f0",
         (BW // 2 - 756, BH // 2 + 50), "ls"),
        ("NEW SHORT EVERY DAY", font("seguibl.ttf", 44), "#ffe66d", (BW // 2 - 756, BH // 2 + 150), "ls"),
    ])
    return golge(img, alt, 6, 8, 180).convert("RGB")


def oyun_profil() -> Image.Image:
    s = 800
    img = gradyan(s, s, ["#1a0533", "#7b1fa2", "#ff2e88", "#ff9f43"], aci=90).convert("RGBA")
    img = Image.alpha_composite(img, gunes_ve_izgara(s, s, 560, 190, 400))
    silu = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    palmiye(ImageDraw.Draw(silu), 95, 600, 400, (16, 2, 30, 255), 0.10)
    palmiye(ImageDraw.Draw(silu), 720, 600, 330, (16, 2, 30, 255), -0.10)
    img = Image.alpha_composite(img, silu)
    yazi = yazi_katmani((s, s), [("VS", font("seguibl.ttf", 300), "#ffffff", (400, 330), "mm")])
    pembe = Image.new("RGBA", (s, s), (255, 46, 136, 0))
    pembe.putalpha(yazi.split()[3])
    img = isilti(img, pembe, 18, 2)
    return Image.alpha_composite(img, yazi).convert("RGB")


KANALLAR = {
    "teknoloji_en": (teknoloji_banner, teknoloji_profil),
    "finans_tr": (finans_banner, finans_profil),
    "gta_en": (oyun_banner, oyun_profil),
}


def main() -> None:
    for kanal_id, (banner, profil) in KANALLAR.items():
        klasor = CIKTI / kanal_id
        klasor.mkdir(parents=True, exist_ok=True)
        banner().save(klasor / "banner.png", optimize=True)
        profil().save(klasor / "profil.png", optimize=True)
        print("Hazır:", klasor)


if __name__ == "__main__":
    main()
