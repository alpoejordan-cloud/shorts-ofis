"""Disk temizliği ve günlük durum özeti.

- Biten işlerin (yüklendi / reddedildi / hata) ara dosyaları birkaç gün sonra silinir
  (görseller, ham video, parçalar, ses). Son video dosyası daha uzun tutulur.
- Her günlük çalışmanın sonunda veri/raporlar/gunluk_YYYY-MM-DD.md özeti yazılır.
"""
from __future__ import annotations

import shutil
from collections import Counter
from datetime import datetime, timedelta

from .cekirdek import VERI, gunluk_al, isler

log = gunluk_al("temizlik")
ARA_DOSYALAR = ("ham_video.mp4", "ses.wav", "gecis.wav", "liste.txt")
BITMIS = ("yuklendi", "reddedildi", "hata")


def temizle(ara_gun: int = 3, video_gun: int = 30, simdi: datetime | None = None) -> dict[str, int]:
    """Biten işlerde ara dosyaları `ara_gun`, videoyu `video_gun` gün sonra siler. Boşalan MB'ı döner."""
    simdi = simdi or datetime.now()
    sayac = {"is": 0, "mb": 0}
    for i in isler():
        if i.durum not in BITMIS or not i.klasor.exists():
            continue
        try:
            yas = simdi - datetime.fromisoformat(i.guncelleme[:19])
        except ValueError:
            continue
        silinecek = []
        if yas > timedelta(days=ara_gun):
            silinecek += [i.klasor / d for d in ARA_DOSYALAR] + [i.klasor / "gorseller"]
            silinecek += list(i.klasor.glob("parca_*.mp4"))
        if yas > timedelta(days=video_gun):
            silinecek.append(i.klasor / "video.mp4")
        bosalan = 0
        for p in silinecek:
            if p.is_dir():
                bosalan += sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                bosalan += p.stat().st_size
                p.unlink(missing_ok=True)
        if bosalan:
            sayac["is"] += 1
            sayac["mb"] += bosalan // (1 << 20)
    if sayac["is"]:
        log.info("Temizlik: %d işten %d MB boşaltıldı", sayac["is"], sayac["mb"])
    return sayac


def gunluk_ozet(sure_dk: float | None = None, simdi: datetime | None = None) -> str:
    """Bugünün özetini veri/raporlar/gunluk_YYYY-MM-DD.md dosyasına yazar ve metni döner."""
    simdi = simdi or datetime.now()
    bugun = simdi.date().isoformat()
    tum = isler()
    durumlar = Counter((i.kanal, i.durum) for i in tum)
    bugun_acilan = [i for i in tum if i.olusturma[:10] == bugun]
    bugun_yuklenen = [i for i in tum if i.durum == "yuklendi" and i.guncelleme[:10] == bugun]
    hatalar = [i for i in tum if i.durum == "hata" and i.guncelleme[:10] == bugun]
    gonderim = [i for i in tum if (i.veri.get("kampanya_gonderim") or {}).get("durum") in ("bekliyor", "sure_doldu")]
    satirlar = [f"# Günlük özet: {bugun}", ""]
    if sure_dk is not None:
        satirlar.append(f"Günlük çalışma süresi: {sure_dk:.0f} dk")
    satirlar += [f"Bugün üretilen iş: {len(bugun_acilan)}", f"Bugün yüklenen: {len(bugun_yuklenen)}", "",
                 "## Kanal / durum", ""]
    for (kanal, durum), n in sorted(durumlar.items()):
        satirlar.append(f"- {kanal}: {durum} = {n}")
    satirlar += ["", "## Onay bekleyenler", ""]
    satirlar += [f"- {i.kanal}: {i.veri.get('baslik', i.id)}" for i in tum if i.durum == "onay_bekliyor"] or ["- yok"]
    satirlar += ["", "## Bugünkü hatalar", ""]
    satirlar += [f"- {i.id} ({i.kanal}): {i.hatalar[-1] if i.hatalar else ''}" for i in hatalar] or ["- yok"]
    satirlar += ["", "## Kampanya gönderimi", ""]
    satirlar += [f"- {i.veri['kampanya_gonderim']['durum']}: {i.veri.get('baslik', '')} "
                 f"{i.veri['kampanya_gonderim']['link']}" for i in gonderim] or ["- bekleyen yok"]
    metin = "\n".join(satirlar) + "\n"
    klasor = VERI / "raporlar"
    klasor.mkdir(parents=True, exist_ok=True)
    (klasor / f"gunluk_{bugun}.md").write_text(metin, encoding="utf-8")
    return metin
