"""Müdür: bütün ofisi yönetir. Her kanal için fikir açar, işi ajandan ajana taşır,
hata olursa tekrar dener, takılan işleri kaldığı yerden sürdürür."""
from __future__ import annotations

import random
import time
import traceback
from datetime import datetime
from typing import Any, Callable

from .ajanlar import gorsel, kurgu, senarist, seslendirme, trend, yukleyici
from .cekirdek import Is, gunluk_al, isler, kanal, kanallar

log = gunluk_al("mudur")
EN_FAZLA_DENEME = 3
BEKLEME_SN = 45  # geçici hatalarda (Ollama/ağ) yeniden denemeden önce bekleme; her denemede artar

# durum -> (bu aşamayı yapan ajan, sonraki durum)
ADIMLAR: dict[str, tuple[Callable[[Is, dict[str, Any]], None], str]] = {
    "fikir": (senarist.yaz, "senaryo"),
    "senaryo": (seslendirme.seslendir, "ses"),
    "ses": (gorsel.topla, "gorsel"),
    "gorsel": (kurgu.kurgula, "video"),
}


def otomatik_onay_uygun(is_: Is, k: dict[str, Any]) -> bool:
    """Kanal otomatik onaylıysa kalite kontrolünü çalıştırır; geçmeyen video onay masasına düşer."""
    if not k.get("otomatik_onay"):
        return False
    if is_.veri.get("kampanya"):
        # kampanya klibi: yayına girdiği an 30 dk gönderim süresi başlar; zamanı kullanıcı seçer (masadan "hemen yayınla")
        is_.veri["kalite_sorunlari"] = ["kampanya klibi: 30 dk gönderim kuralı için yayın zamanını sen seç"]
        return False
    from .kalite import kontrol

    try:
        sorunlar = kontrol(is_, k)
    except Exception as e:  # kontrol çalışamazsa güvenli taraf: masaya
        sorunlar = [f"kalite kontrolü çalışmadı: {e}"]
    is_.veri["kalite_sorunlari"] = sorunlar
    if sorunlar:
        log.warning("%s: kalite kontrolünden geçmedi, onay masasına: %s", is_.id, "; ".join(sorunlar))
    return not sorunlar


def is_ilerlet(is_: Is) -> None:
    """Bir işi bitene, onaya düşene veya hata verene kadar ilerletir."""
    k = kanal(is_.kanal)
    while is_.durum in ADIMLAR or is_.durum == "video":
        if is_.durum == "video":
            is_.durum = "onaylandi" if otomatik_onay_uygun(is_, k) else "onay_bekliyor"
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
            is_.kaydet()
            time.sleep(BEKLEME_SN * is_.deneme)
            continue
        is_.durum = sonraki
        is_.deneme = 0
        is_.kaydet()


def yarim_isleri_surdur() -> None:
    for durum in list(ADIMLAR) + ["video"]:
        for i in isler(durum):
            log.info("%s: yarım kalan iş sürdürülüyor (%s)", i.id, i.durum)
            is_ilerlet(i)


GECE_PENCERESI = (12, 22)  # 02:30 çalışması bu saatlerdeki slotları doldurur (17:00, 19:00, 20:00)


def calisma_penceresi(simdi: datetime | None = None) -> str:
    """Öğleden önce başlayan çalışma 'gece' (ertesi akşam slotları), sonrası 'aksam' (o gecenin geç slotları)."""
    return "gece" if (simdi or datetime.now()).hour < 12 else "aksam"


def penceredeki_slotlar(k: dict[str, Any], pencere: str) -> int:
    saatler = [int(s.split(":")[0]) for s in (k.get("yayin_saatleri") or ["18:00"])]
    gece = sum(GECE_PENCERESI[0] <= h < GECE_PENCERESI[1] for h in saatler)
    return gece if pencere == "gece" else len(saatler) - gece


def _yerel(zaman: str) -> datetime:
    """İşlerin oluşturma zamanı UTC saklanır; pencere/gün hesabı bilgisayarın yerel saatiyle yapılır."""
    z = datetime.fromisoformat(zaman)
    return z.astimezone().replace(tzinfo=None) if z.tzinfo else z


def gunluk_hedef(k: dict[str, Any], simdi: datetime | None = None) -> int:
    """Bu çalışmada bu kanal için kaç yeni iş açılmalı: çalışmanın penceresindeki slot sayısı kadar
    (günlük toplam gunluk_video'yu aşmadan, onay bekleyenler birikmeden)."""
    simdi = simdi or datetime.now()
    bugun = simdi.date().isoformat()
    pencere = calisma_penceresi(simdi)
    bugunkuler = [i for i in isler(kanal_id=k["id"]) if _yerel(i.olusturma).date().isoformat() == bugun]
    bu_pencere = sum(1 for i in bugunkuler if calisma_penceresi(_yerel(i.olusturma)) == pencere)
    bekleyen = len(isler("onay_bekliyor", k["id"])) + len(isler("onaylandi", k["id"]))
    tampon = k.get("en_fazla_bekleyen", 6)
    kalan_gun = k.get("gunluk_video", 1) - len(bugunkuler)
    return max(0, min(penceredeki_slotlar(k, pencere) - bu_pencere, kalan_gun, tampon - bekleyen))


def kanal_icin_uret(k: dict[str, Any], adet: int | None = None) -> list[Is]:
    adet = gunluk_hedef(k) if adet is None else adet
    if adet <= 0:
        log.info("%s: bugünlük yeterli video var", k["id"])
        return []
    yeni: list[Is] = []

    # İzinli yayıncı klibi varsa, kanalın ayarındaki orana göre bir kısmı klip yorumu olur
    if "izinli_klip" in k.get("kaynak_modlari", []):
        oran = float(k.get("klip_orani", 0.5))
        for _ in range(sum(random.random() < oran for _ in range(adet))):  # her slot oran olasılıkla klip
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
        try:  # önce hazır (onaylı) videolar yüklensin ki yakın slotu (ör. 19:00) kaçırmasınlar
            yukleyici.yukle_hepsi()
        except Exception as e:
            log.error("Ön yükleme çalışmadı: %s", e)
        uret()
    try:
        yukleyici.yukle_hepsi()
    except Exception as e:
        log.error("Yükleme adımı çalışmadı: %s", e)
    from .temizlik import gunluk_ozet, temizle

    for adim in (temizle, lambda: gunluk_ozet((time.time() - bas) / 60)):
        try:
            adim()
        except Exception as e:  # temizlik/özet hatası üretimi bozmasın
            log.warning("Temizlik/özet adımı çalışmadı: %s", e)
    log.info("=== Günlük çalışma bitti (%.0f dk) ===", (time.time() - bas) / 60)
