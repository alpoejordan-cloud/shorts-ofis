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


def istemci_dosyasi() -> Path:
    return AYAR / "client_secret.json"


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

        if not istemci_dosyasi().exists():
            raise RuntimeError("config/client_secret.json yok. Kurulum rehberindeki Google Cloud adımını yap.")
        akis = InstalledAppFlow.from_client_secrets_file(str(istemci_dosyasi()), KAPSAMLAR)
        print(f"\nTarayıcı açılacak. '{kanal_id}' için doğru YouTube KANALINI seç.\n")
        k = akis.run_local_server(port=0, prompt="consent", access_type="offline")
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
        for s in sorted(saatler):
            sa, dk = map(int, s.split(":"))
            aday = datetime(tarih.year, tarih.month, tarih.day, sa, dk, tzinfo=bolge)
            if aday > simdi + timedelta(minutes=30) and aday not in dolu_set:
                return aday
    raise RuntimeError("60 gün içinde boş yayın saati yok")


def yukle_bir(is_: Is, k: dict[str, Any]) -> None:
    from googleapiclient.http import MediaFileUpload

    dolu = [datetime.fromisoformat(i.veri["yayin_zamani"]) for i in isler("yuklendi", k["id"])
            if i.veri.get("yayin_zamani")]
    zaman = sonraki_yayin_zamani(k, dolu)
    govde = {
        "snippet": {
            "title": is_.veri["baslik"][:100],
            "description": is_.veri["aciklama"][:4900],
            "tags": is_.veri.get("etiketler", []),
            "categoryId": str(k.get("youtube_kategori", 22)),
            "defaultLanguage": k["dil"],
            "defaultAudioLanguage": k["dil"],
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": zaman.isoformat(),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": bool(is_.veri.get("yapay_icerik", False)),
        },
    }
    medya = MediaFileUpload(str(is_.klasor / is_.veri["video"]), mimetype="video/mp4", resumable=True, chunksize=8 << 20)
    istek = servis(k["id"]).videos().insert(part="snippet,status", body=govde, media_body=medya)
    cevap = None
    while cevap is None:
        _, cevap = istek.next_chunk()
    is_.veri.update({"youtube_id": cevap["id"], "yayin_zamani": zaman.isoformat()})
    is_.durum = "yuklendi"
    is_.kaydet()
    log.info("%s yüklendi: https://youtube.com/shorts/%s, yayın: %s", is_.id, cevap["id"], zaman)


def yukle_hepsi(gunluk_sinir: int | None = None) -> int:
    """Onaylanmış tüm videoları yükler. Kota dolarsa durur, kalanı sonraki çalışmaya kalır."""
    from googleapiclient.errors import HttpError

    sinir = gunluk_sinir or int(ortam("GUNLUK_YUKLEME_SINIRI", "6"))
    bugun = datetime.now().date().isoformat()
    yuklenen = sum(1 for i in isler("yuklendi") if i.guncelleme[:10] == bugun)
    sayac = 0
    for i in isler("onaylandi"):
        if yuklenen + sayac >= sinir:
            log.info("Günlük yükleme sınırı (%d) doldu", sinir)
            break
        try:
            yukle_bir(i, kanal(i.kanal))
            sayac += 1
        except HttpError as e:
            if "quota" in str(e).lower():
                log.warning("YouTube kotası doldu, yarın devam edilecek")
                break
            i.hatalar.append(f"yükleme: {e}")
            i.kaydet()
            log.error("%s yüklenemedi: %s", i.id, e)
        except RuntimeError as e:
            log.error("%s yüklenemedi: %s", i.id, e)
    return sayac
