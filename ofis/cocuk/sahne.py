"""Arka planlar: kodla çizilen sevimli mekanlar ve üzerlerindeki küçük hareketler
(süzülen bulutlar, yanıp sönen yıldızlar, kar, ateş böcekleri, kelebekler, su parıltısı).

Arka plan ekrandan biraz geniş çizilir (1280x1920); kamera sahne boyunca yavaşça kayar.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

G, Y = 1080, 1920
GENIS = 1280
ZEMIN = 1480  # karakterlerin ayaklarının bastığı çizgi
YERLER = ("cayir", "orman", "sahil", "gece", "kar", "bahce", "oda", "gol")
YER_ADLARI = {
    "cayir": "sunny meadow / güneşli çayır", "orman": "friendly forest / orman", "sahil": "beach / sahil",
    "gece": "starry night / yıldızlı gece", "kar": "snowy hill / karlı tepe", "bahce": "flower garden / çiçek bahçesi",
    "oda": "cozy bedroom / sıcacık oda", "gol": "pond / gölet",
}
BULUTLU = {"cayir", "sahil", "kar", "bahce", "gol"}


def _gradyan(d: ImageDraw.ImageDraw, ust, alt, y0: int, y1: int, f: int, genis: int):
    for y in range(y0 * f, y1 * f, 2):
        t = (y - y0 * f) / max(1, (y1 - y0) * f)
        d.rectangle([0, y, genis * f, y + 2], fill=tuple(int(a + (b - a) * t) for a, b in zip(ust, alt)))


def _tepe(d, f, genis, y_orta, genlik, dalga, faz, renk):
    noktalar = [(0, Y * f)]
    for x in range(0, genis + 20, 20):
        yy = y_orta + genlik * math.sin(x / dalga + faz) + genlik * 0.4 * math.sin(x / (dalga * 0.47) + faz * 2)
        noktalar.append((x * f, yy * f))
    noktalar.append((genis * f, Y * f))
    d.polygon(noktalar, fill=renk)


def _agac(d, f, x, y, boy, renk=(86, 170, 90), govde=(140, 96, 60)):
    d.rounded_rectangle([(x - 14) * f, (y - boy * 0.45) * f, (x + 14) * f, y * f], 8 * f, fill=govde)
    for dx, dy, r in ((0, -boy * 0.75, boy * 0.32), (-boy * 0.2, -boy * 0.55, boy * 0.25), (boy * 0.2, -boy * 0.55, boy * 0.25)):
        d.ellipse([(x + dx - r) * f, (y + dy - r) * f, (x + dx + r) * f, (y + dy + r) * f], fill=renk)


def _cam(d, f, x, y, boy, renk=(60, 140, 90), karli=False):
    for i in range(3):
        g = boy * (0.5 - i * 0.12)
        ust = y - boy * (0.35 + i * 0.25)
        alt = ust + boy * 0.42
        d.polygon([((x - g) * f, alt * f), (x * f, (ust - boy * 0.08) * f), ((x + g) * f, alt * f)], fill=renk)
        if karli:
            d.polygon([((x - g * 0.45) * f, (ust + boy * 0.08) * f), (x * f, (ust - boy * 0.08) * f),
                       ((x + g * 0.45) * f, (ust + boy * 0.08) * f)], fill=(250, 252, 255))
    d.rectangle([(x - 12) * f, (y - boy * 0.1) * f, (x + 12) * f, y * f], fill=(120, 84, 56))


def _cicek(d, f, x, y, r, renk):
    for a in range(5):
        aa = a * 2 * math.pi / 5
        cx, cy = x + math.cos(aa) * r, y + math.sin(aa) * r
        d.ellipse([(cx - r * 0.75) * f, (cy - r * 0.75) * f, (cx + r * 0.75) * f, (cy + r * 0.75) * f], fill=renk)
    d.ellipse([(x - r * 0.6) * f, (y - r * 0.6) * f, (x + r * 0.6) * f, (y + r * 0.6) * f], fill=(255, 214, 90))


def _gunes(d, f, x, y, r):
    for a in range(12):
        aa = a * math.pi / 6
        d.line([((x + math.cos(aa) * r * 1.25) * f, (y + math.sin(aa) * r * 1.25) * f),
                ((x + math.cos(aa) * r * 1.6) * f, (y + math.sin(aa) * r * 1.6) * f)], fill=(255, 220, 110), width=10 * f)
    d.ellipse([(x - r) * f, (y - r) * f, (x + r) * f, (y + r) * f], fill=(255, 214, 80))


@lru_cache(maxsize=16)
def arka_plan(yer: str, tohum: int = 0) -> Image.Image:
    """Mekanın sabit arka planı (1280x1920, RGB)."""
    yer = yer if yer in YERLER else "cayir"
    rnd = random.Random(f"{yer}-{tohum}")
    f = 2
    img = Image.new("RGB", (GENIS * f, Y * f))
    d = ImageDraw.Draw(img)
    if yer == "gece":
        _gradyan(d, (24, 30, 78), (92, 70, 140), 0, ZEMIN, f, GENIS)
        d.ellipse([920 * f, 220 * f, 1080 * f, 380 * f], fill=(255, 246, 200))
        d.ellipse([960 * f, 200 * f, 1110 * f, 350 * f], fill=(40, 44, 96))  # hilal
        for _ in range(90):
            x, y, r = rnd.uniform(0, GENIS), rnd.uniform(0, 1100), rnd.uniform(1.5, 4)
            d.ellipse([(x - r) * f, (y - r) * f, (x + r) * f, (y + r) * f], fill=(255, 250, 220))
        _tepe(d, f, GENIS, 1180, 60, 260, 1.0, (48, 62, 110))
        _tepe(d, f, GENIS, 1330, 40, 200, 2.2, (40, 92, 86))
        d.rectangle([0, ZEMIN * f - 60 * f, GENIS * f, Y * f], fill=(34, 80, 72))
    elif yer == "oda":
        d.rectangle([0, 0, GENIS * f, 1240 * f], fill=(255, 222, 196))
        for x in range(0, GENIS, 80):  # duvar kağıdı çizgileri
            d.rectangle([x * f, 0, (x + 30) * f, 1240 * f], fill=(255, 230, 208))
        d.rounded_rectangle([140 * f, 300 * f, 560 * f, 780 * f], 24 * f, fill=(150, 205, 250), outline=(150, 100, 70), width=18 * f)
        d.line([(350 * f, 300 * f), (350 * f, 780 * f)], fill=(150, 100, 70), width=12 * f)
        d.line([(140 * f, 540 * f), (560 * f, 540 * f)], fill=(150, 100, 70), width=12 * f)
        d.ellipse([400 * f, 360 * f, 500 * f, 460 * f], fill=(255, 246, 200))
        d.rectangle([760 * f, 380 * f, 1020 * f, 600 * f], fill=(255, 255, 255), outline=(200, 140, 90), width=14 * f)
        _cicek(d, f, 890, 490, 34, (255, 120, 150))
        d.rectangle([700 * f, 860 * f, 1180 * f, 890 * f], fill=(170, 110, 70))
        for i, x in enumerate(range(720, 1150, 44)):
            renkler = [(240, 100, 100), (100, 160, 240), (250, 200, 80), (120, 200, 130), (190, 120, 220)]
            d.rectangle([x * f, (760 + (i % 3) * 14) * f, (x + 34) * f, 860 * f], fill=renkler[i % 5])
        d.rectangle([0, 1240 * f, GENIS * f, Y * f], fill=(196, 140, 96))
        for y in range(1240, Y, 70):
            d.line([(0, y * f), (GENIS * f, y * f)], fill=(176, 122, 82), width=4 * f)
        d.ellipse([200 * f, 1380 * f, 1080 * f, 1700 * f], fill=(120, 170, 230))
        d.ellipse([280 * f, 1420 * f, 1000 * f, 1660 * f], fill=(150, 196, 245))
    else:
        gok = {"kar": ((170, 210, 245), (232, 244, 255)), "sahil": ((110, 200, 250), (210, 240, 255)),
               "orman": ((150, 215, 240), (225, 245, 230))}.get(yer, ((120, 200, 250), (215, 240, 255)))
        _gradyan(d, gok[0], gok[1], 0, ZEMIN, f, GENIS)
        if yer != "orman":
            _gunes(d, f, 1000 if yer != "kar" else 220, 300, 90)
        if yer == "sahil":
            d.rectangle([0, 1020 * f, GENIS * f, 1320 * f], fill=(60, 150, 220))
            for y in range(1050, 1320, 50):
                for x in range(rnd.randint(-40, 0), GENIS, 140):
                    d.arc([x * f, y * f, (x + 70) * f, (y + 26) * f], 200, 340, fill=(200, 236, 255), width=5 * f)
            _tepe(d, f, GENIS, 1360, 18, 300, 0.4, (250, 222, 160))
            d.rectangle([0, ZEMIN * f - 40 * f, GENIS * f, Y * f], fill=(248, 216, 150))
            for _ in range(10):
                x, y = rnd.uniform(40, GENIS - 40), rnd.uniform(1560, 1880)
                d.ellipse([(x - 16) * f, (y - 10) * f, (x + 16) * f, (y + 10) * f], fill=(255, 190, 200))
            d.polygon([(80 * f, 1500 * f), (120 * f, 1400 * f), (160 * f, 1500 * f)], fill=(240, 190, 110))
            d.rectangle([60 * f, 1490 * f, 180 * f, 1560 * f], fill=(240, 196, 120))
        elif yer == "kar":
            _tepe(d, f, GENIS, 1150, 70, 280, 0.8, (214, 230, 248))
            for x in range(60, GENIS, 210):
                _cam(d, f, x + rnd.uniform(-30, 30), 1250 + rnd.uniform(-20, 20), rnd.uniform(260, 340), (70, 140, 110), True)
            _tepe(d, f, GENIS, 1360, 30, 220, 2.0, (238, 245, 255))
            d.rectangle([0, ZEMIN * f - 50 * f, GENIS * f, Y * f], fill=(246, 250, 255))
        elif yer == "orman":
            _tepe(d, f, GENIS, 1120, 50, 260, 0.3, (130, 196, 140))
            for x in range(-20, GENIS + 60, 120):
                _cam(d, f, x + rnd.uniform(-20, 20), 1260, rnd.uniform(380, 520), (70, 150, 100))
            for x in range(40, GENIS, 230):
                _agac(d, f, x + rnd.uniform(-30, 30), 1380, rnd.uniform(380, 460), (96, 180, 96))
            d.rectangle([0, 1360 * f, GENIS * f, Y * f], fill=(110, 186, 96))
            for _ in range(5):
                x, y = rnd.uniform(60, GENIS - 60), rnd.uniform(1560, 1850)
                d.rectangle([(x - 8) * f, (y - 20) * f, (x + 8) * f, y * f], fill=(250, 240, 220))
                d.chord([(x - 30) * f, (y - 50) * f, (x + 30) * f, (y - 6) * f], 180, 360, fill=(236, 80, 80))
        else:  # çayır, bahçe, gölet
            _tepe(d, f, GENIS, 1120, 70, 300, 0.5, (160, 220, 150))
            _tepe(d, f, GENIS, 1260, 45, 220, 2.1, (120, 200, 110))
            if yer != "bahce":
                _agac(d, f, 140, 1330, 520)
                _agac(d, f, 1150, 1300, 420, (100, 186, 100))
            d.rectangle([0, 1360 * f, GENIS * f, Y * f], fill=(124, 204, 104))
            if yer == "gol":
                d.ellipse([360 * f, 1560 * f, 1240 * f, 1860 * f], fill=(80, 170, 230))
                d.ellipse([420 * f, 1590 * f, 1180 * f, 1830 * f], fill=(104, 190, 240))
                for x, y in ((560, 1700), (900, 1760), (1060, 1660)):
                    d.pieslice([(x - 50) * f, (y - 22) * f, (x + 50) * f, (y + 22) * f], 30, 330, fill=(80, 170, 80))
                for x in (380, 410, 1220):
                    d.line([(x * f, 1600 * f), (x * f, 1430 * f)], fill=(90, 140, 60), width=8 * f)
                    d.ellipse([(x - 10) * f, 1420 * f, (x + 10) * f, 1480 * f], fill=(140, 90, 50))
            if yer == "bahce":
                for x in range(0, GENIS, 70):
                    d.rounded_rectangle([x * f, 1180 * f, (x + 48) * f, 1400 * f], 18 * f, fill=(255, 250, 240))
                d.rectangle([0, 1240 * f, GENIS * f, 1262 * f], fill=(240, 232, 220))
                d.rectangle([0, 1330 * f, GENIS * f, 1352 * f], fill=(240, 232, 220))
                for x in range(40, GENIS, 120):
                    d.line([(x * f, 1420 * f), (x * f, 1300 * f)], fill=(80, 160, 70), width=8 * f)
                    _cicek(d, f, x, 1290, 26, rnd.choice([(255, 120, 150), (190, 130, 240), (255, 160, 80), (120, 170, 255)]))
            for _ in range(26 if yer != "gol" else 12):
                x, y = rnd.uniform(20, GENIS - 20), rnd.uniform(1520, 1890)
                if yer == "gol" and 360 < x < 1240 and y > 1540:
                    continue
                _cicek(d, f, x, y, rnd.uniform(9, 15), rnd.choice([(255, 255, 255), (255, 150, 180), (255, 220, 90)]))
    return img.resize((GENIS, Y), Image.LANCZOS)


@lru_cache(maxsize=8)
def bulut(boyut: int, tohum: int) -> Image.Image:
    rnd = random.Random(tohum)
    img = Image.new("RGBA", (boyut * 2, int(boyut * 1.1)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for _ in range(6):
        r = rnd.uniform(0.25, 0.42) * boyut
        x = rnd.uniform(r, boyut * 2 - r)
        y = rnd.uniform(boyut * 0.5, boyut * 0.75)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 235))
    d.rounded_rectangle([boyut * 0.25, boyut * 0.6, boyut * 1.75, boyut * 1.0], boyut * 0.2, fill=(255, 255, 255, 235))
    return img.filter(ImageFilter.GaussianBlur(1.5))


class Canlandirici:
    """Bir sahnenin her karesinde arka planı ve küçük hareketleri hazırlar."""

    def __init__(self, yer: str, tohum: int, sure: float):
        self.yer = yer if yer in YERLER else "cayir"
        self.rnd = random.Random(tohum)
        self.arka = arka_plan(self.yer, tohum % 3)
        self.sure = max(sure, 0.1)
        self.yon = self.rnd.choice((-1, 1))
        r = self.rnd
        self.bulutlar = [(r.uniform(-200, GENIS), r.uniform(120, 620), r.uniform(10, 26), r.randint(90, 150),
                          r.randint(0, 9)) for _ in range(3)] if self.yer in BULUTLU else []
        self.yildizlar = [(r.uniform(0, G), r.uniform(0, 1100), r.uniform(0, 6.28)) for _ in range(28)] \
            if self.yer == "gece" else []
        self.kar = [(r.uniform(0, G), r.uniform(0, Y), r.uniform(60, 140), r.uniform(3, 8)) for _ in range(90)] \
            if self.yer == "kar" else []
        self.bocek = [(r.uniform(0, G), r.uniform(900, 1700), r.uniform(0, 6.28)) for _ in range(14)] \
            if self.yer in ("gece", "orman") else []
        self.kelebek = [(r.uniform(100, G - 100), r.uniform(800, 1200), r.uniform(0, 6.28),
                         r.choice([(255, 140, 190), (140, 180, 255), (255, 200, 90)])) for _ in range(3)] \
            if self.yer in ("bahce", "cayir") else []

    def kare(self, t: float) -> Image.Image:
        ilerleme = min(max(t / self.sure, 0.0), 1.0)
        kayma = (GENIS - G) * (0.5 + self.yon * (ilerleme - 0.5) * 0.9)
        img = self.arka.crop((int(kayma), 0, int(kayma) + G, Y))
        for x0, y0, hiz, boy, tohum in self.bulutlar:
            b = bulut(boy, tohum)
            x = int((x0 + hiz * t) % (GENIS + 400) - 300 - kayma * 0.3)
            img.paste(b, (x, int(y0)), b)
        d = ImageDraw.Draw(img)
        for x, y, faz in self.yildizlar:
            p = 0.5 + 0.5 * math.sin(t * 3 + faz)
            r = 3 + 5 * p
            d.line([(x - r, y), (x + r, y)], fill=(255, 250, 210), width=3)
            d.line([(x, y - r), (x, y + r)], fill=(255, 250, 210), width=3)
        for x, y, hiz, r in self.kar:
            yy = (y + hiz * t) % Y
            xx = x + 18 * math.sin(t + y)
            d.ellipse([xx - r, yy - r, xx + r, yy + r], fill=(255, 255, 255))
        for x, y, faz in self.bocek:
            p = 0.5 + 0.5 * math.sin(t * 2.4 + faz)
            xx, yy = x + 30 * math.sin(t * 0.7 + faz), y + 20 * math.cos(t * 0.9 + faz)
            r = 4 + 4 * p
            d.ellipse([xx - r * 2, yy - r * 2, xx + r * 2, yy + r * 2], fill=(120, 120, 60) if p < 0.3 else (190, 200, 110))
            d.ellipse([xx - r, yy - r, xx + r, yy + r], fill=(255, 250, 150))
        for x, y, faz, renk in self.kelebek:
            xx, yy = x + 120 * math.sin(t * 0.5 + faz), y + 50 * math.sin(t * 1.3 + faz)
            kanat = 14 + 10 * abs(math.sin(t * 12 + faz))
            d.ellipse([xx - kanat * 1.4, yy - 16, xx, yy + 8], fill=renk)
            d.ellipse([xx, yy - 16, xx + kanat * 1.4, yy + 8], fill=renk)
            d.line([(xx, yy - 14), (xx, yy + 12)], fill=(60, 40, 50), width=4)
        if self.yer in ("sahil", "gol"):
            for i in range(8):
                x = (i * 157 + t * 40) % G
                y = 1080 + i * 30 if self.yer == "sahil" else 1640 + (i % 4) * 40
                d.line([(x, y), (x + 40, y)], fill=(235, 250, 255), width=4)
        return img
