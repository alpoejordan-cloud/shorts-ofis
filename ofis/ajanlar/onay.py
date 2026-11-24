"""Onay masası: hazır videoları tarayıcıda gösterir; sen 'Onayla' ya da 'Reddet' dersin.
Adres: http://127.0.0.1:8765 (telefondan aynı ağda bakmak için ONAY_ADRESI=0.0.0.0 yap)."""
from __future__ import annotations

import html
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ..cekirdek import Is, gunluk_al, isler, ortam

log = gunluk_al("onay")


def onayla(is_id: str) -> None:
    i = Is.yukle(is_id)
    if i.durum == "onay_bekliyor":
        i.durum = "onaylandi"
        i.kaydet()
        log.info("%s onaylandı", is_id)


def reddet(is_id: str, neden: str = "") -> None:
    i = Is.yukle(is_id)
    if i.durum == "onay_bekliyor":
        i.durum = "reddedildi"
        i.veri["red_nedeni"] = neden
        i.kaydet()
        log.info("%s reddedildi: %s", is_id, neden)


def gonderim_bolumu() -> str:
    """Yayına giren kampanya klipleri: 30 dk içinde Content Rewards'a gönderilmeli."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from .hatirlatici import SURE, bekleyenler

    e = html.escape
    simdi = datetime.now(ZoneInfo("Europe/Istanbul"))
    satirlar = []
    for i in bekleyenler():
        g = i.veri["kampanya_gonderim"]
        yayin = datetime.fromisoformat(g["yayin"])
        if simdi < yayin:
            durum = f"Yayın: {yayin:%d.%m %H:%M}. O saatten sonra 30 dk içinde gönder."
            sinif = "bekle"
        else:
            kalan = int((yayin + SURE - simdi).total_seconds() // 60)
            durum = f"ŞİMDİ GÖNDER: {max(kalan, 0)} dk kaldı"
            sinif = "acil"
        satirlar.append(f"""
<div class="gonder {sinif}"><b>{e(durum)}</b><br>{e(i.veri.get('baslik', ''))}<br>
  Video linki: <code>{e(g['link'])}</code><br>
  <a href="{e(g['kampanya'])}" target="_blank">Kampanya sayfasını aç (Submit clip)</a>
  <form method="post" action="/karar" style="display:inline">
    <input type="hidden" name="id" value="{e(i.id)}">
    <button name="karar" value="gonderildi" class="onay">Gönderdim</button>
  </form></div>""")
    if not satirlar:
        return ""
    return "<h1>Content Rewards'a gönderilecekler</h1>" + "".join(satirlar)


def sayfa() -> str:
    bekleyen = isler("onay_bekliyor")
    kartlar = []
    for i in bekleyen:
        v = i.veri
        e = html.escape
        kartlar.append(f"""
<article>
  <video src="/video/{e(i.id)}" controls preload="metadata"></video>
  <div class="bilgi">
    <small>{e(i.kanal)} · {e(v.get('format', ''))} · {v.get('sure', '?')} sn</small>
    <h2>{e(v.get('baslik', ''))}</h2>
    <p>{e(v.get('senaryo', ''))}</p>
    {('<p class="uyari">Kampanya klibi: yayına girince 30 dk içinde Content Rewards' + "'" + 'a gönderilmeli. '
      'Bilgisayar açık olsun, bildirim gelecek.</p>') if v.get('kampanya') else ''}
    <details><summary>Açıklama ve lisanslar</summary><pre>{e(v.get('aciklama', ''))}

{e(chr(10).join(v.get('lisanslar', [])))}</pre></details>
    <form method="post" action="/karar">
      <input type="hidden" name="id" value="{e(i.id)}">
      <button name="karar" value="onay" class="onay">Onayla</button>
      <input name="neden" placeholder="Red nedeni (isteğe bağlı)">
      <button name="karar" value="red" class="red">Reddet</button>
    </form>
  </div>
</article>""")
    icerik = "".join(kartlar) or "<p class='bos'>Onay bekleyen video yok.</p>"
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Onay masası</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;padding:16px;background:#f5f5f4;color:#1c1917}}
h1{{font-size:20px}} article{{display:flex;gap:16px;background:#fff;border-radius:12px;padding:16px;margin:0 0 16px;flex-wrap:wrap}}
video{{width:270px;height:480px;background:#000;border-radius:8px}} .bilgi{{flex:1;min-width:260px}}
h2{{font-size:17px;margin:4px 0}} p{{white-space:pre-wrap;line-height:1.45}} pre{{white-space:pre-wrap;font-size:12px}}
button{{border:0;border-radius:8px;padding:10px 16px;font-size:15px;cursor:pointer;margin:4px 4px 4px 0}}
.onay{{background:#16a34a;color:#fff}} .red{{background:#dc2626;color:#fff}} input{{padding:9px;border:1px solid #ccc;border-radius:8px}}
.bos{{color:#78716c}} .uyari{{background:#fef3c7;color:#78350f;padding:8px;border-radius:8px}}
.gonder{{border-radius:12px;padding:12px;margin:0 0 12px;line-height:1.6}} .acil{{background:#fee2e2;color:#7f1d1d}}
.bekle{{background:#e0f2fe;color:#0c4a6e}}
@media (prefers-color-scheme:dark){{body{{background:#1c1917;color:#f5f5f4}}article{{background:#292524}}}}
</style></head><body>{gonderim_bolumu()}<h1>Onay masası · {len(bekleyen)} video bekliyor</h1>{icerik}</body></html>"""


class Isleyici(BaseHTTPRequestHandler):
    def log_message(self, *a):  # sessiz
        pass

    def do_GET(self):
        yol = urlparse(self.path).path
        if yol.startswith("/video/"):
            is_id = yol.split("/")[-1]
            try:
                i = Is.yukle(is_id)
                dosya = i.klasor / i.veri.get("video", "video.mp4")
                veri = dosya.read_bytes()
            except (FileNotFoundError, KeyError):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(dosya.name)[0] or "video/mp4")
            self.send_header("Content-Length", str(len(veri)))
            self.end_headers()
            self.wfile.write(veri)
            return
        govde = sayfa().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self.end_headers()
        self.wfile.write(govde)

    def do_POST(self):
        uzunluk = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(uzunluk).decode("utf-8"))
        is_id = form.get("id", [""])[0]
        karar = form.get("karar", [""])[0]
        if is_id:
            if karar == "onay":
                onayla(is_id)
            elif karar == "red":
                reddet(is_id, form.get("neden", [""])[0])
            elif karar == "gonderildi":
                from .hatirlatici import gonderildi

                gonderildi(is_id)
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


def calistir() -> None:
    adres = ortam("ONAY_ADRESI", "127.0.0.1")
    port = int(ortam("ONAY_PORTU", "8765"))
    print(f"Onay masası açık: http://{'127.0.0.1' if adres == '0.0.0.0' else adres}:{port}  (kapatmak için Ctrl+C)")
    ThreadingHTTPServer((adres, port), Isleyici).serve_forever()
