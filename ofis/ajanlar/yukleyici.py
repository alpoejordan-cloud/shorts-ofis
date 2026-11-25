"""Yükleyici: onaylanan videoları YouTube Data API ile ilgili kanala yükler ve
kanalın yayın saatine zamanlar.

Not: Google'ın denetiminden geçmemiş API projelerinde yüklenen videolar 'gizli' kalır.
Bu durumda videolar YouTube Studio'da hazır bekler, sen tek tıkla herkese açarsın."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ..cekirdek import AYAR, TOKENLAR, Is, gunluk_al, isler, kanal, ortam

log = gunluk_al("yukleyici")
KAPSAMLAR = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def istemci_dosyasi(kanal_id: str | None = None) -> Path:
    """Kanalın Google Cloud OAuth dosyası. Kanal ayarında `google_istemci` varsa (ör. çocuk kanalları için
    ayrı proje = ayrı günlük kota) o dosya, yoksa config/client_secret.json."""
    if kanal_id:
        try:
            ad = kanal(kanal_id).get("google_istemci")
        except KeyError:
            ad = None
        if ad:
            return AYAR / str(ad)
    return AYAR / "client_secret.json"


def kota_grubu(kanal_id: str) -> str:
    """Aynı Google Cloud projesini (aynı OAuth dosyasını) kullanan kanallar aynı günlük kotayı paylaşır."""
    return istemci_dosyasi(kanal_id).name


def token_yolu(kanal_id: str) -> Path:
    return TOKENLAR / f"{kanal_id}.json"


def kimlik(kanal_id: str, etkilesimli: bool = False):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    yol = token_yolu(kanal_id)
    k = Credentials.from_authorized_user_file(str(yol), KAPSAMLAR) if yol.exists() else None
    if k and k.expired and k.refresh_token:
        try:
            k.refresh(Request())
        except Exception as e:
            log.warning("%s: token yenilenemedi (%s)", kanal_id, e)
            k = None
    if not k or not k.valid:
        if not etkilesimli:
            raise RuntimeError(f"{kanal_id} için izin yok. Şunu çalıştır: python -m ofis yetkilendir {kanal_id}")
        from google_auth_oauthlib.flow import InstalledAppFlow

        dosya = istemci_dosyasi(kanal_id)
        if not dosya.exists():
            raise RuntimeError(f"config/{dosya.name} yok. Kurulum rehberindeki Google Cloud adımını yap.")
        akis = InstalledAppFlow.from_client_secrets_file(str(dosya), KAPSAMLAR)
        print(f"\nTarayıcı açılacak. '{kanal_id}' için doğru YouTube KANALINI seç.\n")
        # select_account: Google her seferinde hesap/kanal seçtirir (son kullanılan kanala otomatik bağlanmasın)
        k = akis.run_local_server(port=0, prompt="consent select_account", access_type="offline")
        yol.write_text(k.to_json(), encoding="utf-8")
    return k


def servis(kanal_id: str, etkilesimli: bool = False):
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=kimlik(kanal_id, etkilesimli), cache_discovery=False)


def yetkilendir(kanal_id: str) -> str:
    yt = servis(kanal_id, etkilesimli=True)
    cevap = yt.channels().list(part="snippet", mine=True).execute()
    ad = cevap["items"][0]["snippet"]["title"] if cevap.get("items") else "(kanal bulunamadı)"
    log.info("%s bağlandı: %s", kanal_id, ad)
    return ad


def sonraki_yayin_zamani(k: dict[str, Any], dolu: list[datetime], simdi: datetime | None = None) -> datetime:
    """Kanalın yayın saatlerinden, dolu olmayan ilk zamanı bulur (en az 30 dk sonrası)."""
    bolge = ZoneInfo(k.get("saat_dilimi", "Europe/Istanbul"))
    simdi = (simdi or datetime.now(bolge)).astimezone(bolge)
    saatler = k.get("yayin_saatleri") or ["18:00"]
    dolu_set = {d.astimezone(bolge).replace(second=0, microsecond=0) for d in dolu}
    for gun in range(0, 60):
        tarih = (simdi + timedelta(days=gun)).date()
        # gun_yayin_saatleri: o güne özel saatler (ör. erken paylaşım günü), normal saatlerin yerine geçer
        gunun = (k.get("gun_yayin_saatleri") or {}).get(tarih.isoformat()) or saatler
        for s in sorted(gunun):
            sa, dk = map(int, s.split(":"))
            aday = datetime(tarih.year, tarih.month, tarih.day, sa, dk, tzinfo=bolge)
            if aday > simdi + timedelta(minutes=15) and aday not in dolu_set:  # 18:30 çalışması 19:00 slotunu yakalasın
                return aday
    raise RuntimeError("60 gün içinde boş yayın saati yok")


def yukle_bir(is_: Is, k: dict[str, Any]) -> None:
    from googleapiclient.http import MediaFileUpload

    from .seo import uygula

    hemen = bool(is_.veri.get("hemen_yayinla"))
    if hemen:  # sen istedin: zamanlama yok, hemen herkese açık
        zaman = datetime.now(ZoneInfo(k.get("saat_dilimi", "Europe/Istanbul")))
    else:
        dolu = [datetime.fromisoformat(i.veri["yayin_zamani"]) for i in isler("yuklendi", k["id"])
                if i.veri.get("yayin_zamani")]
        zaman = sonraki_yayin_zamani(k, dolu)
    durum: dict[str, Any] = {
        "privacyStatus": "public" if hemen else "private",
        # çocuk kanalları "Made for Kids" (COPPA) olarak işaretlenir: yorumlar ve kişiselleştirilmiş reklam kapanır
        "selfDeclaredMadeForKids": bool(k.get("cocuklar_icin", False)),
        "containsSyntheticMedia": bool(is_.veri.get("yapay_icerik", False)),
    }
    if not hemen:
        durum["publishAt"] = zaman.isoformat()
    snippet = uygula(is_.veri, k)  # SEO: başlık/açıklama/etiket, dil, kategori
    is_.veri["seo"] = snippet
    govde = {"snippet": snippet, "status": durum}
    medya = MediaFileUpload(str(is_.klasor / is_.veri["video"]), mimetype="video/mp4", resumable=True, chunksize=8 << 20)
    istek = servis(k["id"]).videos().insert(part="snippet,status", body=govde, media_body=medya)
    cevap = None
    while cevap is None:
        _, cevap = istek.next_chunk()
    is_.veri.update({"youtube_id": cevap["id"], "yayin_zamani": zaman.isoformat(),
                     "yukleme_zamani": datetime.now(ZoneInfo("Europe/Istanbul")).isoformat(timespec="seconds")})
    # Denetlenmemiş API projelerinde YouTube videoyu "gizli (kilitli)" yapabilir: kontrol et
    try:
        st = servis(k["id"]).videos().list(part="status", id=cevap["id"]).execute()["items"][0]["status"]
        is_.veri["youtube_durum"] = st
        if hemen and st.get("privacyStatus") != "public":
            log.warning("%s: YouTube videoyu %s bıraktı (denetlenmemiş API projesi kısıtı olabilir)",
                        is_.id, st.get("privacyStatus"))
    except Exception as e:
        log.warning("%s: video durumu okunamadı: %s", is_.id, e)
    from .hatirlatici import gonderim_kaydi

    gonderim_kaydi(is_, cevap["id"], zaman)  # kampanya klibiyse 30 dk gönderim takibi
    is_.durum = "yuklendi"
    is_.kaydet()
    log.info("%s yüklendi: https://youtube.com/shorts/%s, yayın: %s", is_.id, cevap["id"], zaman)


def kota_gunu(zaman: datetime | None = None) -> str:
    """YouTube API kotası Pasifik saatiyle gece yarısı sıfırlanır (TR 11:00 / yaz saatinde 10:00)."""
    return (zaman or datetime.now(ZoneInfo("UTC"))).astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat()


def kota_gunundeki_yukleme(simdi: datetime | None = None, grup: str | None = None) -> int:
    """Bu kota gününde yapılan yükleme sayısı (her yükleme 1.600 birim; 10.000 birimle ~6).
    grup verilirse yalnız o Google projesini kullanan kanallar sayılır."""
    gun = kota_gunu(simdi)
    sayi = 0
    for i in isler("yuklendi"):
        if grup and kota_grubu(i.kanal) != grup:
            continue
        zaman = i.veri.get("yukleme_zamani")
        if not zaman:
            continue
        try:
            if kota_gunu(datetime.fromisoformat(zaman)) == gun:
                sayi += 1
        except ValueError:
            continue
    return sayi


def yukle_hepsi(gunluk_sinir: int | None = None) -> int:
    """Onaylanmış tüm videoları yükler. Kota dolarsa durur, kalanı sonraki çalışmaya kalır."""
    from googleapiclient.errors import HttpError

    sinir = gunluk_sinir or int(ortam("GUNLUK_YUKLEME_SINIRI", "6"))
    yuklenen: dict[str, int] = {}  # her Google projesinin kendi kotası var
    dolu: set[str] = set()
    sayac = 0
    for i in isler("onaylandi"):
        grup = kota_grubu(i.kanal)
        if grup not in yuklenen:
            yuklenen[grup] = kota_gunundeki_yukleme(grup=grup)
        if grup in dolu or yuklenen[grup] >= sinir:
            if grup not in dolu:
                log.info("Günlük yükleme sınırı (%d) doldu (%s)", sinir, grup)
            dolu.add(grup)
            continue
        try:
            from ..olay import calisiyor

            with calisiyor("yukleyici", "YouTube'a yüklüyor", yz="youtube", is_id=i.id, kanal=i.kanal,
                           baslik=i.veri.get("baslik")):
                yukle_bir(i, kanal(i.kanal))
            sayac += 1
            yuklenen[grup] += 1
        except HttpError as e:
            if "quota" in str(e).lower():
                log.warning("YouTube kotası doldu (%s), yarın devam edilecek", grup)
                dolu.add(grup)
                continue
            i.hatalar.append(f"yükleme: {e}")
            i.kaydet()
            log.error("%s yüklenemedi: %s", i.id, e)
        except RuntimeError as e:
            log.error("%s yüklenemedi: %s", i.id, e)
    return sayac
