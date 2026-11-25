"""Müzik ve efektler kodla üretilir (telif yok, internet gerekmez).

- Müzik kutusu / ksilofon tınısında, her videoda farklı (tohumlu) neşeli bir melodi
- Efektler: karakter girişinde "pop", sahne geçişinde zil, sonda parıltı
"""
from __future__ import annotations

import random
import wave
from pathlib import Path

import numpy as np

HZ = 44100
PENTATONIK = [0, 2, 4, 7, 9]
AKORLAR = [(0, "M"), (7, "M"), (9, "m"), (5, "M")]  # I - V - vi - IV


def _nota(frekans: float, sure: float, sonum: float = 3.5, harmonik=(1.0, 0.35, 0.12)) -> np.ndarray:
    t = np.arange(int(sure * HZ)) / HZ
    ses = sum(a * np.sin(2 * np.pi * frekans * (i + 1) * t) for i, a in enumerate(harmonik))
    zarf = np.exp(-sonum * t) * np.minimum(1.0, t / 0.005)
    return (ses * zarf).astype(np.float32)


def _frekans(yari_ton: float) -> float:
    return 440.0 * 2 ** ((yari_ton - 9) / 12)  # 0 = C4 civarı


def muzik_uret(sure: float, tohum: str | int = 0, tempo: int | None = None) -> np.ndarray:
    rnd = random.Random(str(tohum))
    tempo = tempo or rnd.choice([92, 100, 108])
    vurus = 60.0 / tempo
    ton = rnd.choice([0, 2, 5, 7, -3])
    n = int((sure + 2) * HZ)
    cikti = np.zeros(n, np.float32)

    def ekle(parca: np.ndarray, bas: float, seviye: float):
        i = int(bas * HZ)
        if i >= n:
            return
        son = min(n, i + len(parca))
        cikti[i:son] += parca[: son - i] * seviye

    # 2 ölçülük motif: tekrar + küçük değişim (kulakta kalsın)
    ritimler = [[1, 0.5, 0.5, 1, 1], [0.5, 0.5, 1, 0.5, 0.5, 1], [1, 1, 0.5, 0.5, 1]]
    motif: list[tuple[float, int]] = []
    for olcu in range(2):
        for r in rnd.choice(ritimler):
            motif.append((r, rnd.randrange(len(PENTATONIK) * 2)))
    t, olcu_no = 0.0, 0
    while t < sure + 1:
        kok, tur = AKORLAR[olcu_no % 4]
        ucu = 3 if tur == "m" else 4
        # bas ve yumuşak akor
        ekle(_nota(_frekans(ton + kok - 24), vurus * 2, 2.2, (1.0, 0.2)), t, 0.32)
        ekle(_nota(_frekans(ton + kok - 24), vurus * 2, 2.2, (1.0, 0.2)), t + vurus * 2, 0.26)
        for yt in (0, ucu, 7):
            ekle(_nota(_frekans(ton + kok + yt - 12), vurus * 4, 0.9, (1.0, 0.1)), t, 0.06)
        olcu_no += 1
        t += vurus * 4
    # melodi: motif tekrarları, her 4 tekrarda bir nota kayar
    t, tekrar = 0.0, 0
    while t < sure + 1:
        for i, (r, derece) in enumerate(motif):
            if tekrar % 4 == 3 and i == len(motif) - 1:
                derece = (derece + 2) % (len(PENTATONIK) * 2)
            yt = PENTATONIK[derece % 5] + 12 * (derece // 5)
            ekle(_nota(_frekans(ton + yt + 12), max(r * vurus, 0.3) + 0.6, 4.5, (1.0, 0.25, 0.3, 0.06)), t, 0.22)
            t += r * vurus
        tekrar += 1
    # baş ve son yumuşak
    gir = int(0.6 * HZ)
    cikti[:gir] *= np.linspace(0, 1, gir)
    cik = int(1.5 * HZ)
    kesim = int(sure * HZ)
    cikti = cikti[:kesim]
    cikti[-cik:] *= np.linspace(1, 0, min(cik, len(cikti)))
    tepe = float(np.max(np.abs(cikti))) or 1.0
    return cikti / tepe * 0.9


def pop() -> np.ndarray:
    t = np.arange(int(0.12 * HZ)) / HZ
    f = 380 + 2600 * t
    return (np.sin(2 * np.pi * np.cumsum(f) / HZ) * np.exp(-28 * t) * 0.8).astype(np.float32)


def zil() -> np.ndarray:
    a = _nota(_frekans(19), 0.9, 4.0, (1.0, 0.0, 0.3))
    b = _nota(_frekans(24), 0.9, 4.0, (1.0, 0.0, 0.3))
    sonuc = np.zeros(len(a) + int(0.09 * HZ), np.float32)
    sonuc[: len(a)] += a * 0.5
    sonuc[int(0.09 * HZ):] += b * 0.5
    return sonuc


def parilti() -> np.ndarray:
    sonuc = np.zeros(int(1.3 * HZ), np.float32)
    for i, yt in enumerate((24, 28, 31, 36, 40)):
        p = _nota(_frekans(yt), 0.8, 5.0, (1.0, 0.0, 0.2)) * 0.35
        bas = int(i * 0.08 * HZ)
        sonuc[bas:bas + len(p)] += p[: len(sonuc) - bas]
    return sonuc


def wav_yaz(dizi: np.ndarray, yol: Path, hz: int = HZ) -> None:
    veri = (np.clip(dizi, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(yol), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(hz)
        wf.writeframes(veri.tobytes())


def wav_oku(yol: Path) -> np.ndarray:
    with wave.open(str(yol), "rb") as wf:
        assert wf.getframerate() == HZ and wf.getnchannels() == 1, "44.1 kHz mono bekleniyor"
        return np.frombuffer(wf.readframes(wf.getnframes()), np.int16).astype(np.float32) / 32768.0
