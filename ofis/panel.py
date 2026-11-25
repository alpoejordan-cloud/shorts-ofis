"""Ofis kontrol paneli: bütün sistemi tek ekrandan izle ve yönet.

Aç:  python -m ofis panel      (ya da panel.bat'a çift tıkla)  ->  http://127.0.0.1:8770
Yalnızca bu bilgisayardan açılır. Anahtarlar ve şifreler panelde asla gösterilmez; sadece "var / yok" yazar.

Panel hafiftir: kendisi video üretmez, yalnız dosyaları okur. Ajanlar çalışırken yazdıkları canlı olayları
(veri/olaylar/) ve iş kayıtlarını (veri/isler/) gösterir.
"""
from __future__ import annotations

import importlib.util
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from . import olay
from .cekirdek import AYAR, GUNLUK, ISLER, KOK, RAPORLAR, SESLER, TOKENLAR, VERI, Is, isler, kanallar, ortam, yaml_oku

JETON = secrets.token_urlsafe(24)  # panel her açılışta yeni jeton üretir; başka site panelde işlem yapamaz
SAYFA = Path(__file__).with_name("panel.html")

# ---- Ofisin kadrosu: masalar ----
AJANLAR: list[dict[str, Any]] = [
    {"id": "mudur", "ad": "Müdür", "ikon": "M", "rol": "İşi ajandan ajana taşır, hatada tekrar dener, yarım işi sürdürür",
     "arac": ["Görev Zamanlayıcı"]},
    {"id": "trend", "ad": "Trend Avcısı", "ikon": "T", "rol": "Haber akışlarını (RSS) tarar, en çok izlenecek konuyu seçer",
     "arac": ["ollama", "gemini"]},
    {"id": "senarist", "ad": "Senarist", "ikon": "S", "rol": "Gerçek haber metninden senaryo, kanca ve başlık yazar",
     "arac": ["ollama", "gemini"]},
    {"id": "seslendirme", "ad": "Seslendirme", "ikon": "V", "rol": "Metni seslendirir, kelime kelime altyazı zamanlar",
     "arac": ["kokoro", "piper", "whisper"]},
    {"id": "gorsel", "ad": "Görsel", "ikon": "G", "rol": "Lisanslı görsel/video ve izinli klipleri toplar",
     "arac": ["Openverse", "Wikimedia", "Pexels"]},
    {"id": "kurgu", "ad": "Kurgu", "ikon": "K", "rol": "Kesme, geçiş, altyazı, müzik ve renkle videoyu kurgular",
     "arac": ["ffmpeg", "OpenCV"]},
    {"id": "kalite", "ad": "Kalite Kontrol", "ikon": "Q", "rol": "Ses seviyesi, dil, sayı/isim doğruluğu; geçmeyeni masaya atar",
     "arac": ["gemini"]},
    {"id": "yukleyici", "ad": "Yükleyici", "ikon": "Y", "rol": "SEO başlık/etiket hazırlar, videoyu saatine zamanlar",
     "arac": ["youtube"]},
    {"id": "analist", "ad": "Analist", "ikon": "A", "rol": "İzlenmeleri toplar, neyin tuttuğunu öğrenir, rapor yazar",
     "arac": ["youtube"]},
    {"id": "hatirlatici", "ad": "Kampanya Hatırlatıcı", "ikon": "H", "rol": "Yayına giren kampanya klibi için 30 dk uyarısı",
     "arac": []},
]
AJAN_IDLERI = {a["id"] for a in AJANLAR}

YAPAY_ZEKALAR: list[dict[str, Any]] = [
    {"id": "ollama", "ad": "Ollama", "gorev": "Ana yazar: trend fikirleri ve senaryolar", "nerede": "Bu bilgisayarda"},
    {"id": "gemini", "ad": "Google Gemini", "gorev": "Eleştirmen: konu puanı, kanca, başlık, SEO, denetim",
     "nerede": "Google (ücretsiz katman)"},
    {"id": "kokoro", "ad": "Kokoro-82M", "gorev": "İngilizce seslendirme (Tech in 30, Open World Insider)",
     "nerede": "Bu bilgisayarda"},
    {"id": "piper", "ad": "Piper", "gorev": "Türkçe seslendirme ve İngilizce yedek ses", "nerede": "Bu bilgisayarda"},
    {"id": "whisper", "ad": "faster-whisper", "gorev": "Sesi dinler, kelime kelime altyazı zamanı çıkarır",
     "nerede": "Bu bilgisayarda"},
]
ARACLAR = {"ffmpeg": "FFmpeg (kurgu)", "youtube": "YouTube API"}

ASAMALAR = ["fikir", "senaryo", "ses", "gorsel", "video", "onay_bekliyor", "onaylandi", "yuklendi"]
ASAMA_ADLARI = {"fikir": "Fikir", "senaryo": "Senaryo hazır", "ses": "Ses hazır", "gorsel": "Görseller hazır",
                "video": "Video hazır", "onay_bekliyor": "Onay masasında", "onaylandi": "Yüklemeye hazır",
                "yuklendi": "YouTube'da", "reddedildi": "Reddedildi", "hata": "Hata"}

KOMUTLAR = {"gunluk": "Günlük çalışma (üret + yükle)", "uret": "Sadece üret", "yukle": "Onaylıları yükle",
            "rapor": "Haftalık raporu yaz"}


# ---- küçük önbellek: panel dosyaları her saniye baştan okumasın ----
_onbellek: dict[str, tuple[float, Any]] = {}
_ob_kilit = threading.Lock()


def onbellekli(anahtar: str, sure: float, uret: Callable[[], Any]) -> Any:
    with _ob_kilit:
        kayit = _onbellek.get(anahtar)
        if kayit and time.time() - kayit[0] < sure:
            return kayit[1]
    deger = uret()
    with _ob_kilit:
        _onbellek[anahtar] = (time.time(), deger)
    return deger


def onbellek_sil(*anahtarlar: str) -> None:
    with _ob_kilit:
        for a in anahtarlar or list(_onbellek):
            _onbellek.pop(a, None)


def _isler_imzasi() -> tuple[int, int]:
    try:
        st = ISLER.stat()
        return st.st_mtime_ns, sum(1 for _ in ISLER.glob("*.json"))
    except OSError:
        return 0, 0


_is_ob: dict[str, Any] = {"imza": None, "veri": []}


def tum_isler() -> list[Is]:
    """İş kayıtları; klasör değişmediyse önceki okuma kullanılır (2 sn'de bir okunsa da hafif)."""
    imza = _isler_imzasi()
    if imza != _is_ob["imza"] or time.time() - _is_ob.get("z", 0) > 15:
        _is_ob.update(imza=imza, veri=isler(), z=time.time())
    return _is_ob["veri"]


def _kisa(metin: Any, n: int = 240) -> str:
    metin = str(metin or "")
    return metin if len(metin) <= n else metin[: n - 1] + "…"


def is_ozeti(i: Is, ayrinti: bool = False) -> dict[str, Any]:
    v = i.veri
    d = {
        "id": i.id, "kanal": i.kanal, "durum": i.durum, "asama": ASAMA_ADLARI.get(i.durum, i.durum),
        "baslik": (v.get("seo") or {}).get("title") or v.get("baslik") or v.get("konu") or i.id,
        "konu": _kisa(v.get("konu"), 160), "olusturma": i.olusturma, "guncelleme": i.guncelleme,
        "mod": v.get("mod"), "format": v.get("format"), "sure": v.get("sure"),
        "youtube_id": v.get("youtube_id"), "yayin_zamani": v.get("yayin_zamani"),
        "istatistik": v.get("istatistik"), "kalite": v.get("kalite_sorunlari") or [],
        "hatalar": [_kisa(h, 300) for h in i.hatalar[-3:]], "deneme": i.deneme,
        "red_nedeni": v.get("red_nedeni"), "kampanya": bool(v.get("kampanya")),
        "kaynak": (v.get("kaynaklar") or [None])[0] or v.get("link"),
        "video_var": bool(v.get("video")),
        "gemini": _gemini_notu(v.get("gemini_denetim")),
        "gizlilik": (v.get("youtube_durum") or {}).get("privacyStatus"),
        "gonderim": v.get("kampanya_gonderim"),
    }
    if ayrinti:
        d.update(senaryo=v.get("senaryo"), aciklama=_kisa(v.get("aciklama"), 2500), lisanslar=v.get("lisanslar") or [],
                 kanca=v.get("kanca_metni"), etiketler=(v.get("seo") or {}).get("tags"))
    return d


def _gemini_notu(den: Any) -> dict[str, Any] | None:
    if not isinstance(den, dict):
        return None
    return {"onay": den.get("onay"), "sorunlar": [_kisa(s, 200) for s in (den.get("sorunlar") or [])[:4]]}


# ---- canlı durum ----
def _bugun_olaylari() -> list[dict[str, Any]]:
    return olay.oku(son=1500)


def canli() -> dict[str, Any]:
    olaylar = _bugun_olaylari()
    acik = olay.acik_isler(olaylar)
    son_olay: dict[str, dict[str, Any]] = {}
    sayim: dict[str, Counter] = defaultdict(Counter)
    yz_sure: dict[str, list[float]] = defaultdict(list)
    for o in olaylar:
        a = o.get("ajan") or "ofis"
        son_olay[a] = o
        if o["tur"] == "bitir":
            sayim[a]["is"] += 1
        if o["tur"] == "hata":
            sayim[a]["hata"] += 1
        y = o.get("yz")
        if y and o["tur"] in ("bitir", "hata") and o.get("kimlik"):
            sayim["yz:" + y][o["tur"]] += 1
            if o["tur"] == "bitir" and o.get("sure") is not None:
                yz_sure[y].append(float(o["sure"]))
    ajanlar = []
    for a in AJANLAR:
        simdi = [o for o in acik if o.get("ajan") == a["id"]]
        ajanlar.append({**a, "durum": "calisiyor" if simdi else "bosta", "simdi": simdi[-1] if simdi else None,
                        "son": son_olay.get(a["id"]), "bugun": dict(sayim[a["id"]])})
    yzler = []
    for y in YAPAY_ZEKALAR:
        simdi = [o for o in acik if o.get("yz") == y["id"]]
        s = yz_sure.get(y["id"]) or []
        yzler.append({**y, "durum": "calisiyor" if simdi else "bekliyor", "simdi": simdi,
                      "bugun_cagri": sayim["yz:" + y["id"]].get("bitir", 0),
                      "bugun_hata": sayim["yz:" + y["id"]].get("hata", 0),
                      "ort_sure": round(sum(s) / len(s), 1) if s else None})
    ofis_calisma = next((o for o in acik if o.get("ajan") == "mudur" and o.get("komut")), None)
    akis = [o for o in olaylar if not (o["tur"] == "bitir" and o.get("yz") and (o.get("sure") or 0) < 1)][-150:]
    return {"simdi": datetime.now().isoformat(timespec="seconds"), "acik": acik, "ajanlar": ajanlar,
            "yapay_zekalar": yzler, "ofis": ofis_calisma, "akis": list(reversed(akis))}


# ---- işler, takvim, rapor ----
def is_listesi() -> dict[str, Any]:
    tum = tum_isler()
    hat: dict[str, Counter] = defaultdict(Counter)
    for i in tum:
        hat[i.kanal][i.durum] += 1
    sirali = sorted(tum, key=lambda i: i.guncelleme, reverse=True)
    aktifler = [is_ozeti(i) for i in sirali if i.durum not in ("yuklendi", "reddedildi", "hata")]
    onay = [is_ozeti(i, ayrinti=True) for i in sirali if i.durum == "onay_bekliyor"]
    hatalar = [is_ozeti(i) for i in sirali if i.durum == "hata"][:40]
    yuklenen = [is_ozeti(i) for i in sirali if i.durum == "yuklendi"]
    reddedilen = [is_ozeti(i) for i in sirali if i.durum == "reddedildi"][:30]
    simdi = datetime.now().astimezone()
    zamanli, yayinda = [], []
    for d in yuklenen:
        try:
            z = datetime.fromisoformat(d["yayin_zamani"]) if d["yayin_zamani"] else None
        except ValueError:
            z = None
        (zamanli if z and z > simdi else yayinda).append(d)
    zamanli.sort(key=lambda d: d["yayin_zamani"])
    from .ajanlar.hatirlatici import bekleyenler

    try:
        gonderim = [is_ozeti(i) for i in bekleyenler()]
    except Exception:
        gonderim = []
    gunluk: dict[str, Counter] = defaultdict(Counter)
    for i in tum:
        gunluk[i.olusturma[:10]]["uretilen"] += 1
        if i.durum == "yuklendi" and i.veri.get("yayin_zamani"):
            gunluk[str(i.veri["yayin_zamani"])[:10]]["yayin"] += 1
    son14 = [(datetime.now().date() - timedelta(days=n)).isoformat() for n in range(13, -1, -1)]
    return {
        "hat": {k: dict(v) for k, v in hat.items()}, "aktif": aktifler, "onay": onay, "hatalar": hatalar,
        "zamanli": zamanli, "yayinda": yayinda[:60], "reddedilen": reddedilen, "gonderim": gonderim,
        "gunluk": [{"gun": g, **gunluk.get(g, {})} for g in son14], "toplam": len(tum),
    }


def rapor() -> dict[str, Any]:
    tum = tum_isler()
    kanal_ozet = []
    for k in kanallar(sadece_aktif=False):
        olculen = [i for i in tum if i.kanal == k["id"] and (i.veri.get("istatistik") or {}).get("izlenme") is not None]
        izl = [i.veri["istatistik"]["izlenme"] for i in olculen]
        kanal_ozet.append({
            "id": k["id"], "ad": k.get("ad") or k["id"], "video": len(olculen), "izlenme": sum(izl),
            "ortalama": round(sum(izl) / len(izl)) if izl else 0,
            "begeni": sum(i.veri["istatistik"].get("begeni", 0) for i in olculen),
            "en_iyi": [{"baslik": is_ozeti(i)["baslik"], "izlenme": i.veri["istatistik"]["izlenme"],
                        "youtube_id": i.veri.get("youtube_id")}
                       for i in sorted(olculen, key=lambda i: -i.veri["istatistik"]["izlenme"])[:5]],
            "son_olcum": max((i.veri["istatistik"].get("tarih") or "" for i in olculen), default=None),
        })
    dosyalar = sorted(RAPORLAR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    haftalik = next((p for p in dosyalar if not p.name.startswith("gunluk_")), None)
    gunluk = next((p for p in dosyalar if p.name.startswith("gunluk_")), None)
    oku = lambda p: {"ad": p.name, "metin": p.read_text(encoding="utf-8")[:12000]} if p else None  # noqa: E731
    return {"kanallar": kanal_ozet, "haftalik": oku(haftalik), "gunluk": oku(gunluk)}


# ---- sistem: yapay zekaların ve araçların hazır olup olmadığı ----
def _ollama() -> dict[str, Any]:
    import requests

    from .yapay_zeka import _adres, model_adi

    d: dict[str, Any] = {"model": model_adi(), "hazir": False, "bellekte": []}
    try:
        r = requests.get(f"{_adres()}/api/tags", timeout=2)
        r.raise_for_status()
        modeller = [m["name"] for m in r.json().get("models", [])]
        istenen = model_adi() if ":" in model_adi() else f"{model_adi()}:latest"
        d["hazir"] = istenen in modeller
        d["not"] = "hazır" if d["hazir"] else f"model yüklü değil (ollama pull {model_adi()})"
        try:
            ps = requests.get(f"{_adres()}/api/ps", timeout=2).json().get("models", [])
            d["bellekte"] = [{"ad": m.get("name"), "gb": round((m.get("size") or 0) / 1e9, 1)} for m in ps]
        except Exception:
            pass
    except Exception:
        d["not"] = "Ollama kapalı (iş gelince otomatik açılmazsa Ollama uygulamasını aç)"
    return d


def _paket(modul: str) -> bool:
    try:
        return importlib.util.find_spec(modul) is not None
    except (ImportError, ValueError):
        return False


def sistem() -> dict[str, Any]:
    from . import gemini

    yz: dict[str, Any] = {"ollama": onbellekli("ollama", 8, _ollama)}
    anahtar = bool(ortam("GEMINI_API_ANAHTARI", "").strip())
    sayi, sinir = gemini.bugunku_istek(), gemini.gunluk_sinir()
    yz["gemini"] = {"model": gemini.model_adi(), "hazir": anahtar and _paket("google.genai") and sayi < sinir,
                    "anahtar": anahtar, "bugun": sayi, "sinir": sinir,
                    "not": ("anahtar yok: Ollama tek başına çalışır" if not anahtar else
                            "paket eksik: pip install -r requirements.txt" if not _paket("google.genai") else
                            "bugünlük sınır doldu, yarın devam" if sayi >= sinir else "hazır")}
    ses_ids = [s for k in kanallar() for s in (k.get("ses"), k.get("ses_yedek")) if s]
    kokoro_var = (SESLER / "kokoro-v1.0.int8.onnx").exists() and _paket("kokoro_onnx")
    kokoro_sesler = sorted({s.split(":", 1)[1] for s in ses_ids if str(s).startswith("kokoro:")})
    piper_sesler = sorted({s for s in ses_ids if not str(s).startswith("kokoro:")})
    piper_tamam = _paket("piper") and all((SESLER / f"{s}.onnx").exists() for s in piper_sesler)
    yz["kokoro"] = {"model": "kokoro-v1.0 (int8) · " + ", ".join(kokoro_sesler), "hazir": kokoro_var,
                    "not": "hazır" if kokoro_var else "eksik: python -m ofis sesleri-indir (Piper yedek ses devreye girer)"}
    yz["piper"] = {"model": ", ".join(piper_sesler) or "—", "hazir": piper_tamam,
                   "not": "hazır" if piper_tamam else "eksik ses: python -m ofis sesleri-indir"}
    yz["whisper"] = {"model": "small (int8, CPU)", "hazir": _paket("faster_whisper"),
                     "not": "hazır" if _paket("faster_whisper") else "paket eksik: pip install -r requirements.txt"}
    araclar = {
        "FFmpeg": bool(shutil.which("ffmpeg")), "OpenCV (yüz kamerası)": _paket("cv2"),
        "YouTube uygulama dosyası (client_secret.json)": (AYAR / "client_secret.json").exists(),
        "Gemini anahtarı": anahtar, "Pexels anahtarı": bool(ortam("PEXELS_API_ANAHTARI")),
        "Pixabay anahtarı": bool(ortam("PIXABAY_API_ANAHTARI")),
        "YouTube API anahtarı (trend)": bool(ortam("YOUTUBE_API_ANAHTARI")),
    }
    kanal_listesi = []
    for k in kanallar(sadece_aktif=False):
        if not k.get("ad") and not k.get("aktif"):
            continue
        kanal_listesi.append({
            "id": k["id"], "ad": k.get("ad") or k["id"], "aktif": bool(k.get("aktif", True)),
            "otomatik_onay": bool(k.get("otomatik_onay")), "gunluk_video": k.get("gunluk_video", 1),
            "dil": k.get("dil"), "nis": k.get("nis"), "ses": k.get("ses"),
            "yayin_saatleri": k.get("yayin_saatleri") or [],
            "bugun_saatleri": (k.get("gun_yayin_saatleri") or {}).get(datetime.now().date().isoformat()),
            "bagli": (TOKENLAR / f"{k['id']}.json").exists(), "klip_orani": k.get("klip_orani"),
        })
    return {"yz": yz, "araclar": araclar, "kanallar": kanal_listesi, "zamanlayici": onbellekli("zaman", 60, zamanlayici),
            "komutlar": KOMUTLAR, "platform": sys.platform, "kok": str(KOK)}


def zamanlayici() -> dict[str, Any]:
    """Windows Görev Zamanlayıcı'daki ShortsOfis görevleri (sadece okuma; aç/kapat ayrı)."""
    if sys.platform != "win32":
        return {"destek": False, "gorevler": []}
    ps = (
        "Get-ScheduledTask -TaskName 'ShortsOfis*' -ErrorAction SilentlyContinue | ForEach-Object { "
        "$i = $_ | Get-ScheduledTaskInfo; [pscustomobject]@{ ad = $_.TaskName; durum = [string]$_.State; "
        "sonraki = $(if ($i.NextRunTime) { $i.NextRunTime.ToString('yyyy-MM-dd HH:mm') } else { '' }); "
        "son = $(if ($i.LastRunTime -and $i.LastRunTime.Year -gt 2000) { $i.LastRunTime.ToString('yyyy-MM-dd HH:mm') } else { '' }); "
        "sonuc = $i.LastTaskResult } } | ConvertTo-Json -Compress"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=25,
                           creationflags=0x08000000)
        veri = json.loads(r.stdout or "[]")
        gorevler = veri if isinstance(veri, list) else [veri]
    except Exception as e:
        return {"destek": True, "gorevler": [], "hata": str(e)[:200]}
    return {"destek": True, "gorevler": sorted(gorevler, key=lambda g: g.get("sonraki") or "9")}


def gunluk_kuyrugu(satir: int = 250) -> dict[str, Any]:
    yol = GUNLUK / f"{datetime.now():%Y-%m-%d}.log"
    if not yol.exists():
        dosyalar = sorted(GUNLUK.glob("*.log"))
        yol = dosyalar[-1] if dosyalar else yol
    if not yol.exists():
        return {"ad": None, "satirlar": []}
    with open(yol, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - satir * 300))
        satirlar = f.read().decode("utf-8", errors="ignore").splitlines()[-satir:]
    return {"ad": yol.name, "satirlar": satirlar}


# ---- eylemler (paneldeki düğmeler) ----
def calisan_komut() -> dict[str, Any] | None:
    return next((o for o in olay.acik_isler(_bugun_olaylari()) if o.get("ajan") == "mudur" and o.get("komut")), None)


def komut_baslat(arglar: list[str], ad: str) -> str:
    (GUNLUK / "panel").mkdir(parents=True, exist_ok=True)
    cikti = open(GUNLUK / "panel" / f"{datetime.now():%Y%m%d-%H%M%S}-{ad}.log", "w", encoding="utf-8")
    bayrak = 0x08000000 | 0x00000200 if sys.platform == "win32" else 0  # pencere açma + panelden bağımsız
    subprocess.Popen([sys.executable, "-m", "ofis", *arglar], cwd=str(KOK), stdout=cikti, stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, creationflags=bayrak, start_new_session=sys.platform != "win32")
    olay.yaz("bilgi", f"Panelden başlatıldı: {' '.join(arglar)}", ajan="panel")
    return f"Başladı: {KOMUTLAR.get(arglar[0], ' '.join(arglar))}. İlerlemeyi Canlı Ofis ekranından izle."


def kanal_ayari_yaz(kanal_id: str, alan: str, deger: Any) -> None:
    """config/kanallar.yaml'da yalnızca tek satırı değiştirir; yorumlar ve düzen korunur."""
    import yaml

    yol = AYAR / "kanallar.yaml"
    satirlar = yol.read_text(encoding="utf-8").splitlines(keepends=True)
    bas = next((n for n, s in enumerate(satirlar) if re.match(rf"\s*-\s*id:\s*{re.escape(kanal_id)}\s*(#.*)?$", s)), None)
    if bas is None:
        raise ValueError("kanal bulunamadı")
    son = next((n for n in range(bas + 1, len(satirlar)) if re.match(r"\s*-\s*id:", satirlar[n])), len(satirlar))
    girinti = " " * satirlar[bas].index("id:")
    metin = "true" if deger is True else "false" if deger is False else str(int(deger))
    not_ = f"  # panelden değiştirildi {datetime.now():%Y-%m-%d %H:%M}"
    desen = re.compile(rf"^{girinti}{re.escape(alan)}:\s*[^#\n]*?(\s*#.*)?(\r?\n)?$")
    for n in range(bas + 1, son):
        m = desen.match(satirlar[n])
        if m:
            satirlar[n] = f"{girinti}{alan}: {metin}{not_}{m.group(2) or ''}"
            break
    else:
        satirlar.insert(bas + 1, f"{girinti}{alan}: {metin}{not_}\n")
    yeni = "".join(satirlar)
    kontrol = {k["id"]: k for k in (yaml.safe_load(yeni) or {}).get("kanallar", [])}
    if kontrol.get(kanal_id, {}).get(alan) != deger:
        raise ValueError("ayar dosyası beklenmedik biçimde, değiştirilmedi")
    gecici = yol.with_suffix(".yaml.tmp")
    gecici.write_text(yeni, encoding="utf-8")
    shutil.copy2(yol, yol.with_suffix(".yaml.yedek"))
    gecici.replace(yol)
    olay.yaz("bilgi", f"{kanal_id}: {alan} = {metin} (panelden)", ajan="panel", kanal=kanal_id)


def tekrar_dene(is_id: str) -> str:
    i = Is.yukle(is_id)
    if i.durum != "hata":
        return "Bu iş hata durumunda değil."
    asama = "fikir"
    for h in reversed(i.hatalar):
        m = re.search(r"\d{2}\.\d{2} \d{2}:\d{2} (\w+):", h)
        if m and m.group(1) in ASAMALAR:
            asama = m.group(1)
            break
    i.durum, i.deneme = asama, 0
    i.kaydet()
    olay.yaz("bilgi", f"{is_id}: tekrar denenecek ({asama} aşamasından)", ajan="panel", is_id=is_id, kanal=i.kanal)
    return f"Sıraya alındı: bir sonraki çalışmada {ASAMA_ADLARI.get(asama, asama)} aşamasından devam edecek."


def eylem(g: dict[str, Any]) -> str:
    from .ajanlar import onay

    ne = g.get("eylem")
    is_id = str(g.get("id") or "")
    if is_id and not re.fullmatch(r"[\w\-]+", is_id):
        raise ValueError("geçersiz iş")
    if ne == "onayla":
        onay.onayla(is_id)
        return "Onaylandı: sıradaki yüklemede saatine zamanlanacak."
    if ne == "reddet":
        onay.reddet(is_id, str(g.get("neden") or "")[:300])
        return "Reddedildi."
    if ne == "hemen_yayinla":
        i = Is.yukle(is_id)
        if i.durum not in ("onay_bekliyor", "onaylandi"):
            return "Bu video yayınlanabilir durumda değil."
        return komut_baslat(["yayinla", is_id], "yayinla")
    if ne == "gonderildi":
        from .ajanlar.hatirlatici import gonderildi

        gonderildi(is_id)
        return "Content Rewards gönderimi kaydedildi."
    if ne == "tekrar_dene":
        return tekrar_dene(is_id)
    if ne == "ayar":
        alan = g.get("alan")
        if alan in ("aktif", "otomatik_onay"):
            deger: Any = bool(g.get("deger"))
        elif alan == "gunluk_video":
            deger = max(0, min(6, int(g.get("deger"))))
        else:
            raise ValueError("bu ayar panelden değiştirilemez")
        kanal_ayari_yaz(str(g.get("kanal")), alan, deger)
        return "Kaydedildi. Bir sonraki çalışmada geçerli."
    if ne == "calistir":
        komut = g.get("komut")
        if komut not in KOMUTLAR:
            raise ValueError("bilinmeyen komut")
        c = calisan_komut()
        if c and komut != "rapor":
            return f"Ofis zaten çalışıyor ({c.get('mesaj')}). Bitince tekrar dene."
        return komut_baslat([komut], komut)
    if ne == "zamanlayici":
        if sys.platform != "win32":
            return "Görev Zamanlayıcı sadece Windows'ta."
        ad = str(g.get("gorev") or "")
        if not re.fullmatch(r"ShortsOfis - [\w ]+", ad):
            raise ValueError("geçersiz görev")
        komut = "Enable-ScheduledTask" if g.get("ac") else "Disable-ScheduledTask"
        r = subprocess.run(["powershell", "-NoProfile", "-Command", f"{komut} -TaskName '{ad}' | Out-Null"],
                           capture_output=True, text=True, timeout=30, creationflags=0x08000000)
        onbellek_sil("zaman")
        if r.returncode:
            return "Değiştirilemedi: " + (r.stderr.strip()[:200] or "yetki gerekebilir")
        olay.yaz("bilgi", f"Zamanlayıcı: {ad} {'açıldı' if g.get('ac') else 'kapatıldı'}", ajan="panel")
        return "Zamanlayıcı güncellendi."
    raise ValueError("bilinmeyen işlem")


# ---- sunucu ----
def _video_yolu(is_id: str) -> Path | None:
    if not re.fullmatch(r"[\w\-]+", is_id):
        return None
    try:
        i = Is.yukle(is_id)
    except (FileNotFoundError, ValueError, TypeError):
        return None
    yol = i.klasor / i.veri.get("video", "video.mp4")
    return yol if yol.exists() else None


class Isleyici(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # sessiz
        pass

    def _gonder(self, kod: int, govde: bytes, tur: str, ek: dict[str, str] | None = None) -> None:
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (ek or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(govde)

    def _json(self, veri: Any, kod: int = 200) -> None:
        self._gonder(kod, json.dumps(veri, ensure_ascii=False, default=str).encode("utf-8"),
                     "application/json; charset=utf-8")

    def _yerel_mi(self) -> bool:
        """DNS yeniden bağlama saldırısına karşı: yalnızca bu bilgisayarın adresiyle gelen istekler."""
        if ortam("PANEL_ADRESI", "127.0.0.1") != "127.0.0.1":
            return True
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in ("127.0.0.1", "localhost", "::1")

    def do_GET(self):
        if not self._yerel_mi():
            return self._gonder(403, b"yasak", "text/plain")
        yol = urlparse(self.path).path
        try:
            if yol in ("/", "/index.html"):
                html = SAYFA.read_text(encoding="utf-8").replace("__JETON__", JETON)
                return self._gonder(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if yol == "/api/canli":
                return self._json(canli())
            if yol == "/api/isler":
                return self._json(onbellekli("isler", 3, is_listesi))
            if yol == "/api/sistem":
                return self._json(onbellekli("sistem", 10, sistem))
            if yol == "/api/rapor":
                return self._json(onbellekli("rapor", 20, rapor))
            if yol == "/api/gunluk":
                return self._json(gunluk_kuyrugu())
            if yol.startswith("/video/"):
                return self._video(yol.split("/")[-1])
        except Exception as e:
            return self._json({"hata": str(e)[:300]}, 500)
        self._gonder(404, b"yok", "text/plain")

    do_HEAD = do_GET

    def _video(self, is_id: str) -> None:
        dosya = _video_yolu(is_id)
        if not dosya:
            return self._gonder(404, b"video yok", "text/plain")
        boyut = dosya.stat().st_size
        bas, son, kod = 0, boyut - 1, 200
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                bas = int(m.group(1))
                son = min(int(m.group(2)) if m.group(2) else boyut - 1, boyut - 1)
            else:
                bas = max(0, boyut - int(m.group(2)))
            kod = 206
        uzunluk = max(0, son - bas + 1)
        self.send_response(kod)
        self.send_header("Content-Type", mimetypes.guess_type(dosya.name)[0] or "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(uzunluk))
        if kod == 206:
            self.send_header("Content-Range", f"bytes {bas}-{son}/{boyut}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(dosya, "rb") as f:
            f.seek(bas)
            kalan = uzunluk
            while kalan > 0:
                parca = f.read(min(1 << 20, kalan))
                if not parca:
                    break
                try:
                    self.wfile.write(parca)
                except (BrokenPipeError, ConnectionResetError):
                    return
                kalan -= len(parca)

    def do_POST(self):
        if not self._yerel_mi() or self.headers.get("X-Panel-Jeton") != JETON:
            return self._json({"hata": "yetkisiz istek (sayfayı yenile)"}, 403)
        if urlparse(self.path).path != "/api/eylem":
            return self._json({"hata": "yok"}, 404)
        try:
            uzunluk = min(int(self.headers.get("Content-Length", 0)), 20000)
            g = json.loads(self.rfile.read(uzunluk).decode("utf-8") or "{}")
            mesaj = eylem(g)
            onbellek_sil("isler", "sistem", "rapor")
            _is_ob["imza"] = None
            return self._json({"tamam": True, "mesaj": mesaj})
        except Exception as e:
            return self._json({"tamam": False, "mesaj": f"Olmadı: {str(e)[:300]}"}, 400)


def calistir(port: int | None = None, tarayici: bool = True) -> None:
    adres = ortam("PANEL_ADRESI", "127.0.0.1")
    port = port or int(ortam("PANEL_PORTU", "8770"))
    sunucu = ThreadingHTTPServer((adres, port), Isleyici)
    sunucu.daemon_threads = True
    url = f"http://127.0.0.1:{port}"
    print(f"Ofis paneli açık: {url}   (kapatmak için bu pencerede Ctrl+C)")
    if tarayici:
        import webbrowser

        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        pass
