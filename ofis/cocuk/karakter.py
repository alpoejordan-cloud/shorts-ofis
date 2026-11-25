"""Karakter çizimi: sevimli hayvan karakterleri kodla (Pillow) çizilir.

Her karakter 320x420 birimlik bir tuvalde tanımlanır, 2 kat büyük çizilip küçültülür (yumuşak kenar).
Durumlar: ağız (kapalı/açık), göz (açık/kapalı), duygu (mutlu/saskin/uzgun/heyecanli).
Türler: tavsan, ayi, kedi, tilki, baykus, kurbaga, sincap, ordek, dino.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from PIL import Image, ImageDraw

TUVAL = (320, 420)
TURLER = ("tavsan", "ayi", "kedi", "tilki", "baykus", "kurbaga", "sincap", "ordek", "dino")
DUYGULAR = ("mutlu", "saskin", "uzgun", "heyecanli")

VARSAYILAN_RENK = {
    "tavsan": "#F4F1F8", "ayi": "#B07A4F", "kedi": "#9AA3B5", "tilki": "#F08A3C", "baykus": "#8E6CC9",
    "kurbaga": "#6CC56A", "sincap": "#C9814A", "ordek": "#FFD84D", "dino": "#7BC8A4",
}


def _hex(renk: str) -> tuple[int, int, int]:
    renk = renk.lstrip("#")
    return tuple(int(renk[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _ton(rgb: tuple[int, int, int], oran: float) -> tuple[int, int, int]:
    """oran > 1 açar (beyaza doğru), < 1 koyulaştırır."""
    if oran >= 1:
        return tuple(int(c + (255 - c) * (oran - 1)) for c in rgb)  # type: ignore[return-value]
    return tuple(int(c * oran) for c in rgb)  # type: ignore[return-value]


class _Kalem:
    """Birim koordinatlarla çizer; ölçek ve çizgi kalınlığını tek yerde tutar."""

    def __init__(self, ciz: ImageDraw.ImageDraw, f: float, cizgi: tuple[int, int, int]):
        self.d, self.f, self.cizgi = ciz, f, cizgi

    def _k(self, *xy: float) -> list[float]:
        return [v * self.f for v in xy]

    def elips(self, cx: float, cy: float, rx: float, ry: float, dolgu, kenar: bool = True, kalinlik: float = 3.2):
        self.d.ellipse(self._k(cx - rx, cy - ry, cx + rx, cy + ry), fill=dolgu,
                       outline=self.cizgi if kenar else None, width=max(1, int(kalinlik * self.f)) if kenar else 0)

    def cokgen(self, noktalar: list[tuple[float, float]], dolgu, kenar: bool = True, kalinlik: float = 3.2):
        nk = [(x * self.f, y * self.f) for x, y in noktalar]
        self.d.polygon(nk, fill=dolgu)
        if kenar:
            self.d.line(nk + [nk[0]], fill=self.cizgi, width=max(1, int(kalinlik * self.f)), joint="curve")

    def yay(self, cx: float, cy: float, rx: float, ry: float, bas: float, son: float, kalinlik: float = 4.0,
            renk=None):
        self.d.arc(self._k(cx - rx, cy - ry, cx + rx, cy + ry), bas, son, fill=renk or self.cizgi,
                   width=max(1, int(kalinlik * self.f)))

    def cizgi_ciz(self, noktalar: list[tuple[float, float]], kalinlik: float = 3.0, renk=None):
        self.d.line([(x * self.f, y * self.f) for x, y in noktalar], fill=renk or self.cizgi,
                    width=max(1, int(kalinlik * self.f)), joint="curve")


def _kulaklar(k: _Kalem, tur: str, ana, ic, acik):
    if tur == "tavsan":
        for x, egim in ((118, -14), (202, 14)):
            k.cokgen([(x - 22, 90), (x - 18 + egim, 12), (x + egim, -6 + 10), (x + 18 + egim, 12), (x + 22, 90)], ana)
            k.elips(x + egim * 0.45, 52, 10, 34, ic, kenar=False)
    elif tur in ("ayi", "sincap"):
        r = 26 if tur == "ayi" else 20
        for x in (88, 232):
            k.elips(x, 74, r, r, ana)
            k.elips(x, 76, r * 0.55, r * 0.55, ic, kenar=False)
    elif tur in ("kedi", "tilki", "baykus"):
        uc = {"kedi": 30, "tilki": 4, "baykus": 40}[tur]
        for yon in (-1, 1):
            dis = [(160 + 84 * yon, 120), (160 + 66 * yon, uc), (160 + 22 * yon, 72)]
            k.cokgen([(x, y) for x, y in dis], ana)
            if tur != "baykus":
                ic_uc = [(160 + 74 * yon, 104), (160 + 64 * yon, uc + 24), (160 + 38 * yon, 78)]
                k.cokgen(ic_uc, ic, kenar=False)
    elif tur == "dino":
        for i, x in enumerate((130, 160, 190)):
            h = 26 if i == 1 else 20
            k.cokgen([(x - 14, 60), (x, 60 - h - 10), (x + 14, 60)], acik)


def _kuyruk(k: _Kalem, tur: str, ana, acik):
    if tur == "tilki":
        k.cokgen([(220, 330), (290, 250), (312, 300), (300, 360), (250, 380)], ana)
        k.cokgen([(292, 262), (312, 300), (304, 330), (288, 300)], (255, 255, 255), kenar=False)
    elif tur == "sincap":
        k.elips(262, 270, 52, 92, ana)
        k.elips(266, 262, 30, 64, acik, kenar=False)
    elif tur == "dino":
        k.cokgen([(220, 340), (308, 372), (300, 392), (220, 392)], ana)
    elif tur == "kedi":
        k.cizgi_ciz([(222, 360), (268, 340), (290, 300), (282, 270)], kalinlik=13, renk=k.cizgi)
        k.cizgi_ciz([(222, 360), (268, 340), (290, 300), (282, 270)], kalinlik=8, renk=ana)
    elif tur == "tavsan":
        k.elips(232, 352, 20, 20, (255, 255, 255))


def _gozler(k: _Kalem, tur: str, acik_mi: bool, duygu: str, cizgi):
    y = 150 if tur not in ("kurbaga",) else 96
    xs = (122, 198) if tur != "kurbaga" else (104, 216)
    buyuk = 1.25 if tur in ("baykus", "kurbaga") else 1.0
    if tur == "baykus":
        for x in xs:
            k.elips(x, y, 38, 38, (255, 236, 180), kenar=True, kalinlik=2.5)
    for x in xs:
        if acik_mi:
            ry = 26 * buyuk * (1.12 if duygu == "saskin" else 1.0)
            k.elips(x, y, 21 * buyuk, ry, (255, 255, 255), kalinlik=2.6)
            py = y + (4 if duygu == "uzgun" else 3)
            k.elips(x + 2, py, 12 * buyuk, 15 * buyuk, (34, 30, 48), kenar=False)
            k.elips(x + 7, py - 7, 5 * buyuk, 5 * buyuk, (255, 255, 255), kenar=False)
            k.elips(x - 2, py + 6, 2.4 * buyuk, 2.4 * buyuk, (255, 255, 255), kenar=False)
        else:
            k.yay(x, y + 2, 19 * buyuk, 10, 200 if duygu != "uzgun" else 20, 340 if duygu != "uzgun" else 160,
                  kalinlik=5)
    # kaşlar duyguya göre
    if duygu in ("saskin", "uzgun", "heyecanli"):
        for x, yon in ((xs[0], -1), (xs[1], 1)):
            if duygu == "saskin":
                k.yay(x, y - 44, 16, 8, 200, 340, kalinlik=4.2)
            elif duygu == "uzgun":
                k.cizgi_ciz([(x - 16 * yon * -1 * -1, y - 30), (x + 14 * yon * -1, y - 40)], kalinlik=4.2)
            else:
                k.yay(x, y - 40, 16, 9, 210, 330, kalinlik=4.2)


def _agiz(k: _Kalem, tur: str, acik: bool, duygu: str):
    y = 200 if tur != "kurbaga" else 176
    koyu, dil = (92, 36, 50), (240, 120, 140)
    if tur in ("baykus", "ordek"):
        renk = (255, 170, 60)
        if acik:
            k.cokgen([(144, y - 22), (176, y - 22), (160, y - 2)], renk)
            k.cokgen([(146, y - 2), (174, y - 2), (160, y + 14)], _ton(renk, 0.8))
        else:
            k.cokgen([(142, y - 20), (178, y - 20), (160, y + 4)], renk)
        return
    if acik:
        ry = 22 if duygu in ("saskin", "heyecanli") else 17
        rx = 15 if duygu == "saskin" else 22
        k.elips(160, y + 6, rx, ry, koyu, kalinlik=2.6)
        k.elips(160, y + 6 + ry * 0.45, rx * 0.6, ry * 0.4, dil, kenar=False)
    elif duygu == "uzgun":
        k.yay(160, y + 18, 18, 12, 200, 340, kalinlik=4.5)
    elif duygu == "saskin":
        k.elips(160, y + 4, 8, 9, koyu, kalinlik=2.2)
    else:
        genis = 26 if tur == "kurbaga" else 20
        k.yay(160, y - 2, genis, 14, 20, 160, kalinlik=4.5)


def _burun_ve_agiz_bolgesi(k: _Kalem, tur: str, ana, acik):
    if tur in ("ayi", "tilki", "kedi", "sincap", "tavsan", "dino"):
        renk = (255, 255, 255) if tur == "tilki" else _ton(ana, 1.45)
        if tur in ("ayi", "sincap", "dino"):
            k.elips(160, 194, 42, 32, renk, kenar=False)
        elif tur == "tilki":
            k.elips(122, 200, 44, 34, renk, kenar=False)
            k.elips(198, 200, 44, 34, renk, kenar=False)
        if tur != "dino":
            k.elips(160, 180, 10, 7, (60, 40, 50), kenar=False)
    if tur == "kedi":
        for yon in (-1, 1):
            for dy in (-6, 6):
                k.cizgi_ciz([(160 + 30 * yon, 186 + dy * 0.4), (160 + 74 * yon, 180 + dy * 1.6)], kalinlik=2.2)


def _aksesuar(k: _Kalem, aksesuar: str | None, renk):
    if not aksesuar:
        return
    r = _hex(renk) if isinstance(renk, str) else renk
    if aksesuar == "atki":  # boyunda atkı
        k.cokgen([(92, 240), (228, 240), (232, 262), (88, 262)], r)
        k.cokgen([(190, 256), (214, 256), (222, 312), (196, 316)], r)
    elif aksesuar == "fiyonk":  # başta fiyonk
        k.cokgen([(196, 70), (236, 50), (236, 92)], r)
        k.cokgen([(196, 70), (160, 50), (160, 92)], r)
        k.elips(198, 70, 9, 9, _ton(r, 0.8))
    elif aksesuar == "sapka":  # küçük şapka
        k.elips(160, 64, 70, 12, r)
        k.cokgen([(116, 64), (124, 10), (196, 10), (204, 64)], r)
        k.cokgen([(118, 50), (202, 50), (204, 62), (116, 62)], (255, 255, 255), kenar=False)
    elif aksesuar == "gozluk":
        for x in (122, 198):
            k.yay(x, 150, 30, 30, 0, 360, kalinlik=4, renk=(40, 40, 60))
        k.cizgi_ciz([(152, 148), (168, 148)], kalinlik=4, renk=(40, 40, 60))


def _ciz(tur: str, renk: str, aksesuar: str | None, aksesuar_renk: str, agiz_acik: bool, goz_acik: bool,
         duygu: str, olcek: float) -> Image.Image:
    f = 2.0 * olcek
    G, Y = int(TUVAL[0] * f), int(TUVAL[1] * f)
    img = Image.new("RGBA", (G, Y), (0, 0, 0, 0))
    ana = _hex(renk)
    cizgi = _ton(ana, 0.45) if sum(ana) > 160 else (30, 24, 40)
    if tur == "tavsan" and sum(ana) > 690:
        cizgi = (120, 110, 140)
    k = _Kalem(ImageDraw.Draw(img), f, cizgi)
    acik, ic = _ton(ana, 1.5), (255, 182, 200)
    if tur in ("kurbaga", "dino", "ordek"):
        ic = _ton(ana, 1.3)

    _kuyruk(k, tur, ana, acik)
    # gövde, ayaklar, kollar
    k.elips(118, 398, 30, 16, _ton(ana, 0.92))
    k.elips(202, 398, 30, 16, _ton(ana, 0.92))
    k.elips(160, 322, 78, 80, ana)
    k.elips(160, 334, 48, 54, acik, kenar=False)
    if tur in ("baykus", "ordek"):
        k.elips(88, 316, 22, 46, _ton(ana, 0.85))
        k.elips(232, 316, 22, 46, _ton(ana, 0.85))
    else:
        k.elips(92, 300, 18, 30, ana)
        k.elips(228, 300, 18, 30, ana)
    _kulaklar(k, tur, ana, ic, acik)
    # baş
    if tur == "kurbaga":
        k.elips(160, 170, 112, 84, ana)
        for x in (104, 216):
            k.elips(x, 100, 40, 38, ana)
    else:
        k.elips(160, 160, 104, 96, ana)
    _burun_ve_agiz_bolgesi(k, tur, ana, acik)
    if tur == "baykus":
        k.elips(160, 200, 50, 40, _ton(ana, 1.35), kenar=False)
    _gozler(k, tur, goz_acik, duygu, cizgi)
    # yanaklar
    for x in (92, 228):
        k.elips(x, 196 if tur != "kurbaga" else 168, 16, 10, (255, 150, 170), kenar=False)
    _agiz(k, tur, agiz_acik, duygu)
    _aksesuar(k, aksesuar, aksesuar_renk)
    return img.resize((G // 2, Y // 2), Image.LANCZOS)


@lru_cache(maxsize=512)
def _cizim_onbellek(tur: str, renk: str, aksesuar: str | None, aksesuar_renk: str, agiz_acik: bool,
                    goz_acik: bool, duygu: str, olcek: float) -> Image.Image:
    return _ciz(tur, renk, aksesuar, aksesuar_renk, agiz_acik, goz_acik, duygu, olcek)


def sprite(kar: dict[str, Any], agiz_acik: bool = False, goz_acik: bool = True, duygu: str = "mutlu",
           olcek: float = 1.0) -> Image.Image:
    """Karakterin bir durumdaki görüntüsü (RGBA). Aynı durum bir kez çizilir, sonra önbellekten gelir."""
    tur = kar.get("tur", "ayi")
    if tur not in TURLER:
        tur = "ayi"
    duygu = duygu if duygu in DUYGULAR else "mutlu"
    return _cizim_onbellek(tur, kar.get("renk") or VARSAYILAN_RENK[tur], kar.get("aksesuar"),
                           kar.get("aksesuar_renk", "#E84A5F"), agiz_acik, goz_acik, duygu, round(olcek, 2))


def ayak_hizasi(olcek: float = 1.0) -> int:
    """Sprite içinde ayakların alt kenarının y konumu (zemine oturtmak için)."""
    return int(414 * olcek)
