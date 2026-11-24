"""Müdür: bütün ofisi yönetir. Her kanal için fikir açar, işi ajandan ajana taşır,
hata olursa tekrar dener, takılan işleri kaldığı yerden sürdürür."""
from __future__ import annotations

import time
import traceback
from datetime import datetime
from typing import Any, Callable

from .ajanlar import gorsel, kurgu, senarist, seslendirme, trend, yukleyici
from .cekirdek import Is, gunluk_al, isler, kanal, kanallar

log = gunluk_al("mudur")
EN_FAZLA_DENEME = 3

# durum -> (bu aşamayı yapan ajan, sonraki durum)
ADIMLAR: dict[str, tuple[Callable[[Is, dict[str, Any]], None], str]] = {
    "fikir": (senarist.yaz, "senaryo"),
    "senaryo": (seslendirme.seslendir, "ses"),
    "ses": (gorsel.topla, "gorsel"),
    "gorsel": (kurgu.kurgula, "video"),
}


def is_ilerlet(is_: Is) -> None:
    """Bir işi bitene, onaya düşene veya hata verene kadar ilerletir."""
    k = kanal(is_.kanal)
    while is_.durum in ADIMLAR or is_.durum == "video":
        if is_.durum == "video":
            is_.durum = "onaylandi" if k.get("otomatik_onay") else "onay_bekliyor"
            is_.kaydet()
            log.info("%s: %s", is_.id, "otomatik onaylandı" if is_.durum == "onaylandi" else "onay bekliyor")
            return
        ajan, sonraki = ADIMLAR[is_.durum]
        try:
            ajan(is_, k)
        except Exception as e:
            is_.deneme += 1
            is_.hatalar.append(f"{datetime.now():%d.%m %H:%M} {is_.durum}: {e}")
            log.error("%s: %s aşamasında hata (%d/%d): %s", is_.id, is_.durum, is_.deneme, EN_FAZLA_DENEME, e)
            log.debug(traceback.format_exc())
            if is_.deneme >= EN_FAZLA_DENEME:
                is_.durum = "hata"
            is_.kaydet()
            return
        is_.durum = sonraki
        is_.deneme = 0
        is_.kaydet()


def yarim_isleri_surdur() -> None:
    for durum in list(ADIMLAR) + ["video"]:
        for i in isler(durum):
            log.info("%s: yarım kalan iş sürdürülüyor (%s)", i.id, i.durum)
            is_ilerlet(i)


def gunluk_hedef(k: dict[str, Any]) -> int:
    """Bugün bu kanal için kaç yeni iş açılmalı (onay bekleyenler birikmesin)."""
    bugun = datetime.now().date().isoformat()
    bugun_acilan = sum(1 for i in isler(kanal_id=k["id"]) if i.olusturma[:10] == bugun)
    bekleyen = len(isler("onay_bekliyor", k["id"])) + len(isler("onaylandi", k["id"]))
    tampon = k.get("en_fazla_bekleyen", 6)
    return max(0, min(k.get("gunluk_video", 1) - bugun_acilan, tampon - bekleyen))


def kanal_icin_uret(k: dict[str, Any], adet: int | None = None) -> list[Is]:
    adet = gunluk_hedef(k) if adet is None else adet
    if adet <= 0:
        log.info("%s: bugünlük yeterli video var", k["id"])
        return []
    yeni: list[Is] = []

    # İzinli yayıncı klibi varsa, kanalın ayarındaki orana göre bir kısmı klip yorumu olur
    if "izinli_klip" in k.get("kaynak_modlari", []):
        oran = float(k.get("klip_orani", 0.5))
        for _ in range(round(adet * oran)):
            klip = gorsel.klip_sec(k)
            if not klip:
                log.info("%s: kullanılabilir izinli klip yok, haber/yorum ile devam", k["id"])
                break
            i = Is(kanal=k["id"], veri={"mod": "izinli_klip", "konu": klip["klip_aciklama"],
                                        "aci": "klibe özgün yorum ve bağlam", **klip})
            i.kaydet()
            yeni.append(i)

    kalan = adet - len(yeni)
    if kalan > 0:
        for f in trend.fikir_bul(k, kalan):
            i = Is(kanal=k["id"], veri={"mod": "normal", **f})
            i.kaydet()
            yeni.append(i)
    for i in yeni:
        is_ilerlet(i)
    return yeni


def uret(kanal_id: str | None = None, adet: int | None = None) -> None:
    yarim_isleri_surdur()
    hedefler = [kanal(kanal_id)] if kanal_id else kanallar()
    for k in hedefler:
        try:
            kanal_icin_uret(k, adet)
        except Exception as e:  # bir kanal çökerse diğerleri devam eder
            log.error("%s kanalında üretim durdu: %s", k["id"], e)


def gunluk_calisma() -> None:
    """Zamanlayıcının her gün çağırdığı iş: üret, sonra onaylıları yükle."""
    bas = time.time()
    log.info("=== Günlük çalışma başladı ===")
    from .doktor import kontrol

    sorunlar = [s for s in kontrol() if not s[1] and s[2]]
    if sorunlar:
        for ad, _, _, cozum in sorunlar:
            log.error("Eksik: %s -> %s", ad, cozum)
        log.error("Zorunlu eksikler var, üretim atlandı. 'python -m ofis doktor' ile bak.")
    else:
        uret()
    try:
        yukleyici.yukle_hepsi()
    except Exception as e:
        log.error("Yükleme adımı çalışmadı: %s", e)
    log.info("=== Günlük çalışma bitti (%.0f dk) ===", (time.time() - bas) / 60)
