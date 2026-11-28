"""Hareketli grafik (motion graphics): fotoğraf/stok görüntü yerine videoyu tamamen kendimiz çizeriz.

Neden (2026-11-28 analizi): stok/CC fotoğraf slaytı + yapay ses izleyiciye "tekrar kullanılmış içerik" gibi görünür,
ilk saniyede kaydırılır ve YouTube İş Ortağı Programı'nda "reused content" reddi riski taşır. Burada her kare kodla
üretilir (0 TL, internet gerekmez, telif riski yok):

- Her anlatım cümlesi kendi sahnesi olur; sahne cümlenin söylendiği anda başlar (ses ile senkron).
- İlk cümle "kanca" sahnesi: beyaz flaş + büyük ikon + sarsıntılı anahtar kelime.
- Sayı geçen cümle: sayı sıfırdan hızla sayarak büyür ("$15,000", "39 MILLION").
- Diğer cümleler: konuya uygun vektör ikon (çip, kilit, para, araba, oyun kolu, harita iğnesi...) zıplayarak gelir,
  anahtar kelime kartları sırayla kayar. Yorum cümlesi "MY TAKE" balonu, soru cümlesi büyük "?" olur.
- Arka plan kanalın temasıyla canlıdır: Tech için devre/ızgara + parçacıklar, GTA için gün batımı neon şehir,
  palmiyeler ve kayan retro ızgara zemin.

Ekran düzeni altyazı ve kancayla çakışmaz: üstte kanca (y<460), ortada grafik (y 480-1150), altta altyazı (y~1250).
"""
from __future__ import annotations

import math
import random
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .cekirdek import gunluk_al

log = gunluk_al("hareketli")
G, Y, FPS = 1080, 1920, 30
MERKEZ_Y = 740          # ana grafiğin merkezi
KART_Y = 1100           # anahtar kelime kartlarının merkezi

YAZI_TIPLERI = ["C:/Windows/Fonts/ariblk.ttf", "C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]

TEMALAR: dict[str, dict[str, Any]] = {
    "devre": {  # Tech in 30
        "ust": (6, 12, 34), "alt": (14, 44, 92), "vurgu": (0, 229, 255), "vurgu2": (255, 214, 0),
        "ikon": (0, 229, 255), "ikon2": (124, 77, 255), "kart": (255, 214, 0), "kart_yazi": (10, 14, 30),
        "parcacik": (0, 229, 255),
    },
    "neon_sehir": {  # Open World Insider
        "ust": (32, 8, 64), "orta": (196, 44, 128), "alt": (255, 140, 60), "vurgu": (255, 64, 160),
        "vurgu2": (255, 214, 0), "ikon": (255, 230, 90), "ikon2": (255, 64, 160), "kart": (255, 64, 160),
        "kart_yazi": (255, 255, 255), "parcacik": (255, 200, 120),
    },
}

IKON_KELIMELERI: dict[str, tuple[str, ...]] = {
    "yasak": ("ban", "banned", "bans", "block", "blocked", "halt", "stop", "stops", "illegal", "forbid"),
    "kilit": ("privacy", "private", "password", "passwords", "hack", "hacked", "hackers", "breach", "security",
              "leak", "leaked", "encrypt", "secure", "cyber", "cybersecurity"),
    "uyari": ("warn", "warns", "warning", "risk", "risks", "danger", "dangerous", "fear", "attack", "attacks",
              "threat", "scam", "fraud", "explicit", "fire", "fail", "fails", "unreliable"),
    "kalkan": ("law", "laws", "fda", "approval", "approves", "approved", "court", "fcc", "regulators",
               "regulation", "rules", "safety", "safe", "protect"),
    "bina": ("government", "agency", "state", "senate", "congress", "company", "companies", "ceo", "office"),
    "para": ("$", "price", "prices", "money", "sales", "sold", "fine", "fines", "cost", "costs", "dollar",
             "dollars", "crypto", "steal", "stole", "auction", "deal", "pay", "paid", "cash", "memecoin"),
    "roket": ("spacex", "space", "launch", "rocket", "satellite", "orbit", "nasa"),
    "araba": ("car", "cars", "robotaxi", "robotaxis", "driverless", "uber", "tesla", "vehicle", "vehicles",
              "infernus", "drive", "driving"),
    "telefon": ("phone", "phones", "app", "apps", "iphone", "android", "whatsapp", "smartphone", "mobile"),
    "sohbet": ("chat", "chats", "chatbot", "chatbots", "talk", "talks", "message", "messages", "voice"),
    "gamepad": ("game", "games", "gta", "playstation", "ps5", "xbox", "player", "players", "gaming", "npc",
                "npcs", "rockstar", "gamers", "playtime", "console"),
    "pin": ("where", "location", "map", "city", "vice", "florida", "find", "spot", "parking", "lot", "floor"),
    "grafik": ("record", "records", "milestone", "growth", "grow", "million", "billion", "percent", "%",
               "increasing", "rise", "highest", "biggest", "numbers", "stats"),
    "cip": ("ai", "model", "models", "gpt", "openai", "anthropic", "gemini", "neural", "robot", "robots",
            "algorithm", "data", "neuralink", "brain", "computer", "tech", "technology", "assistants"),
}

DURAK = set("""a an the and or but so to of in on at by for with from into about as is are was were be been being
it its this that these those you your yours we our they their them he she his her i me my mine just now new also
than then there here what who how why when where which will would can could should has have had do does did not
no yes very really more most some any all every one two get got make makes made like even only over under out up
down off again still big huge major real fake says said say see look much many may might must let lets im it's
that's there's here's don't doesn't can't won't""".split())


# ---------------------------------------------------------------- yardımcılar
@lru_cache(maxsize=32)
def yazi_tipi(boyut: int) -> ImageFont.FreeTypeFont:
    for yol in YAZI_TIPLERI:
        if Path(yol).exists():
            return ImageFont.truetype(yol, boyut)
    return ImageFont.load_default(boyut)


def tema(k: dict[str, Any]) -> dict[str, Any]:
    ad = k.get("hareketli_tema") or ("neon_sehir" if "gta" in str(k.get("id", "")) else "devre")
    return {"ad": ad, **TEMALAR.get(ad, TEMALAR["devre"])}


def _kolay(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def _zipla(x: float) -> float:
    """0->1 arası 'pop' eğrisi: hedefi biraz aşar ve yerine oturur."""
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.9, 2.9
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def _sade(kelime: str) -> str:
    return re.sub(r"[^\w$%'.-]", "", kelime.lower()).strip(".'-")


# ---------------------------------------------------------------- metin çözümleme
def metni_onar(metin: str) -> str:
    """Konuşma tanıma sayıları böler ("$15 ,000", "17 .4", "70 %"): ekranda tek parça olsun."""
    metin = re.sub(r"(\d)\s+([,.]\d)", r"\1\2", metin)
    metin = re.sub(r"(\d)\s+%", r"\1%", metin)
    metin = re.sub(r"([$€£])\s+(\d)", r"\1\2", metin)
    return re.sub(r"\s+", " ", metin).strip()


def cumleler(kelime_zamanlari: list[dict[str, Any]], senaryo: str, toplam: float) -> list[dict[str, Any]]:
    """Kelime zamanlarından cümle aralıkları. Zaman yoksa senaryo cümleleri kelime sayısıyla orantılı dağıtılır."""
    sonuc: list[dict[str, Any]] = []
    if kelime_zamanlari:
        aktif: list[dict[str, Any]] = []
        for w in kelime_zamanlari:
            aktif.append(w)
            if str(w.get("kelime", "")).strip().endswith((".", "!", "?")):
                sonuc.append({"metin": " ".join(str(x["kelime"]).strip() for x in aktif),
                              "bas": float(aktif[0]["bas"]), "son": float(aktif[-1]["son"])})
                aktif = []
        if aktif:
            sonuc.append({"metin": " ".join(str(x["kelime"]).strip() for x in aktif),
                          "bas": float(aktif[0]["bas"]), "son": float(aktif[-1]["son"])})
    for c in sonuc:
        c["metin"] = metni_onar(c["metin"])
    if len(sonuc) < 2:  # zaman yok ya da noktalama gelmedi
        parcalar = [c.strip() for c in re.split(r"(?<=[.!?])\s+", senaryo or "") if c.strip()] or [senaryo or ""]
        sayilar = [max(len(c.split()), 1) for c in parcalar]
        t, sonuc = 0.0, []
        for c, n in zip(parcalar, sayilar):
            d = toplam * n / sum(sayilar)
            sonuc.append({"metin": c, "bas": t, "son": t + d})
            t += d
    # boşluk kalmasın: her sahne bir sonrakinin başına kadar sürer, ilki 0'dan başlar, sonuncusu sona kadar
    sonuc[0]["bas"] = 0.0
    for a, b in zip(sonuc, sonuc[1:]):
        a["son"] = b["bas"]
    sonuc[-1]["son"] = max(toplam, sonuc[-1]["son"])
    # çok kısa sahneleri (< 1,2 sn) bir öncekine kat: göz yorulmasın
    birlesik: list[dict[str, Any]] = []
    for c in sonuc:
        if birlesik and c["son"] - c["bas"] < 1.2:
            birlesik[-1] = {**birlesik[-1], "metin": birlesik[-1]["metin"] + " " + c["metin"], "son": c["son"]}
        else:
            birlesik.append(dict(c))
    return birlesik


SAYI_RE = re.compile(r"(\$|€|£)?(\d[\d,]*(?:\.\d+)?)\s?(%|percent|million|billion|thousand|trillion|k\b|m\b|bn\b|"
                     r"hours|hour|days|years|players|users|accounts|tracks|times|x\b)?", re.I)


def sayi_bul(metin: str) -> dict[str, Any] | None:
    """Cümledeki ilk anlamlı sayı: {'on': '$', 'deger': 15000.0, 'ondalik': 0, 'son': '', 'etiket': 'DAILY FINES'}."""
    for m in SAYI_RE.finditer(metin):
        ham = m.group(2).replace(",", "")
        try:
            deger = float(ham)
        except ValueError:
            continue
        if not m.group(1) and not m.group(3) and (1900 <= deger <= 2100 or deger < 100):
            continue  # yıl ("2026") ya da "GTA 6" gibi ad içindeki küçük sayı sayaç olmaz
        if deger == 0:
            continue
        son = (m.group(3) or "").lower()
        son = {"percent": "%", "k": "K", "m": " MILLION", "bn": " BILLION"}.get(son, (" " + son.upper()) if son and son != "%" else son)
        sonrasi = [w for w in re.findall(r"[A-Za-z][\w'-]*", metin[m.end():]) if w.lower() not in DURAK][:2]
        return {"on": m.group(1) or "", "deger": deger, "ondalik": len(ham.split(".")[1]) if "." in ham else 0,
                "son": son, "etiket": " ".join(sonrasi).upper()}
    return None


def anahtar_kelimeler(metin: str, adet: int = 2) -> list[str]:
    """Ekranda kart olacak kelimeler: önce özel isimler/kısaltmalar, sonra ikon kelimeleri, sonra uzun kelimeler."""
    ham = re.findall(r"[A-Za-z0-9][\w'.&-]*", metin)
    sozler: list[str] = []
    for n, w in enumerate(ham):  # "New York", "Max Verstappen": art arda büyük harfli kelimeler tek kart
        if (sozler and w[:1].isupper() and sozler[-1][:1].isupper() and len(sozler[-1].split()) < 2
                and w.lower() not in DURAK and (n > 1 or sozler[-1].lower() in ("new", "big"))):
            sozler[-1] += " " + w
        else:
            sozler.append(w)
    adaylar: list[tuple[int, int, str]] = []
    for n, w in enumerate(sozler):
        temiz = w.strip(".'-")
        if temiz.lower().endswith("'s"):
            temiz = temiz[:-2]
        alt = temiz.lower()
        if alt in DURAK or len(temiz) < 2:
            continue
        puan = 0
        if " " in temiz:  # "New York", "Max Verstappen"
            puan += 5
        elif n > 0 and temiz[:1].isupper():
            puan += 3
        if temiz.isupper() and len(temiz) > 1:
            puan += 3
        if any(c.isdigit() for c in temiz):
            puan += 2
        if any(alt in v for v in IKON_KELIMELERI.values()):
            puan += 2
        puan += min(len(temiz), 10) // 4
        adaylar.append((puan, -n, temiz))
    secilen: list[str] = []
    for _, _, w in sorted(adaylar, reverse=True):
        if not any(w.upper() in s.upper() or s.upper() in w.upper() for s in secilen):
            secilen.append(w)
        if len(secilen) >= adet:
            break
    sira = {w: metin.find(w) for w in secilen}  # okunma sırası
    return [w.upper() for w in sorted(secilen, key=lambda x: sira[x])]


def ikon_sec(metin: str, varsayilan: str = "cip", haric: tuple[str, ...] = ()) -> str:
    sozler = [_sade(w) for w in metin.split()]
    if "$" in metin:
        sozler.append("$")
    puan = {ad: sum(s in kel for s in sozler) for ad, kel in IKON_KELIMELERI.items() if ad not in haric}
    en_iyi = max(puan, key=lambda a: (puan[a], -list(IKON_KELIMELERI).index(a)))
    return en_iyi if puan[en_iyi] else varsayilan


YEDEK_IKONLAR = {"neon_sehir": ["yildiz", "grafik", "gamepad"],  # konuya uyan ikon yoksa genel ve nötr olanlar
                 "devre": ["cip", "grafik", "yildiz"]}


def sahne_turu(metin: str, sira: int) -> str:
    alt = metin.lower()
    if sira == 0:
        return "kanca"
    if re.search(r"\b(i think|in my opinion|my take|i believe|honestly|i'd say)\b", alt):
        return "yorum"
    if sayi_bul(metin):
        return "sayi"
    if metin.strip().endswith("?"):
        return "soru"
    return "ikon"


def plan_cikar(kelime_zamanlari: list[dict[str, Any]], senaryo: str, toplam: float,
               k: dict[str, Any]) -> list[dict[str, Any]]:
    yedek = YEDEK_IKONLAR.get(tema(k)["ad"], YEDEK_IKONLAR["devre"])
    plan = []
    son_ikon = None
    for n, c in enumerate(cumleler(kelime_zamanlari, senaryo, toplam)):
        tur = sahne_turu(c["metin"], n)
        varsayilan = next(y for y in yedek[n % len(yedek):] + yedek if y != son_ikon)
        ikon = ikon_sec(c["metin"], varsayilan)
        if ikon == son_ikon:  # aynı ikon art arda gelmesin: ikinci en uygun ya da sıradaki yedek
            ikon = ikon_sec(c["metin"], varsayilan, haric=(ikon,))
        son_ikon = ikon
        plan.append({**c, "tur": tur, "ikon": ikon, "kelimeler": anahtar_kelimeler(c["metin"], 2),
                     "sayi": sayi_bul(c["metin"]) if tur in ("sayi", "kanca") else None})
    return plan


# ---------------------------------------------------------------- ikonlar (kodla çizilir)
def ikon_ciz(ad: str, renk: tuple, renk2: tuple, boyut: int = 460) -> Image.Image:
    """Tek renk düz (flat) ikon; kalın kontur ve yumuşak parıltıyla. Tamamen kodla çizilir."""
    s = boyut
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    koyu = (12, 14, 30, 255)
    r, r2 = (*renk, 255), (*renk2, 255)
    k = s / 100  # 100 birimlik çizim ızgarası

    def P(*xy):
        return [v * k for v in xy]

    if ad == "cip":
        d.rounded_rectangle(P(22, 22, 78, 78), radius=8 * k, fill=r, outline=koyu, width=int(3 * k))
        for i in range(4):
            x = 30 + i * 13
            for (x0, y0, x1, y1) in ((x, 10, x + 6, 22), (x, 78, x + 6, 90), (10, x, 22, x + 6), (78, x, 90, x + 6)):
                d.rounded_rectangle(P(x0, y0, x1, y1), radius=1.5 * k, fill=r2)
        d.rounded_rectangle(P(34, 34, 66, 66), radius=5 * k, fill=koyu)
        f = yazi_tipi(int(20 * k))
        d.text((50 * k, 50 * k), "AI", font=f, fill=r, anchor="mm")
    elif ad == "kilit":
        d.arc(P(28, 8, 72, 56), 180, 360, fill=r2, width=int(10 * k))
        d.line(P(33, 32, 33, 46), fill=r2, width=int(10 * k))
        d.line(P(67, 32, 67, 46), fill=r2, width=int(10 * k))
        d.rounded_rectangle(P(18, 42, 82, 92), radius=10 * k, fill=r, outline=koyu, width=int(3 * k))
        d.ellipse(P(43, 55, 57, 69), fill=koyu)
        d.polygon(P(46, 66, 54, 66, 56, 82, 44, 82), fill=koyu)
    elif ad == "yasak":
        d.ellipse(P(8, 8, 92, 92), outline=(255, 70, 70, 255), width=int(12 * k))
        d.line(P(22, 78, 78, 22), fill=(255, 70, 70, 255), width=int(12 * k))
    elif ad == "uyari":
        d.polygon(P(50, 6, 95, 88, 5, 88), fill=r2 if renk2 != renk else r, outline=koyu)
        d.polygon(P(50, 18, 85, 82, 15, 82), fill=(255, 214, 0, 255))
        d.rounded_rectangle(P(45, 34, 55, 64), radius=4 * k, fill=koyu)
        d.ellipse(P(44, 68, 56, 80), fill=koyu)
    elif ad == "kalkan":
        d.polygon(P(50, 4, 90, 18, 86, 56, 50, 96, 14, 56, 10, 18), fill=r, outline=koyu)
        d.polygon(P(50, 14, 80, 24, 77, 54, 50, 86, 23, 54, 20, 24), fill=r2)
        d.line(P(32, 50, 46, 64, 70, 36), fill=(255, 255, 255, 255), width=int(9 * k), joint="curve")
    elif ad == "bina":
        d.polygon(P(50, 6, 94, 30, 6, 30), fill=r)
        d.rectangle(P(10, 30, 90, 38), fill=r2)
        for x in (16, 34, 52, 70):
            d.rectangle(P(x, 40, x + 12, 80), fill=r)
        d.rectangle(P(6, 82, 94, 94), fill=r2)
    elif ad == "para":
        d.ellipse(P(6, 6, 94, 94), fill=(255, 200, 40, 255), outline=koyu, width=int(3 * k))
        d.ellipse(P(16, 16, 84, 84), outline=(255, 236, 140, 255), width=int(4 * k))
        f = yazi_tipi(int(56 * k))
        d.text((50 * k, 52 * k), "$", font=f, fill=(120, 70, 0, 255), anchor="mm")
    elif ad == "roket":
        d.polygon(P(50, 2, 66, 26, 66, 70, 34, 70, 34, 26), fill=(240, 240, 255, 255), outline=koyu)
        d.polygon(P(34, 48, 18, 74, 34, 70), fill=r2)
        d.polygon(P(66, 48, 82, 74, 66, 70), fill=r2)
        d.ellipse(P(42, 28, 58, 44), fill=r, outline=koyu, width=int(2 * k))
        d.polygon(P(38, 72, 62, 72, 50, 98), fill=(255, 140, 40, 255))
        d.polygon(P(44, 72, 56, 72, 50, 88), fill=(255, 230, 90, 255))
    elif ad == "araba":
        d.polygon(P(26, 40, 36, 22, 66, 22, 78, 40), fill=r2)
        d.rounded_rectangle(P(6, 38, 94, 70), radius=10 * k, fill=r, outline=koyu, width=int(3 * k))
        d.polygon(P(32, 38, 39, 26, 49, 26, 49, 38), fill=(190, 230, 255, 255))
        d.polygon(P(53, 38, 53, 26, 63, 26, 71, 38), fill=(190, 230, 255, 255))
        for x in (24, 76):
            d.ellipse(P(x - 12, 58, x + 12, 82), fill=koyu)
            d.ellipse(P(x - 5, 65, x + 5, 75), fill=(200, 200, 210, 255))
        d.ellipse(P(84, 46, 92, 54), fill=(255, 240, 150, 255))
    elif ad == "telefon":
        d.rounded_rectangle(P(26, 4, 74, 96), radius=10 * k, fill=koyu, outline=r, width=int(4 * k))
        d.rounded_rectangle(P(31, 12, 69, 86), radius=5 * k, fill=r)
        d.rounded_rectangle(P(43, 6, 57, 10), radius=2 * k, fill=r2)
        for i, y in enumerate((22, 40, 58)):
            d.rounded_rectangle(P(35, y, 65 - i * 6, y + 10), radius=4 * k, fill=(255, 255, 255, 230))
    elif ad == "sohbet":
        d.rounded_rectangle(P(6, 10, 94, 70), radius=18 * k, fill=r, outline=koyu, width=int(3 * k))
        d.polygon(P(22, 66, 40, 66, 18, 90), fill=r)
        for x in (30, 50, 70):
            d.ellipse(P(x - 7, 33, x + 7, 47), fill=koyu)
    elif ad == "gamepad":
        d.rounded_rectangle(P(6, 28, 94, 72), radius=20 * k, fill=r, outline=koyu, width=int(3 * k))
        d.ellipse(P(2, 44, 34, 90), fill=r)
        d.ellipse(P(66, 44, 98, 90), fill=r)
        d.rectangle(P(20, 44, 28, 64), fill=koyu)
        d.rectangle(P(14, 50, 34, 58), fill=koyu)
        for (x, y, c) in ((72, 44, r2), (82, 52, (80, 220, 120, 255)), (72, 60, (255, 90, 90, 255)),
                          (62, 52, (90, 170, 255, 255))):
            d.ellipse(P(x - 5, y - 5, x + 5, y + 5), fill=c)
    elif ad == "pin":
        d.polygon(P(20, 42, 80, 42, 50, 96), fill=r2)
        d.ellipse(P(18, 6, 82, 70), fill=r2)
        d.ellipse(P(36, 22, 64, 50), fill=(255, 255, 255, 255))
        d.ellipse(P(30, 90, 70, 98), fill=(0, 0, 0, 90))
    elif ad == "grafik":
        for i, (h, c) in enumerate(((30, r2), (50, r), (68, r2), (88, r))):
            x = 10 + i * 21
            d.rounded_rectangle(P(x, 96 - h, x + 16, 96), radius=3 * k, fill=c, outline=koyu, width=int(2 * k))
        d.line(P(12, 70, 34, 52, 54, 58, 86, 14), fill=(255, 255, 255, 255), width=int(5 * k), joint="curve")
        d.polygon(P(86, 6, 94, 22, 78, 20), fill=(255, 255, 255, 255))
    else:  # yildiz
        noktalar = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rr = 46 if i % 2 == 0 else 20
            noktalar += [50 + rr * math.cos(a), 52 + rr * math.sin(a)]
        d.polygon(P(*noktalar), fill=r, outline=koyu)
    # parıltı: ikonun bulanık kopyası arkaya
    parilti = img.filter(ImageFilter.GaussianBlur(boyut / 22))
    alfa = parilti.getchannel("A").point(lambda v: int(v * 0.8))
    parilti.putalpha(alfa)
    sonuc = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sonuc.alpha_composite(parilti)
    sonuc.alpha_composite(img)
    return sonuc


def kart_ciz(metin: str, zemin: tuple, yazi: tuple, boyut: int = 92) -> Image.Image:
    f = yazi_tipi(boyut)
    x0, y0, x1, y1 = f.getbbox(metin)
    en, boy = x1 - x0 + 64, y1 - y0 + 44
    img = Image.new("RGBA", (en + 16, boy + 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([10, 12, en + 10, boy + 12], radius=22, fill=(0, 0, 0, 150))  # gölge
    d.rounded_rectangle([2, 2, en, boy], radius=22, fill=(*zemin, 255))
    d.text((32 - x0, 22 - y0), metin, font=f, fill=(*yazi, 255))
    return img


def buyuk_yazi(metin: str, renk: tuple, boyut: int, kontur: int = 10) -> Image.Image:
    f = yazi_tipi(boyut)
    x0, y0, x1, y1 = f.getbbox(metin, stroke_width=kontur)
    img = Image.new("RGBA", (x1 - x0 + 20, y1 - y0 + 20), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((10 - x0, 10 - y0), metin, font=f, fill=(*renk, 255), stroke_width=kontur,
                             stroke_fill=(10, 10, 20, 255))
    return img


def _sigdir(img: Image.Image, en_fazla: int) -> Image.Image:
    if img.width <= en_fazla:
        return img
    o = en_fazla / img.width
    return img.resize((en_fazla, max(1, int(img.height * o))), Image.LANCZOS)


# ---------------------------------------------------------------- arka planlar
def _dikey_gradyan(renkler: list[tuple], en: int, boy: int) -> np.ndarray:
    t = np.linspace(0, 1, boy)[:, None]
    duraklar = np.linspace(0, 1, len(renkler))
    kanallar = [np.interp(t, duraklar, [c[i] for c in renkler]) for i in range(3)]
    return np.repeat(np.concatenate(kanallar, axis=1)[:, None, :], en, axis=1).astype(np.float32)


@lru_cache(maxsize=4)
def arka_plan_taban(ad: str) -> np.ndarray:
    """Taban görüntü (uint8, Y+400 yüksekliğinde: yavaş dikey kayma için pay)."""
    tm = TEMALAR[ad]
    boy = Y + 400
    if ad == "neon_sehir":
        dizi = _dikey_gradyan([tm["ust"], (88, 20, 110), tm["orta"], tm["alt"]], G, boy)
        img = Image.fromarray(dizi.astype(np.uint8)).convert("RGBA")
        d = ImageDraw.Draw(img)
        ufuk = int(boy * 0.70)
        # çizgili retro güneş
        gx, gy, gr = G // 2, ufuk - 150, 330
        gunes = Image.new("RGBA", (gr * 2, gr * 2), (0, 0, 0, 0))
        gd = ImageDraw.Draw(gunes)
        for i in range(gr * 2):
            t = i / (gr * 2)
            c = (255, int(230 - 120 * t), int(90 + 40 * t), 255)
            gd.line([(0, i), (gr * 2, i)], fill=c)
        maske = Image.new("L", (gr * 2, gr * 2), 0)
        md = ImageDraw.Draw(maske)
        md.ellipse([0, 0, gr * 2 - 1, gr * 2 - 1], fill=255)
        for j in range(7):  # alt yarıda yatay boşluklar
            yy = gr + 30 + j * 44
            md.rectangle([0, yy, gr * 2, yy + 8 + j * 3], fill=0)
        img.paste(gunes, (gx - gr, gy - gr), maske)
        # şehir silueti
        rnd = random.Random(7)
        x = 0
        while x < G:
            en = rnd.randint(50, 120)
            yuk = rnd.randint(120, 420)
            d.rectangle([x, ufuk - yuk, x + en, ufuk], fill=(40, 10, 60, 255))
            for wy in range(ufuk - yuk + 20, ufuk - 10, 34):
                for wx in range(x + 10, x + en - 10, 22):
                    if rnd.random() < 0.35:
                        d.rectangle([wx, wy, wx + 8, wy + 12], fill=(255, 200, 120, 200))
            x += en + rnd.randint(0, 12)
        # palmiyeler
        for px, ph, yon in ((90, 640, 1), (980, 720, -1), (840, 520, -1)):
            taban = ufuk + 40
            d.line([(px, taban), (px + yon * 40, taban - ph)], fill=(20, 4, 30, 255), width=22)
            tx, ty = px + yon * 40, taban - ph
            for a in range(0, 360, 40):
                rad = math.radians(a)
                uc = (tx + 190 * math.cos(rad), ty + 90 * math.sin(rad) + 40)
                d.line([(tx, ty), ((tx + uc[0]) / 2, ty - 30), uc], fill=(20, 4, 30, 255), width=20, joint="curve")
        d.rectangle([0, ufuk, G, boy], fill=(24, 6, 40, 255))
        return np.array(img.convert("RGB"))
    # devre (teknoloji)
    dizi = _dikey_gradyan([tm["ust"], (10, 24, 60), tm["alt"]], G, boy)
    img = Image.fromarray(dizi.astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img)
    for x in range(0, G, 60):
        for y in range(0, boy, 60):
            d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(60, 120, 200, 140))
    rnd = random.Random(3)
    for _ in range(40):  # devre yolları
        x, y = rnd.randrange(0, G, 60), rnd.randrange(0, boy, 60)
        nokta = [(x, y)]
        for _ in range(rnd.randint(2, 5)):
            if rnd.random() < 0.5:
                x += rnd.choice((-1, 1)) * 60 * rnd.randint(1, 4)
            else:
                y += rnd.choice((-1, 1)) * 60 * rnd.randint(1, 4)
            nokta.append((x, y))
        d.line(nokta, fill=(0, 150, 220, 110), width=4)
        d.ellipse([x - 7, y - 7, x + 7, y + 7], outline=(0, 200, 255, 170), width=3)
    return np.array(img.convert("RGB"))


class ArkaPlan:
    def __init__(self, ad: str, tohum: str):
        self.ad = ad
        self.taban = arka_plan_taban(ad)
        rnd = random.Random(tohum)
        self.parcacik = [(rnd.uniform(0, G), rnd.uniform(0, Y), rnd.uniform(2, 7), rnd.uniform(20, 90),
                          rnd.uniform(0, math.tau)) for _ in range(46)]
        self.renk = TEMALAR[ad]["parcacik"]

    def kare(self, t: float) -> Image.Image:
        kayma = int(200 + 160 * math.sin(t * 0.25))
        img = Image.fromarray(self.taban[kayma: kayma + Y]).convert("RGBA")
        d = ImageDraw.Draw(img, "RGBA")
        if self.ad == "neon_sehir":  # kayan retro ızgara zemin
            ufuk = int((Y + 400) * 0.70) - kayma + 40
            for i in range(14):
                z = ((i + (t * 1.6) % 1) / 14) ** 2
                y = ufuk + z * (Y - ufuk)
                if ufuk < y < Y:
                    d.line([(0, y), (G, y)], fill=(255, 64, 160, int(60 + 160 * z)), width=3)
            for i in range(-8, 9):
                d.line([(G / 2 + i * 40, ufuk), (G / 2 + i * 260, Y)], fill=(255, 64, 160, 120), width=3)
        else:  # tarama çizgisi
            ty = (t * 380) % (Y + 300) - 150
            d.rectangle([0, ty, G, ty + 6], fill=(0, 229, 255, 60))
        for (x, y, r, hiz, faz) in self.parcacik:
            yy = (y - t * hiz) % Y
            xx = x + 18 * math.sin(t * 0.8 + faz)
            a = int(90 + 80 * math.sin(t * 2 + faz))
            d.ellipse([xx - r, yy - r, xx + r, yy + r], fill=(*self.renk, max(a, 0)))
        return img


# ---------------------------------------------------------------- sahne çizimi
class Sahne:
    def __init__(self, s: dict[str, Any], tm: dict[str, Any], kanca: str = ""):
        self.s, self.tm = s, tm
        self.sure = max(float(s["son"]) - float(s["bas"]), 0.5)
        self.ikon = ikon_ciz(s["ikon"], tm["ikon"], tm["ikon2"], 460 if s["tur"] != "kanca" else 400)
        kelimeler = list(s.get("kelimeler") or [])
        self.kartlar = [_sigdir(kart_ciz(w, tm["kart"], tm["kart_yazi"], 86), G - 120) for w in kelimeler[:2]]
        self.sayi = s.get("sayi")
        self.soru = buyuk_yazi("?", tm["vurgu2"], 420, 14) if s["tur"] == "soru" else None
        self.yorum = kart_ciz("MY TAKE", tm["vurgu"], (255, 255, 255), 96) if s["tur"] == "yorum" else None
        if self.sayi:
            etiket = self.sayi.get("etiket") or ""
            self.sayi_etiket = _sigdir(kart_ciz(etiket, tm["kart"], tm["kart_yazi"], 74), G - 140) if etiket else None

    def _sayi_metni(self, oran: float) -> str:
        s = self.sayi
        v = s["deger"] * _kolay(oran)
        metin = f"{v:,.{s['ondalik']}f}" if s["ondalik"] else f"{int(round(v)):,}"
        return f"{s['on']}{metin}{s['son']}"

    def ciz(self, img: Image.Image, t: float) -> None:
        """t: sahne içi zaman (sn)."""
        tur = self.s["tur"]
        giris = min(t / 0.35, 1.0)
        cikis = max(0.0, (t - (self.sure - 0.18)) / 0.18)  # son 0,18 sn: küçülerek çık
        olcek_genel = 1.0 - 0.25 * _kolay(cikis)
        nefes = 1.0 + 0.025 * math.sin(t * 3.2)
        sars = 0
        if tur == "kanca" and t < 0.5:
            sars = int(18 * (1 - t / 0.5) * math.sin(t * 90))
        # ana görsel: sayı / soru / ikon
        if tur == "sayi" and self.sayi:
            metin = self._sayi_metni(min(t / 0.9, 1.0))
            yazi = buyuk_yazi(metin, self.tm["vurgu2"], 200, 12)
            yazi = _sigdir(yazi, G - 80)
            o = _zipla(giris) * olcek_genel * (1.0 + (0.08 if t < 0.95 else 0.0) * math.sin(t * 20))
            self._yapistir(img, yazi, G // 2, MERKEZ_Y - 40, o)
            if self.sayi_etiket:
                o2 = _zipla(min(max(t - 0.5, 0) / 0.3, 1.0)) * olcek_genel
                self._yapistir(img, self.sayi_etiket, G // 2, KART_Y - 60, o2)
            # sayı sahnesinde küçük ikon köşede
            self._yapistir(img, self.ikon.resize((200, 200), Image.LANCZOS), 190, MERKEZ_Y - 300,
                           _zipla(min(max(t - 0.2, 0) / 0.3, 1.0)) * olcek_genel, aci=10 * math.sin(t * 2))
            return
        if tur == "soru" and self.soru is not None:
            self._yapistir(img, self.ikon.resize((300, 300), Image.LANCZOS), G // 2 + 250, MERKEZ_Y - 220,
                           _zipla(min(max(t - 0.15, 0) / 0.35, 1.0)) * olcek_genel)
            self._yapistir(img, self.soru, G // 2 - 60, MERKEZ_Y, _zipla(giris) * nefes * olcek_genel,
                           aci=12 * math.sin(t * 4))
        else:
            # ikonun arkasında dönen ışın halkası; kanca sahnesinde üstteki kanca yazısına yer açmak için aşağıda
            cy = MERKEZ_Y + (90 if tur == "kanca" else 0)
            self._isinlar(img, G // 2 + sars, cy, t, _kolay(giris) * olcek_genel * (0.85 if tur == "kanca" else 1))
            o = _zipla(giris) * nefes * olcek_genel
            self._yapistir(img, self.ikon, G // 2 + sars, cy + int(10 * math.sin(t * 2.4)), o,
                           aci=4 * math.sin(t * 1.7))
        if tur == "yorum" and self.yorum is not None:
            self._yapistir(img, self.yorum, G // 2, MERKEZ_Y - 330, _zipla(min(max(t - 0.1, 0) / 0.3, 1.0)) *
                           olcek_genel, aci=-6)
        # anahtar kelime kartları: sırayla, yandan kayarak; sığarsa yan yana, sığmazsa alt alta
        yan_yana = len(self.kartlar) > 1 and sum(kt.width for kt in self.kartlar) + 30 <= G - 80
        for n, kart in enumerate(self.kartlar):
            bas = 0.25 + n * 0.45
            if t < bas:
                continue
            ilerleme = _kolay(min((t - bas) / 0.3, 1.0))
            yon = -1 if n % 2 == 0 else 1
            if yan_yana:
                toplam_en = sum(kt.width for kt in self.kartlar) + 30
                hedef_x = G // 2 - toplam_en // 2 + sum(kt.width + 30 for kt in self.kartlar[:n]) + kart.width // 2
                y = KART_Y
            else:
                hedef_x = G // 2
                y = KART_Y + n * 115 - (70 if len(self.kartlar) > 1 else 0)
            x = int(hedef_x + yon * (1 - ilerleme) * G * 0.9)
            self._yapistir(img, kart, x + sars, y, olcek_genel, aci=(-3 if n % 2 == 0 else 3))
        if tur == "kanca" and t < 0.12:  # ilk karelerde beyaz flaş: göz durur
            beyaz = Image.new("RGBA", img.size, (255, 255, 255, int(255 * (1 - t / 0.12))))
            img.alpha_composite(beyaz)

    def _isinlar(self, img: Image.Image, cx: int, cy: int, t: float, o: float) -> None:
        if o <= 0.02:
            return
        katman = Image.new("RGBA", (900, 900), (0, 0, 0, 0))
        d = ImageDraw.Draw(katman)
        renk = self.tm["vurgu"]
        for i in range(12):
            a = t * 0.6 + i * math.tau / 12
            d.polygon([(450, 450), (450 + 440 * math.cos(a - 0.09), 450 + 440 * math.sin(a - 0.09)),
                       (450 + 440 * math.cos(a + 0.09), 450 + 440 * math.sin(a + 0.09))], fill=(*renk, 46))
        d.ellipse([170, 170, 730, 730], outline=(*renk, 150), width=8)
        boyut = max(int(900 * o), 1)
        katman = katman.resize((boyut, boyut), Image.BILINEAR)
        img.alpha_composite(katman, (cx - boyut // 2, cy - boyut // 2))

    @staticmethod
    def _yapistir(img: Image.Image, parca: Image.Image, cx: int, cy: int, olcek: float, aci: float = 0.0) -> None:
        if olcek <= 0.02:
            return
        en, boy = max(int(parca.width * olcek), 1), max(int(parca.height * olcek), 1)
        p = parca.resize((en, boy), Image.BILINEAR)
        if abs(aci) > 0.3:
            p = p.rotate(aci, resample=Image.BILINEAR, expand=True)
        x, y = cx - p.width // 2, cy - p.height // 2
        if x >= G or y >= Y or x + p.width <= 0 or y + p.height <= 0:
            return
        kx, ky = max(0, -x), max(0, -y)
        p = p.crop((kx, ky, min(p.width, G - x), min(p.height, Y - y)))
        img.alpha_composite(p, (x + kx, y + ky))


def ciz_video(plan: list[dict[str, Any]], k: dict[str, Any], toplam: float, cikis: Path,
              tohum: str = "", ffmpeg: str = "ffmpeg", threads: str = "2") -> list[float]:
    """Planı kare kare çizip `cikis` mp4'üne yazar. Sahne geçiş anlarını (whoosh için) döndürür."""
    tm = tema(k)
    arka = ArkaPlan(tm["ad"], tohum or "x")
    sahneler = [Sahne(s, tm) for s in plan]
    kare_sayisi = max(int(round(toplam * FPS)), 1)
    komut = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{G}x{Y}", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "20", "-pix_fmt", "yuv420p", "-threads", threads, str(cikis)]
    surec = subprocess.Popen(komut, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        si = 0
        for i in range(kare_sayisi):
            t = i / FPS
            while si + 1 < len(plan) and t >= float(plan[si + 1]["bas"]):
                si += 1
            img = arka.kare(t)
            sahneler[si].ciz(img, t - float(plan[si]["bas"]))
            surec.stdin.write(img.convert("RGB").tobytes())
        surec.stdin.close()
        hata = surec.stderr.read().decode("utf-8", "ignore")
        if surec.wait() != 0:
            raise RuntimeError(f"ffmpeg hareketli video yazamadı: {hata[-400:]}")
    finally:
        if surec.poll() is None:
            surec.kill()
    return [float(s["bas"]) for s in plan[1:]]


def uret(is_veri: dict[str, Any], k: dict[str, Any], klasor: Path, ffmpeg: str = "ffmpeg") -> dict[str, Any]:
    """Gorsel ajanının çağırdığı giriş: hareketli.mp4 üretir ve tek bir 'video' sahnesi döndürür."""
    toplam = min(float(is_veri.get("sure") or 30) + 0.6, float(k.get("en_uzun_sure", 58)))
    plan = plan_cikar(is_veri.get("kelime_zamanlari") or [], str(is_veri.get("senaryo", "")), toplam, k)
    cikis = klasor / "hareketli.mp4"
    gecisler = ciz_video(plan, k, toplam, cikis, tohum=str(is_veri.get("baslik", "")), ffmpeg=ffmpeg)
    log.info("hareketli video: %d sahne (%s)", len(plan), ", ".join(f"{p['tur']}:{p['ikon']}" for p in plan))
    return {"tur": "video", "yol": str(cikis), "hareketli": True, "en_uzun": toplam, "gecisler": gecisler,
            "plan": [{k2: v for k2, v in p.items() if k2 != "sayi"} for p in plan]}
