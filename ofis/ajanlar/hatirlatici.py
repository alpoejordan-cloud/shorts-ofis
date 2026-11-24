"""Hatırlatıcı: kampanya klipleri yayına girince 30 dakika içinde Content Rewards'a gönderilmeli.

Yükleyici, kampanya klibini yükleyince yayın saatini `kampanya_gonderim` alanına yazar.
Bu ajan (Görev Zamanlayıcı her 5 dakikada bir çalıştırır):
- yayın saati gelmiş, 30 dakikası dolmamış ve henüz bildirilmemiş videolar için Windows bildirimi gösterir,
- 30 dakikası dolan ve gönderilmeyenleri 'sure_doldu' olarak işaretler.
Gönderimi (Submit) her zaman sen yaparsın; onay masasında link ve "Gönderdim" düğmesi vardır.
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..cekirdek import Is, gunluk_al, isler

log = gunluk_al("hatirlatici")
SURE = timedelta(minutes=30)


def gonderim_kaydi(is_: Is, youtube_id: str, yayin: datetime) -> None:
    """Yükleyici çağırır: kampanya klibiyse gönderim takibini başlatır."""
    if not is_.veri.get("kampanya"):
        return
    is_.veri["kampanya_gonderim"] = {
        "durum": "bekliyor", "yayin": yayin.isoformat(), "link": f"https://youtube.com/shorts/{youtube_id}",
        "kampanya": is_.veri["kampanya"], "bildirildi": False,
    }


def bekleyenler() -> list[Is]:
    return [i for i in isler("yuklendi")
            if (i.veri.get("kampanya_gonderim") or {}).get("durum") == "bekliyor"]


def windows_bildirim(baslik: str, metin: str) -> None:
    """Windows 10/11 bildirimi (ek modül gerekmez). Olmazsa sessizce geçer."""
    temiz = lambda s: s.replace("'", "").replace("&", "ve").replace("<", "").replace(">", "")  # noqa: E731
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null;"
        "$x = New-Object Windows.Data.Xml.Dom.XmlDocument;"
        f"$x.LoadXml('<toast><visual><binding template=\"ToastGeneric\"><text>{temiz(baslik)}</text>"
        f"<text>{temiz(metin)}</text></binding></visual></toast>');"
        "$t = New-Object Windows.UI.Notifications.ToastNotification $x;"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Shorts Ofis').Show($t)"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=30)
    except Exception as e:  # bildirim olmazsa onay masasındaki uyarı yine görünür
        log.warning("Windows bildirimi gösterilemedi: %s", e)


def kontrol(simdi: datetime | None = None, bildir=windows_bildirim) -> int:
    """Yayına giren kampanya kliplerini bildirir; 30 dk dolanları işaretler. Bildirilen sayıyı döner."""
    simdi = simdi or datetime.now(ZoneInfo("Europe/Istanbul"))
    sayac = 0
    for i in bekleyenler():
        g = i.veri["kampanya_gonderim"]
        yayin = datetime.fromisoformat(g["yayin"])
        if simdi < yayin:
            continue
        if simdi > yayin + SURE:
            g["durum"] = "sure_doldu"
            i.kaydet()
            log.warning("%s: 30 dk doldu, kampanyaya gönderilmedi", i.id)
            continue
        if not g.get("bildirildi"):
            kalan = int((yayin + SURE - simdi).total_seconds() // 60)
            bildir("Content Rewards'a gönder", f"{i.veri.get('baslik', '')} yayında. {kalan} dk içinde Submit et.")
            g["bildirildi"] = True
            i.kaydet()
            sayac += 1
    return sayac


def gonderildi(is_id: str) -> None:
    i = Is.yukle(is_id)
    g: dict[str, Any] = i.veri.get("kampanya_gonderim") or {}
    if g:
        g["durum"] = "gonderildi"
        g["gonderim_zamani"] = datetime.now(ZoneInfo("Europe/Istanbul")).isoformat()
        i.kaydet()
        log.info("%s: kampanyaya gönderildi olarak işaretlendi", is_id)
