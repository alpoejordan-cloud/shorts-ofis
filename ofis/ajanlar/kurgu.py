"""Kurgu: sahneleri 9:16 dikey videoya çevirir (FFmpeg).

Profesyonel Shorts kurgusu:
- her 2-3 saniyede bir kesme; kaynak azsa aynı kaynak farklı hareket/başlangıçla yeniden kullanılır
- her sahnede hareket (Ken Burns yakınlaşma/uzaklaşma/kaydırma, videoda yavaş itme/kaydırma)
- yatay görüntülerde bulanık arka plan + ortada net görüntü
- sahneler arasında 0.3 sn xfade geçişleri ve hafif "whoosh" sesi
- renk düzeltme (kontrast, doygunluk, keskinlik, vignette)
- kelime kelime altyazı, kanca metni ve ilerleme çubuğu (altyazi.ass)
- müzik varsa seslendirme konuşurken otomatik kısılır (sidechaincompress)
"""
from __future__ import annotations

import json
import random
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..cekirdek import KOK, Is, gunluk_al, ortam

log = gunluk_al("kurgu")
G, Y, FPS = 1080, 1920, 30
OLCEK = f"scale={G}:{Y}:force_original_aspect_ratio=increase,crop={G}:{Y},setsar=1,fps={FPS}"
GECIS = 0.3
GECIS_TURLERI = ["fade", "slideleft", "slideup", "smoothleft", "circleopen", "zoomin", "smoothup", "wipeleft"]
HAREKETLER = ["yakin", "sag", "uzak", "sol", "yukari"]
VURUS_KARE = 15  # ilk sahnedeki hızlı vuruş (30 fps'te yarım saniye)
RENK = "eq=contrast=1.07:saturation=1.2:brightness=0.01,unsharp=5:5:0.45:5:5:0.0,vignette=angle=PI/5"
SES_NORMAL = "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000"
KODLA = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]


def ffmpeg_yolu() -> str:
    yol = shutil.which("ffmpeg")
    if not yol:
        raise RuntimeError("FFmpeg bulunamadı. Kurulum betiğini (scripts/kurulum.ps1) çalıştır.")
    return yol


def calistir(arglar: list[str], klasor: Path) -> None:
    # bilgisayar yavaşlamasın: ffmpeg en fazla FFMPEG_IS_PARCACIGI (varsayılan 2) çekirdek kullanır
    n = ortam("FFMPEG_IS_PARCACIGI", "2")
    arglar = [*arglar[:-1], "-threads", n, arglar[-1]] if arglar else arglar
    sonuc = subprocess.run([ffmpeg_yolu(), "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", n,
                            "-filter_complex_threads", n, *arglar],
                           cwd=klasor, capture_output=True, text=True)
    if sonuc.returncode != 0:
        raise RuntimeError(f"FFmpeg hatası: {sonuc.stderr[-1500:]}")


def olcu(yol: str) -> tuple[int, int, float]:
    """(genişlik, yükseklik, süre) — ffprobe yoksa varsayılan."""
    probe = shutil.which("ffprobe")
    if not probe:
        return 0, 0, 0.0
    s = subprocess.run([probe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:format=duration", "-of", "json", yol], capture_output=True, text=True)
    try:
        j = json.loads(s.stdout)
        akis = j["streams"][0]
        return int(akis["width"]), int(akis["height"]), float(j.get("format", {}).get("duration") or 0)
    except Exception:
        return 0, 0, 0.0


def sahne_sureleri(adet: int, toplam: float, en_az: float = 2.5) -> list[float]:
    if adet <= 0:
        return []
    adet = max(1, min(adet, int(toplam // en_az) or 1))
    return [toplam / adet] * adet


def kesim_plani(sahneler: list[dict[str, Any]], toplam: float, kesme: float = 2.4,
                tohum: str = "") -> list[dict[str, Any]]:
    """Toplam süreyi ~kesme saniyelik parçalara böler; kaynakları sırayla, farklı hareketle kullanır.
    Parça süreleri geçiş payını içerir: toplam görünen süre = toplam."""
    rnd = random.Random(tohum)
    gercek = [s for s in sahneler if s.get("tur") != "desen"]
    if len(gercek) >= 2:  # yeterli gerçek görüntü varsa düz renk sahnelerini kullanma
        sahneler = gercek
    n = max(1, round(toplam / kesme))
    gorunen = toplam / n
    plan = []
    son_hareket = None
    for i in range(n):
        sahne = sahneler[i % len(sahneler)]
        tekrar = i // len(sahneler)
        secenek = [h for h in HAREKETLER if h != son_hareket]
        hareket = secenek[(i + tekrar * 2 + rnd.randrange(len(secenek))) % len(secenek)]
        son_hareket = hareket
        if i == 0 and sahne.get("tur") == "resim":
            hareket = "vurus"  # ilk 1 saniye: güçlü görsel vuruş (izleyici kaydırmadan önce)
        plan.append({"sahne": sahne, "tekrar": tekrar, "hareket": hareket,
                     "sure": gorunen + (GECIS if i < n - 1 else 0.0),
                     "gecis": rnd.choice(GECIS_TURLERI)})
    return plan


def _cerceve(en: int, boy: int) -> str:
    """Kaynağı 1080x1920'ye oturtur: dikeye yakınsa doldurur, değilse bulanık arka plan + ortada net görüntü."""
    if en and boy and boy / en >= 1.45:
        return f"scale={G}:{Y}:force_original_aspect_ratio=increase,crop={G}:{Y},setsar=1"
    return (f"split=2[a][b];[a]scale={G}:{Y}:force_original_aspect_ratio=increase,crop={G}:{Y},"
            f"boxblur=28:2,eq=brightness=-0.10:saturation=1.1[bg];"
            f"[b]scale={G}:{int(Y * 0.62)}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2-60,setsar=1")


UST_YUKSEKLIK = 768  # yayıncı düzeni: üstte yüz kamerası (1080x768), altta oyun (1080x1152)


def yuz_kamerasi_bul(yol: str, ornek: int = 10) -> list[int] | None:
    """Yayın klibinde yüz kamerasının yerini bulur: karelerde hep aynı yerde duran yüz.
    Dönüş: [x, y, w, h] (piksel, kaynak çözünürlükte) ya da None (yüz kamerası yok)."""
    try:
        import cv2
    except ImportError:
        return None
    cap = cv2.VideoCapture(yol)
    toplam = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    en, boy = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not toplam or not en or not boy:
        cap.release()
        return None
    sinif = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    kutular: list[tuple[float, float, float]] = []
    for i in range(ornek):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(toplam * (i + 0.5) / ornek))
        ok, kare = cap.read()
        if not ok:
            continue
        gri = cv2.cvtColor(kare, cv2.COLOR_BGR2GRAY)
        for (x, y, w, h) in sinif.detectMultiScale(gri, 1.1, 8, minSize=(int(boy * 0.07), int(boy * 0.07))):
            kutular.append((x + w / 2, y + h / 2, float(w)))
    cap.release()
    if not kutular:
        return None
    yakin = boy * 0.08

    def komsular(a):
        return [b for b in kutular if abs(a[0] - b[0]) < yakin and abs(a[1] - b[1]) < yakin]

    grup = komsular(max(kutular, key=lambda a: len(komsular(a))))
    if len(grup) < max(3, ornek // 3):  # yüz kareler boyunca aynı yerde değilse oyun içi bir yüzdür
        return None
    grup.sort()
    cx, cy = grup[len(grup) // 2][0], sorted(g[1] for g in grup)[len(grup) // 2]
    yw = sorted(g[2] for g in grup)[len(grup) // 2]
    kw = min(en, yw * 3.4)
    kh = min(boy, kw * UST_YUKSEKLIK / G)
    kw = kh * G / UST_YUKSEKLIK
    x0 = min(max(cx - kw / 2, 0), en - kw)
    y0 = min(max(cy - kh * 0.45, 0), boy - kh)
    return [int(x0) // 2 * 2, int(y0) // 2 * 2, int(kw) // 2 * 2, int(kh) // 2 * 2]


def dikey_yerlesim(en: int, boy: int, yuz: list[int] | None) -> str:
    """Yayıncı klibi düzeni: yüz kamerası varsa üstte (1080x768) + oyun altta büyük (1080x1152);
    yoksa oyun tam dikey kırpılır."""
    alt = Y - UST_YUKSEKLIK
    if yuz:
        x, y, w, h = yuz
        gw = min(en, int(boy * G / alt) // 2 * 2)
        gx = (en - gw) // 2
        return (f"split=2[u][o];[u]crop={w}:{h}:{x}:{y},scale={G}:{UST_YUKSEKLIK}:force_original_aspect_ratio=increase,"
                f"crop={G}:{UST_YUKSEKLIK},setsar=1[ust];"
                f"[o]crop={gw}:{boy}:{gx}:0,scale={G}:{alt}:force_original_aspect_ratio=increase,crop={G}:{alt},setsar=1[alt];"
                f"[ust][alt]vstack,drawbox=x=0:y={UST_YUKSEKLIK - 3}:w={G}:h=6:color=black@0.9:t=fill")
    gw = min(en, int(boy * 9 / 16) // 2 * 2)
    return f"crop={gw}:{boy}:{(en - gw) // 2}:0,scale={G}:{Y},setsar=1"


def _zoompan(hareket: str, kare: int) -> str:
    ilerleme = f"(on/{max(kare - 1, 1)})"
    merkez_x, merkez_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if hareket == "vurus":  # ilk sahne: ilk yarım saniyede 1.35'ten hızlı açılma, sonra yavaş itme
        z = (f"if(lt(on,{VURUS_KARE}),1.35-0.33*on/{VURUS_KARE},"
             f"1.02+0.06*(on-{VURUS_KARE})/{max(kare - VURUS_KARE, 1)})")
        x, y = merkez_x, merkez_y
    elif hareket == "yakin":
        z, x, y = f"1.0+0.12*{ilerleme}", merkez_x, merkez_y
    elif hareket == "uzak":
        z, x, y = f"1.12-0.12*{ilerleme}", merkez_x, merkez_y
    elif hareket == "sag":
        z, x, y = "1.14", f"(iw-iw/zoom)*{ilerleme}", merkez_y
    elif hareket == "sol":
        z, x, y = "1.14", f"(iw-iw/zoom)*(1-{ilerleme})", merkez_y
    else:  # yukari
        z, x, y = "1.14", merkez_x, f"(ih-ih/zoom)*(1-{ilerleme})"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={kare}:s={G}x{Y}:fps={FPS}"


def sahne_komutu(sahne: dict[str, Any], sure: float, cikis: str, hareket: str = "yakin",
                 tekrar: int = 0) -> list[str]:
    kare = max(int(round(sure * FPS)), 2)
    if sahne["tur"] == "desen":
        c0, c1 = sahne.get("renkler", ["0x0f2027", "0x2c5364"])
        kaynak = f"gradients=s={G}x{Y}:r={FPS}:c0={c0}:c1={c1}:speed=0.02:d={sure:.2f}"
        return ["-f", "lavfi", "-i", kaynak, "-t", f"{sure:.2f}", "-vf", "setsar=1,format=yuv420p", *KODLA, cikis]
    en, boy, kaynak_sure = olcu(sahne["yol"])
    if sahne["tur"] == "resim":
        # tek kare girdi + zoompan: kare kare akıcı Ken Burns (2x ölçekte, titremesiz)
        filtre = (f"[0:v]{_cerceve(en, boy)},scale={G * 2}:{Y * 2},{_zoompan(hareket, kare)},"
                  f"setsar=1,format=yuv420p[v]")
        return ["-i", sahne["yol"], "-filter_complex", filtre, "-map", "[v]", "-frames:v", str(kare), *KODLA, cikis]
    if sahne.get("yerlesim") == "yayinci":  # kampanya klibi: baştan, ses ile senkron, dikey düzen
        filtre = f"[0:v]fps={FPS},{dikey_yerlesim(en, boy, sahne.get('yuz'))},format=yuv420p[v]"
        return ["-ss", f"{float(sahne.get('baslangic', 0)):.2f}", "-i", sahne["yol"], "-t", f"{sure:.2f}",
                "-filter_complex", filtre, "-map", "[v]", *KODLA, cikis]
    # video: farklı tekrarlarda farklı yerden başla, yavaş itme veya kaydırma
    baslangic = 0.0
    if sahne.get("bas") is not None:  # oyun kaydı gibi uzun kaynaklarda seçilmiş an
        baslangic = max(0.0, min(float(sahne["bas"]), max(kaynak_sure - sure, 0.0)))
    elif kaynak_sure > sure + 1:
        baslangic = ((tekrar * 3.7) + (hash(sahne["yol"]) % 5)) % max(kaynak_sure - sure, 0.1)
    if hareket in ("yakin", "uzak"):
        hiz = 0.10 / kare
        z = f"1+{hiz:.6f}*on" if hareket == "yakin" else f"1.10-{hiz:.6f}*on"
        hareket_f = f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={G}x{Y}:fps={FPS}"
    else:
        yon = "t" if hareket in ("sag", "yukari") else f"({sure:.2f}-t)"
        hareket_f = (f"scale={int(G * 1.12)}:{int(Y * 1.12)},"
                     f"crop={G}:{Y}:x='(iw-ow)*{yon}/{sure:.2f}':y='(ih-oh)/2'")
    filtre = f"[0:v]fps={FPS},{_cerceve(en, boy)},{hareket_f},setsar=1,format=yuv420p[v]"
    return ["-ss", f"{baslangic:.2f}", "-stream_loop", "-1", "-i", sahne["yol"], "-t", f"{sure:.2f}",
            "-filter_complex", filtre, "-map", "[v]", *KODLA, cikis]


def birlestir_komutu(parcalar: list[str], plan: list[dict[str, Any]], toplam: float) -> list[str]:
    """Parçaları xfade geçişleriyle birleştirir ve renk düzeltme uygular."""
    girisler: list[str] = []
    for p in parcalar:
        girisler += ["-i", p]
    zincir = [f"[{i}:v]settb=AVTB,fps={FPS},format=yuv420p[v{i}]" for i in range(len(parcalar))]
    son = "v0"
    uzunluk = plan[0]["sure"]
    for i in range(1, len(parcalar)):
        ofset = uzunluk - GECIS
        zincir.append(f"[{son}][v{i}]xfade=transition={plan[i]['gecis']}:duration={GECIS}:offset={ofset:.3f}[x{i}]")
        son = f"x{i}"
        uzunluk = uzunluk + plan[i]["sure"] - GECIS
    zincir.append(f"[{son}]{RENK},format=yuv420p[out]")
    return girisler + ["-filter_complex", ";".join(zincir), "-map", "[out]", "-t", f"{toplam:.2f}",
                       *KODLA, "ham_video.mp4"]


def gecis_anlari(plan: list[dict[str, Any]]) -> list[float]:
    anlar, uzunluk = [], plan[0]["sure"] if plan else 0
    for p in plan[1:]:
        anlar.append(uzunluk - GECIS)
        uzunluk += p["sure"] - GECIS
    return anlar


def sahne_etiketleri(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Her sahnenin ekranda göründüğü zaman aralığı + etiketi (resmi havuz: yer/karakter adı)."""
    sonuc, bas = [], 0.0
    for p in plan:
        son = bas + p["sure"] - GECIS
        if p["sahne"].get("etiket"):
            sonuc.append({"bas": round(bas + 0.15, 2), "son": round(son, 2), "metin": str(p["sahne"]["etiket"])})
        bas = son
    return sonuc


def whoosh_komutu(anlar: list[float], toplam: float, cikis: str = "gecis.wav") -> list[str]:
    """Her kesmede kısa, yumuşak bir hava sesi (internetsiz üretilir)."""
    n = len(anlar)
    tek = ("anoisesrc=d=0.45:c=pink:a=0.6:r=44100,highpass=f=350,lowpass=f=4200,"
           "afade=t=in:d=0.18,afade=t=out:st=0.18:d=0.27,aformat=channel_layouts=stereo")
    zincir = [f"{tek},asplit={n}" + "".join(f"[w{i}]" for i in range(n))] if n > 1 else [f"{tek}[w0]"]
    for i, an in enumerate(anlar):
        ms = max(int((an + GECIS / 2 - 0.22) * 1000), 0)
        zincir.append(f"[w{i}]adelay={ms}:all=1[d{i}]")
    zincir.append("".join(f"[d{i}]" for i in range(n)) +
                  f"amix=inputs={n}:normalize=0,apad=whole_dur={toplam:.2f}[a]")
    return ["-filter_complex", ";".join(zincir), "-map", "[a]", "-t", f"{toplam:.2f}", "-ar", "44100", cikis]


def final_komutu(sure: float, muzik: str | None, klip_sesi: tuple[str, float] | None,
                 muzik_seviyesi: float = 0.08, gecis_sesi: str | None = None,
                 gecis_seviyesi: float = 0.35) -> list[str]:
    girisler = ["-stream_loop", "-1", "-i", "ham_video.mp4", "-i", "ses.wav"]
    ses_zinciri = []
    karisim = ["[s0]"]
    sira = 2
    if muzik:
        girisler += ["-stream_loop", "-1", "-i", muzik]
        ses_zinciri.append("[1:a]aformat=channel_layouts=stereo,asplit=2[s0][yan]")
        # seslendirme konuşurken müzik otomatik kısılır
        ses_zinciri.append(f"[{sira}:a]aformat=channel_layouts=stereo,volume={muzik_seviyesi * 2.5}[m{sira}]")
        ses_zinciri.append(f"[m{sira}][yan]sidechaincompress=threshold=0.03:ratio=9:attack=15:release=350[s{sira}]")
        karisim.append(f"[s{sira}]")
        sira += 1
    else:
        ses_zinciri.append("[1:a]aformat=channel_layouts=stereo,volume=1.0[s0]")
    if klip_sesi:
        girisler += ["-i", klip_sesi[0]]
        ses_zinciri.append(f"[{sira}:a]volume={klip_sesi[1]}[s{sira}]")
        karisim.append(f"[s{sira}]")
        sira += 1
    if gecis_sesi:
        girisler += ["-i", gecis_sesi]
        ses_zinciri.append(f"[{sira}:a]volume={gecis_seviyesi}[s{sira}]")
        karisim.append(f"[s{sira}]")
        sira += 1
    if len(karisim) > 1:
        ses_zinciri.append(f"{''.join(karisim)}amix=inputs={len(karisim)}:duration=first:normalize=0,"
                           "alimiter=limit=0.95[k]")
    else:
        ses_zinciri[-1] = ses_zinciri[-1].replace("[s0]", "[k]")
    # YouTube standardı: -14 LUFS, tepe -1.5 dB (videolar arası ses seviyesi tutarlı olur)
    ses_zinciri.append(f"[k]{SES_NORMAL}[a]")
    filtre = "[0:v]ass=altyazi.ass[v];" + ";".join(ses_zinciri)
    return girisler + [
        "-filter_complex", filtre, "-map", "[v]", "-map", "[a]", "-t", f"{sure:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "video.mp4",
    ]


def muzik_sec(k: dict[str, Any]) -> str | None:
    klasor = KOK / "muzik" / k.get("muzik_klasoru", k["id"])
    if not klasor.exists():
        klasor = KOK / "muzik"
    parcalar = [p for p in klasor.glob("*") if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg"}]
    return str(random.choice(parcalar).resolve()) if parcalar else None


def muzik_atfi(muzik: str | None) -> tuple[str, bool] | None:
    """muzik/LISANSLAR.txt içinden parçanın atıf metnini bulur: (atıf, atıf_zorunlu_mu)."""
    if not muzik:
        return None
    yol = Path(muzik)
    for dosya in (yol.parent / "LISANSLAR.txt", KOK / "muzik" / "LISANSLAR.txt"):
        if not dosya.exists():
            continue
        for satir in dosya.read_text(encoding="utf-8").splitlines():
            if satir.strip().startswith("#") or satir.count("|") < 2:
                continue
            ad, lisans, atif = (x.strip() for x in satir.split("|", 2))
            if ad == yol.name:
                return atif, lisans.upper() not in {"CC0", "PUBLIC DOMAIN"}
    return None


def muzik_atfini_ekle(is_: Is, muzik: str | None) -> None:
    atif = muzik_atfi(muzik)
    if not atif:
        return
    metin, zorunlu = atif
    lisanslar = is_.veri.setdefault("lisanslar", [])
    if ("Müzik: " + metin) not in lisanslar:
        lisanslar.append("Müzik: " + metin)
    aciklama = is_.veri.get("aciklama")
    if zorunlu and isinstance(aciklama, str) and metin not in aciklama:
        is_.veri["aciklama"] = aciklama + "\n\n" + metin


def altyazi_yenile(is_: Is, k: dict[str, Any], toplam: float) -> None:
    """Altyazıyı güncel tasarımla (kanca + kelime kelime + ilerleme çubuğu) yeniden yazar."""
    from . import seslendirme
    from .senarist import kanca_duzelt

    zamanlar = is_.veri.get("kelime_zamanlari")
    if not zamanlar and is_.veri.get("senaryo"):
        zamanlar = seslendirme.tahmini_zamanlar(is_.veri["senaryo"], float(is_.veri["sure"]))
    if not zamanlar:
        return
    kanca = is_.veri.get("kanca_metni") or (kanca_duzelt(is_.veri) if is_.veri.get("baslik") else None)
    seslendirme.ass_yaz(seslendirme.kelimeleri_grupla(zamanlar), is_.klasor / "altyazi.ass",
                        k.get("altyazi"), kanca=kanca, toplam=toplam, dil=k.get("dil", "en"),
                        acilis_notu=is_.veri.get("acilis_notu") or None,
                        kapanis=is_.veri.get("kapanis_notu") or None,
                        kanca_y=UST_YUKSEKLIK if is_.veri.get("yayinci_sesi") else None,
                        etiketler=is_.veri.get("sahne_etiketleri") or None)


def kurgula(is_: Is, k: dict[str, Any]) -> None:
    klasor = is_.klasor
    sure = min(float(is_.veri["sure"]) + 0.6, float(k.get("en_uzun_sure", 58)))
    sahneler = is_.veri["sahneler"]
    klip_sesi = None
    if is_.veri.get("mod") == "izinli_klip":
        klip = sahneler[0]
        sure = min(sure, float(klip.get("en_uzun", 30)) + 0.6) if klip.get("en_uzun") else sure
        sure = max(sure, float(is_.veri["sure"]) + 0.3)
        if is_.veri.get("yayinci_sesi"):  # ses klibin kendisi: süre tam klip kadar
            sure = float(is_.veri["sure"])
            if "yuz_kamerasi" not in is_.veri:
                is_.veri["yuz_kamerasi"] = yuz_kamerasi_bul(str(Path(klip["yol"]).resolve()))
                log.info("%s: yüz kamerası %s", is_.id, is_.veri["yuz_kamerasi"] or "bulunamadı, tam dikey kırpma")
            klip = {**klip, "yerlesim": "yayinci", "yuz": is_.veri["yuz_kamerasi"],
                    "baslangic": float(is_.veri.get("klip_baslangic", 0))}
        plan = [{"sahne": klip, "tekrar": 0, "hareket": "yakin", "sure": sure, "gecis": "fade"}]
        if klip.get("orijinal_ses") and not is_.veri.get("yayinci_sesi"):
            klip_sesi =(str(Path(klip["yol"]).resolve()), float(klip["orijinal_ses"]))
    else:
        plan = kesim_plani(sahneler, sure, float(k.get("kesme_sn", 2.4)), tohum=is_.id)

    parcalar = []
    for i, adim in enumerate(plan):
        ad = f"parca_{i:02d}.mp4"
        sahne = adim["sahne"]
        if "yol" in sahne:
            sahne = {**sahne, "yol": str(Path(sahne["yol"]).resolve())}
        calistir(sahne_komutu(sahne, adim["sure"], ad, adim["hareket"], adim["tekrar"]), klasor)
        parcalar.append(ad)
    calistir(birlestir_komutu(parcalar, plan, sure), klasor)

    gecis_sesi = None
    anlar = gecis_anlari(plan)
    if anlar and k.get("gecis_sesi", True):
        calistir(whoosh_komutu(anlar, sure), klasor)
        gecis_sesi = "gecis.wav"
    is_.veri["sahne_etiketleri"] = sahne_etiketleri(plan)
    altyazi_yenile(is_, k, sure)
    # yayıncı klibinde ses aynen korunur (kampanya kuralı): müzik eklenmez
    muzik = None if is_.veri.get("yayinci_sesi") else muzik_sec(k)
    calistir(final_komutu(sure, muzik, klip_sesi, k.get("muzik_seviyesi", 0.08), gecis_sesi,
                          k.get("gecis_seviyesi", 0.35)), klasor)
    if muzik:
        is_.veri["muzik"] = Path(muzik).name
        muzik_atfini_ekle(is_, muzik)
    for p in parcalar + ["gecis.wav"]:
        (klasor / p).unlink(missing_ok=True)
    is_.veri["video"] = "video.mp4"
    is_.veri["kesim_sayisi"] = len(plan)
    log.info("%s: video hazır (%.1f sn, %d kesme)", is_.id, sure, len(plan))
