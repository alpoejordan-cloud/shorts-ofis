"""Canlı olay kaydı: her ajan ve her yapay zeka "şu an ne yapıyorum" bilgisini buraya yazar, panel okur.

Olaylar günlük JSON satırları olarak veri/olaylar/YYYY-MM-DD.jsonl dosyasına eklenir.
Bir olay yazılamasa bile (disk, izin) asıl iş asla durmaz: buradaki her şey sessizce yutulur.
Anahtar/şifre gibi sırlar hiçbir olaya yazılmaz.
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

_ajan: contextvars.ContextVar[str | None] = contextvars.ContextVar("ofis_ajan", default=None)
_is: contextvars.ContextVar[str | None] = contextvars.ContextVar("ofis_is", default=None)
_kanal: contextvars.ContextVar[str | None] = contextvars.ContextVar("ofis_kanal", default=None)
_kilit = threading.Lock()

# Hangi fonksiyon yapay zekaya sorduğunda panelde ne yazacağı
GOREV_ADLARI = {
    # Ollama (senarist / trend)
    "fikir_bul": "trend haberlerinden video fikri çıkarıyor",
    "yaz": "senaryo yazıyor",
    "genislet": "kısa kalan senaryoyu uzatıyor",
    "konuyu_cevir": "konuyu kanal diline çeviriyor",
    "gorsel_kelimeleri_ingilizce": "görsel arama kelimelerini çeviriyor",
    "klip_metni_yaz": "yayıncı klibi için metin yazıyor",
    "gemini_ile_iyilestir": "Gemini'nin notlarına göre senaryoyu düzeltiyor",
    "gemini_beyin_firtinasi": "Gemini'nin eleştirisine göre fikirleri yeniliyor",
    # Gemini
    "senaryo_denetle": "senaryoyu denetliyor (kanca, akış, doğruluk)",
    "fikirleri_elestir": "fikirleri eleştiriyor",
    "makaleleri_puanla": "haberleri izlenme potansiyeline göre puanlıyor",
    "kanca_ve_baslik": "kanca ve başlık yazıyor",
    "senaryoyu_akicilastir": "senaryoyu akıcılaştırıyor",
    "seo_onerisi": "SEO (başlık/etiket) öneriyor",
}


def klasor() -> Path:
    from .cekirdek import VERI

    yol = VERI / "olaylar"
    yol.mkdir(parents=True, exist_ok=True)
    return yol


def dosya(gun: str | None = None) -> Path:
    return klasor() / f"{gun or f'{datetime.now():%Y-%m-%d}'}.jsonl"


def yaz(tur: str, mesaj: str = "", ajan: str | None = None, yz: str | None = None, is_id: str | None = None,
        kanal: str | None = None, **ek: Any) -> None:
    """Bir olay satırı ekler. tur: basla | bitir | hata | bilgi | uyari."""
    try:
        satir = {
            "z": round(time.time(), 3), "t": datetime.now().isoformat(timespec="seconds"), "tur": tur,
            "ajan": ajan or _ajan.get() or "ofis", "yz": yz, "mesaj": str(mesaj)[:500],
            "is": is_id or _is.get(), "kanal": kanal or _kanal.get(), "pid": os.getpid(), **ek,
        }
        metin = json.dumps(satir, ensure_ascii=False) + "\n"
        with _kilit, open(dosya(), "a", encoding="utf-8") as f:
            f.write(metin)
    except Exception:  # olay kaydı asıl işi asla bozmaz
        pass


def cagiran_gorev(derinlik: int = 2) -> str:
    """Yapay zekaya soran fonksiyonun adına göre okunur bir görev metni (panel için)."""
    try:
        f = sys._getframe(derinlik)
        for _ in range(4):
            if f is None:
                break
            if f.f_code.co_name in GOREV_ADLARI:
                return GOREV_ADLARI[f.f_code.co_name]
            f = f.f_back
    except Exception:
        pass
    return "çalışıyor"


@contextmanager
def calisiyor(ajan: str | None, ne: str, yz: str | None = None, is_id: str | None = None,
              kanal: str | None = None, **ek: Any) -> Iterator[None]:
    """Bir işin başını ve sonunu kaydeder; arada panel bu ajanı/yapay zekayı "çalışıyor" gösterir."""
    kimlik = uuid.uuid4().hex[:10]
    ajan = ajan or _ajan.get() or "ofis"
    jetonlar = [_ajan.set(ajan)]
    if is_id:
        jetonlar.append(_is.set(is_id))
    if kanal:
        jetonlar.append(_kanal.set(kanal))
    bas = time.time()
    yaz("basla", ne, ajan=ajan, yz=yz, is_id=is_id, kanal=kanal, kimlik=kimlik, **ek)
    try:
        yield
    except BaseException as e:
        yaz("hata", f"{ne}: {e}", ajan=ajan, yz=yz, is_id=is_id, kanal=kanal, kimlik=kimlik,
            sure=round(time.time() - bas, 2))
        raise
    else:
        yaz("bitir", ne, ajan=ajan, yz=yz, is_id=is_id, kanal=kanal, kimlik=kimlik, sure=round(time.time() - bas, 2))
    finally:
        for j in reversed(jetonlar):
            try:
                j.var.reset(j)
            except ValueError:
                pass


class OlayIsleyici(logging.Handler):
    """Ajanların normal günlük (log) satırlarını da canlı akışa düşürür."""

    def emit(self, kayit: logging.LogRecord) -> None:
        if kayit.levelno < logging.INFO:
            return
        tur = "hata" if kayit.levelno >= logging.ERROR else "uyari" if kayit.levelno >= logging.WARNING else "bilgi"
        try:
            mesaj = kayit.getMessage()
        except Exception:
            mesaj = str(kayit.msg)
        yaz(tur, mesaj, ajan=kayit.name, log=True)


def oku(gun: str | None = None, son: int = 400) -> list[dict[str, Any]]:
    """Günün son `son` olayını okur (dosyanın yalnız sonunu okur; büyük dosyada da hafif)."""
    yol = dosya(gun)
    if not yol.exists():
        return []
    try:
        with open(yol, "rb") as f:
            f.seek(0, os.SEEK_END)
            boyut = f.tell()
            f.seek(max(0, boyut - son * 600))
            ham = f.read().decode("utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    if boyut > son * 600 and ham:
        ham = ham[1:]  # yarım satır
    sonuc = []
    for s in ham[-son:]:
        try:
            sonuc.append(json.loads(s))
        except ValueError:
            continue
    return sonuc


def surec_yasiyor(pid: int) -> bool:
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        try:
            import ctypes

            k32 = ctypes.windll.kernel32
            tutamac = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not tutamac:
                return False
            kod = ctypes.c_ulong()
            k32.GetExitCodeProcess(tutamac, ctypes.byref(kod))
            k32.CloseHandle(tutamac)
            return kod.value == 259  # STILL_ACTIVE
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acik_isler(olaylar: list[dict[str, Any]], en_uzun_sn: float = 6 * 3600) -> list[dict[str, Any]]:
    """Başlamış ama bitmemiş (ve süreci hâlâ yaşayan) işler: şu an çalışanlar."""
    acik: dict[str, dict[str, Any]] = {}
    for o in olaylar:
        k = o.get("kimlik")
        if not k:
            continue
        if o["tur"] == "basla":
            acik[k] = o
        elif o["tur"] in ("bitir", "hata"):
            acik.pop(k, None)
    simdi = time.time()
    canli = {}
    sonuc = []
    for o in acik.values():
        pid = int(o.get("pid") or 0)
        if pid not in canli:
            canli[pid] = surec_yasiyor(pid)
        if canli[pid] and simdi - o["z"] < en_uzun_sn:
            sonuc.append({**o, "gecen": round(simdi - o["z"], 1)})
    return sorted(sonuc, key=lambda o: o["z"])
