"""Komutlar:  python -m ofis <komut>

  doktor               eksikleri kontrol eder
  sesleri-indir        kanalların ses modellerini indirir
  yetkilendir KANAL    bir YouTube kanalını sisteme bağlar (bir kez)
  uret [--kanal K] [--adet N]   video üretir (onaya düşürür)
  onay                 onay masasını açar (tarayıcıda)
  yukle                onaylı videoları YouTube'a yükler
  rapor                haftalık raporu yazar
  gunluk               zamanlayıcının çalıştırdığı tam gün: üret + yükle
  durum                işlerin özetini gösterir
  temizle              biten işlerin ara dosyalarını siler (3 gün), eski videoları (30 gün)
  ozet                 bugünün durum özetini yazar (veri/raporlar/)
  yayinla İŞ [İŞ...]   seçilen işleri hemen herkese açık yükler (zamanlama yok)
  hatirlat             yayına giren kampanya kliplerini bildirir (30 dk Content Rewards kuralı)
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="ofis", description="Shorts Ofis", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    alt = p.add_subparsers(dest="komut", required=True)
    alt.add_parser("doktor")
    alt.add_parser("sesleri-indir")
    y = alt.add_parser("yetkilendir")
    y.add_argument("kanal")
    u = alt.add_parser("uret")
    u.add_argument("--kanal")
    u.add_argument("--adet", type=int)
    alt.add_parser("onay")
    alt.add_parser("yukle")
    alt.add_parser("rapor")
    alt.add_parser("gunluk")
    alt.add_parser("durum")
    alt.add_parser("hatirlat")
    alt.add_parser("temizle")
    alt.add_parser("ozet")
    yy = alt.add_parser("yayinla")
    yy.add_argument("isler", nargs="+")
    a = p.parse_args(argv)
    if a.komut == "yayinla":
        # Senin komutunla: verilen işleri onaylar ve zamanlamadan HEMEN herkese açık yükler
        from .ajanlar import yukleyici
        from .cekirdek import Is, kanal
        for is_id in a.isler:
            i = Is.yukle(is_id)
            i.durum, i.veri["hemen_yayinla"] = "onaylandi", True
            i.kaydet()
            yukleyici.yukle_bir(i, kanal(i.kanal))
            i = Is.yukle(is_id)
            d = i.veri.get("youtube_durum") or {}
            print(f"{is_id}: https://youtube.com/shorts/{i.veri.get('youtube_id')}  "
                  f"gizlilik={d.get('privacyStatus', '?')}  başlık={i.veri['seo']['title']}")
            if i.veri.get("kampanya"):
                print(f"   Content Rewards'a 30 dk içinde gönder: {i.veri['kampanya']}")
        return 0
    if a.komut == "temizle":
        from .temizlik import temizle
        print(temizle())
        return 0
    if a.komut == "ozet":
        from .temizlik import gunluk_ozet
        print(gunluk_ozet())
        return 0
    if a.komut == "hatirlat":
        from .ajanlar.hatirlatici import kontrol
        print(kontrol(), "kampanya bildirimi")
        return 0

    if a.komut == "doktor":
        from .doktor import yazdir
        return 1 if yazdir() else 0
    if a.komut == "sesleri-indir":
        from .ajanlar.seslendirme import ses_indir
        from .cekirdek import kanallar
        for k in kanallar(sadece_aktif=False):
            for ses in [k["ses"], k.get("ses_yedek")]:
                if ses:
                    print("İndirildi:", ses_indir(ses))
        return 0
    if a.komut == "yetkilendir":
        from .ajanlar.yukleyici import yetkilendir
        print("Bağlanan kanal:", yetkilendir(a.kanal))
        return 0
    if a.komut == "uret":
        from .mudur import uret
        uret(a.kanal, a.adet)
        return 0
    if a.komut == "onay":
        from .ajanlar.onay import calistir
        calistir()
        return 0
    if a.komut == "yukle":
        from .ajanlar.yukleyici import yukle_hepsi
        print(yukle_hepsi(), "video yüklendi")
        return 0
    if a.komut == "rapor":
        from .ajanlar.analist import rapor_yaz
        print(rapor_yaz())
        return 0
    if a.komut == "gunluk":
        from .mudur import gunluk_calisma
        gunluk_calisma()
        return 0
    if a.komut == "durum":
        from .cekirdek import isler
        sayim = Counter((i.kanal, i.durum) for i in isler())
        for (k, d), n in sorted(sayim.items()):
            print(f"{k:15} {d:15} {n}")
        for i in isler("hata"):
            print(f"HATA {i.id}: {i.hatalar[-1] if i.hatalar else ''}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
