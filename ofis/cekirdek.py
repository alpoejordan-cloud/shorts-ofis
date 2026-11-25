"""Ofisin ortak parçaları: klasörler, ayarlar, iş kayıtları ve günlük (log)."""
from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

KOK = Path(os.environ.get("SHORTS_OFIS_KOK", Path(__file__).resolve().parent.parent))
VERI = Path(os.environ.get("SHORTS_OFIS_VERI", KOK / "veri"))
ISLER = VERI / "isler"
CIKTI = VERI / "cikti"
TOKENLAR = VERI / "tokenlar"
RAPORLAR = VERI / "raporlar"
GUNLUK = VERI / "gunluk"
SESLER = VERI / "sesler"
AYAR = KOK / "config"

for _k in (ISLER, CIKTI, TOKENLAR, RAPORLAR, GUNLUK, SESLER):
    _k.mkdir(parents=True, exist_ok=True)

if load_dotenv:
    load_dotenv(KOK / ".env")


def gunluk_al(ad: str) -> logging.Logger:
    log = logging.getLogger(ad)
    if not log.handlers:
        log.setLevel(logging.INFO)
        bicim = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        dosya = logging.FileHandler(GUNLUK / f"{datetime.now():%Y-%m-%d}.log", encoding="utf-8")
        dosya.setFormatter(bicim)
        ekran = logging.StreamHandler()
        ekran.setFormatter(bicim)
        log.addHandler(dosya)
        log.addHandler(ekran)
        from .olay import OlayIsleyici  # panelin canlı akışı

        log.addHandler(OlayIsleyici())
    return log


def yaml_oku(ad: str) -> dict[str, Any]:
    yol = AYAR / ad
    if not yol.exists():
        return {}
    with open(yol, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def kanallar(sadece_aktif: bool = True) -> list[dict[str, Any]]:
    liste = yaml_oku("kanallar.yaml").get("kanallar", [])
    return [k for k in liste if k.get("aktif", True) or not sadece_aktif]


def kanal(kanal_id: str) -> dict[str, Any]:
    for k in kanallar(sadece_aktif=False):
        if k["id"] == kanal_id:
            return k
    raise KeyError(f"Kanal bulunamadı: {kanal_id}")


def ortam(ad: str, varsayilan: str = "") -> str:
    return os.environ.get(ad, varsayilan)


def simdi() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# İşin geçtiği aşamalar, sırasıyla
DURUMLAR = [
    "fikir", "senaryo", "ses", "gorsel", "video",
    "onay_bekliyor", "onaylandi", "yuklendi",
]
SON_DURUMLAR = {"yuklendi", "reddedildi", "hata"}


@dataclass
class Is:
    kanal: str
    durum: str = "fikir"
    id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6])
    olusturma: str = field(default_factory=simdi)
    guncelleme: str = field(default_factory=simdi)
    veri: dict[str, Any] = field(default_factory=dict)
    hatalar: list[str] = field(default_factory=list)
    deneme: int = 0

    @property
    def klasor(self) -> Path:
        yol = CIKTI / self.kanal / self.id
        yol.mkdir(parents=True, exist_ok=True)
        return yol

    def kaydet(self) -> None:
        self.guncelleme = simdi()
        gecici = ISLER / f"{self.id}.json.tmp"
        gecici.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        gecici.replace(ISLER / f"{self.id}.json")

    @classmethod
    def yukle(cls, is_id: str) -> "Is":
        return cls(**json.loads((ISLER / f"{is_id}.json").read_text(encoding="utf-8")))


def isler(durum: str | None = None, kanal_id: str | None = None) -> list[Is]:
    sonuc = []
    for yol in sorted(ISLER.glob("*.json")):
        try:
            i = Is(**json.loads(yol.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError):
            continue
        if durum and i.durum != durum:
            continue
        if kanal_id and i.kanal != kanal_id:
            continue
        sonuc.append(i)
    return sonuc


def gecmis_basliklar(kanal_id: str, limit: int = 200) -> list[str]:
    """Daha önce işlenmiş konular; aynı konuyu tekrar üretmemek için."""
    basliklar = [i.veri.get("konu") or i.veri.get("baslik", "") for i in isler(kanal_id=kanal_id)]
    return [b for b in basliklar if b][-limit:]
