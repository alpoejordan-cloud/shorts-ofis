"""Seslendirme: senaryoyu Piper (açık kaynak, bilgisayarda çalışır) ile sese çevirir,
faster-whisper ile kelime zamanlarını çıkarıp altyazı dosyası yazar."""
from __future__ import annotations

import wave
from pathlib import Path
from typing import Any

import requests

from ..cekirdek import SESLER, Is, gunluk_al
from ..olay import calisiyor

log = gunluk_al("seslendirme")

HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
KOKORO_DOSYALAR = ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")


def kokoro_mu(ses_adi: str) -> bool:
    """'kokoro:af_heart' biçimindeki sesler Kokoro-82M (Apache 2.0) ile üretilir; yalnız İngilizce."""
    return ses_adi.startswith("kokoro:")


def ses_yolu(ses_adi: str) -> Path:
    if kokoro_mu(ses_adi):
        return SESLER / KOKORO_DOSYALAR[0]
    return SESLER / f"{ses_adi}.onnx"


def ses_indir(ses_adi: str) -> Path:
    """Örn. 'tr_TR-dfki-medium' -> tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx"""
    if kokoro_mu(ses_adi):
        for dosya in KOKORO_DOSYALAR:
            hedef_k = SESLER / dosya
            if not hedef_k.exists():
                log.info("Kokoro modeli indiriliyor: %s", dosya)
                r = requests.get(f"{KOKORO_URL}/{dosya}", timeout=600)
                r.raise_for_status()
                hedef_k.write_bytes(r.content)
        return ses_yolu(ses_adi)
    hedef = ses_yolu(ses_adi)
    if hedef.exists() and Path(str(hedef) + ".json").exists():
        return hedef
    yerel, isim, kalite = ses_adi.split("-", 2)
    dil = yerel.split("_")[0]
    for uzanti in (".onnx", ".onnx.json"):
        url = f"{HF}/{dil}/{yerel}/{isim}/{kalite}/{ses_adi}{uzanti}"
        log.info("Ses indiriliyor: %s", url)
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        Path(str(SESLER / ses_adi) + uzanti).write_bytes(r.content)
    return hedef


_SES_ONBELLEK: dict[str, Any] = {}


def _ses_yukle(ses_adi: str):
    if ses_adi not in _SES_ONBELLEK:
        from piper import PiperVoice  # ağır modül, gerektiğinde yüklenir

        _SES_ONBELLEK[ses_adi] = PiperVoice.load(str(ses_indir(ses_adi)))
    return _SES_ONBELLEK[ses_adi]


def _kokoro_sentezle(metin: str, ses_adi: str, cikis: Path, hiz: float) -> float:
    import numpy as np

    if "kokoro" not in _SES_ONBELLEK:
        from kokoro_onnx import Kokoro

        ses_indir(ses_adi)
        _SES_ONBELLEK["kokoro"] = Kokoro(str(SESLER / KOKORO_DOSYALAR[0]), str(SESLER / KOKORO_DOSYALAR[1]))
    ornekler, hz = _SES_ONBELLEK["kokoro"].create(metin, voice=ses_adi.split(":", 1)[1], speed=hiz, lang="en-us")
    veri = (np.clip(ornekler, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(cikis), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(hz)
        wf.writeframes(veri.tobytes())
    return len(veri) / float(hz)


def sentezle(metin: str, ses_adi: str, cikis: Path, hiz: float = 1.0, yedek: str | None = None) -> float:
    """Kokoro sesi istenirse onu dener, olmazsa yedek Piper sesine düşer."""
    if kokoro_mu(ses_adi):
        try:
            with calisiyor(None, f"İngilizce seslendiriyor ({ses_adi.split(':', 1)[1]})", yz="kokoro"):
                return _kokoro_sentezle(metin, ses_adi, cikis, hiz)
        except Exception as e:
            if not yedek:
                raise
            log.warning("Kokoro çalışmadı (%s), yedek ses kullanılıyor: %s", e, yedek)
            ses_adi = yedek
    with calisiyor(None, f"seslendiriyor ({ses_adi})", yz="piper"):
        return _piper_sentezle(metin, ses_adi, cikis, hiz)


def _piper_sentezle(metin: str, ses_adi: str, cikis: Path, hiz: float) -> float:
    ses = _ses_yukle(ses_adi)
    with wave.open(str(cikis), "wb") as wf:
        if hasattr(ses, "synthesize_wav"):  # piper-tts 1.3+
            try:
                from piper import SynthesisConfig

                ses.synthesize_wav(metin, wf, syn_config=SynthesisConfig(length_scale=1.0 / hiz))
            except ImportError:
                ses.synthesize_wav(metin, wf)
        else:  # eski piper-tts
            ses.synthesize(metin, wf, length_scale=1.0 / hiz)
    with wave.open(str(cikis), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


# ---- Altyazı ----

def _grup(simdiki: list[dict[str, Any]]) -> dict[str, Any]:
    return {"bas": simdiki[0]["bas"], "son": simdiki[-1]["son"],
            "metin": " ".join(x["kelime"].strip() for x in simdiki),
            "kelimeler": [{"kelime": x["kelime"].strip(), "bas": float(x["bas"]), "son": float(x["son"])}
                          for x in simdiki]}


def kelimeleri_grupla(kelimeler: list[dict[str, Any]], en_fazla: int = 3,
                      en_fazla_karakter: int = 16) -> list[dict[str, Any]]:
    """Kelime zamanlarını ekranda 1-3 kelimelik, tek satıra sığan (en fazla ~16 harf) parçalara böler."""
    gruplar: list[dict[str, Any]] = []
    simdiki: list[dict[str, Any]] = []
    for k in kelimeler:
        if not str(k["kelime"]).strip():
            continue
        uzunluk = sum(len(str(x["kelime"]).strip()) + 1 for x in simdiki) + len(str(k["kelime"]).strip())
        if simdiki and uzunluk > en_fazla_karakter:  # okunabilirlik: satır taşmasın
            gruplar.append(_grup(simdiki))
            simdiki = []
        simdiki.append(k)
        noktalama = k["kelime"].rstrip().endswith((".", ",", "!", "?", ":", ";"))
        if len(simdiki) >= en_fazla or noktalama:
            gruplar.append(_grup(simdiki))
            simdiki = []
    if simdiki:
        gruplar.append(_grup(simdiki))
    return gruplar


def _ass_zaman(sn: float) -> str:
    sn = max(sn, 0.0)
    s, kalan = divmod(sn, 3600)
    d, kalan = divmod(kalan, 60)
    return f"{int(s)}:{int(d):02d}:{kalan:05.2f}"


_DIL = {"dil": "en"}


_KUFUR = __import__("re").compile(
    r"\b(fuck\w*|motherfuck\w*|shit(s|ty|ting)?|bitch(es)?|asshole(s)?|dick(s|head)?|pussy|cunt(s)?|nigg\w*|"
    r"amk|aq|siktir\w*|orospu\w*|piç\w*)\b", __import__("re").IGNORECASE)


def kufur_maskele(metin: str) -> str:
    """Ekrandaki altyazıda küfürleri maskeler (ses değişmez): fuck -> f***"""
    return _KUFUR.sub(lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1), metin)


def _temiz(metin: str) -> str:
    metin = kufur_maskele(metin.replace("{", "(").replace("}", ")").replace("\\", "/"))
    if _DIL["dil"] == "tr":  # Türkçe büyük harf: i -> İ, ı -> I
        metin = metin.replace("i", "İ").replace("ı", "I")
    return metin.upper()


def ass_yaz(gruplar: list[dict[str, Any]], cikis: Path, stil: dict[str, Any] | None = None,
            kanca: str | None = None, toplam: float | None = None, dil: str = "en",
            acilis_notu: str | None = None, acilis_sure: float = 2.0, kapanis: str | None = None,
            kanca_y: int | None = None, etiketler: list[dict[str, Any]] | None = None) -> None:
    """Altyazı dosyası: kelime kelime renklenen alt yazı, ilk saniyelerde kanca metni,
    altta ilerleme çubuğu."""
    _DIL["dil"] = dil
    stil = stil or {}
    yazi = stil.get("yazi_tipi", "Arial Black")
    boyut = stil.get("boyut", 92)
    renk = stil.get("renk", "&H00FFFFFF")
    vurgu = stil.get("vurgu", "&H0000E5FF")  # sarı (ASS renkleri BGR)
    marj = stil.get("alt_bosluk", 600)
    kanca_boyut = stil.get("kanca_boyut", 100)
    kanca_sure = float(stil.get("kanca_sure", 2.8))
    satirlar = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        f"Style: Ana,{yazi},{boyut},{renk},{vurgu},&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,9,5,2,60,60,{marj},1",
        f"Style: Kanca,{yazi},{kanca_boyut},&H00FFFFFF,&H000000FF,&H1E000000,&H00000000,-1,0,0,0,100,100,1,0,3,24,0,8,"
        "80,80,300,1",
        "Style: Not,Arial,46,&H00FFFFFF,&H000000FF,&H40000000,&H00000000,-1,0,0,0,100,100,0,0,3,14,0,8,"
        "90,90,120,1",
        "Style: Etiket,Arial Black,40,&H00FFFFFF,&H000000FF,&H00000000,&H9E000000,-1,0,0,0,100,100,2,0,3,10,0,7,"
        "60,60,150,1",
        "Style: Cubuk,Arial,10,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for gi, g in enumerate(gruplar):
        # bir sonraki grup başlarken bu grup ekrandan kalksın (üst üste binme olmasın)
        if gi + 1 < len(gruplar):
            g = {**g, "son": min(g["son"], gruplar[gi + 1]["bas"] - 0.06)}
        kelimeler = g.get("kelimeler")
        if not kelimeler:
            satirlar.append(f"Dialogue: 0,{_ass_zaman(g['bas'])},{_ass_zaman(g['son'] + 0.05)},Ana,,0,0,0,,"
                            f"{{\\fad(60,0)\\t(0,90,\\fscx112\\fscy112)\\t(90,180,\\fscx100\\fscy100)}}"
                            f"{_temiz(g['metin'])}")
            continue
        for j, w in enumerate(kelimeler):
            bas = g["bas"] if j == 0 else w["bas"]
            son = kelimeler[j + 1]["bas"] if j + 1 < len(kelimeler) else g["son"] + 0.05
            parcalar = []
            for n, x in enumerate(kelimeler):
                if n == j:
                    parcalar.append(f"{{\\c{vurgu}\\t(0,70,\\fscx114\\fscy114)\\t(70,150,\\fscx106\\fscy106)}}"
                                    f"{_temiz(x['kelime'])}{{\\c{renk}\\fscx100\\fscy100}}")
                else:
                    parcalar.append(_temiz(x["kelime"]))
            giris = "{\\fad(50,0)}" if j == 0 else ""
            satirlar.append(f"Dialogue: 0,{_ass_zaman(bas)},{_ass_zaman(max(son, bas + 0.05))},Ana,,0,0,0,,"
                            f"{giris}{' '.join(parcalar)}")
    if kanca:
        sozler = _temiz(kanca).split()
        if len(sozler) > 2:  # son iki kelime sarı
            metin = " ".join(sozler[:-2]) + f" {{\\c{vurgu}}}" + " ".join(sozler[-2:])
        else:
            metin = f"{{\\c{vurgu}}}" + " ".join(sozler)
        satirlar.append(f"Dialogue: 2,0:00:00.00,{_ass_zaman(kanca_sure)},Kanca,,0,0,0,,"
                        "{" + (f"\\an5\\pos(540,{kanca_y})" if kanca_y else "") +
                        f"\\fad(0,250)\\t(0,140,\\fscx112\\fscy112)\\t(140,280,\\fscx100\\fscy100)}}{metin}")
    if kapanis and toplam:  # kampanyanın istediği çağrı (CTA): son 3 saniye, ekran ortasında
        temiz_k = kapanis.replace("{", "(").replace("}", ")").replace("\\", "/")
        satirlar.append(f"Dialogue: 2,{_ass_zaman(max(toplam - 3.0, 0))},{_ass_zaman(toplam)},Kanca,,0,0,0,,"
                        f"{{\\an5\\pos(540,760)\\fad(200,0)\\t(0,160,\\fscx110\\fscy110)\\t(160,320,\\fscx100\\fscy100)}}"
                        f"{temiz_k}")
    for e in etiketler or []:  # sahne etiketi (ör. "PLACE: VICE CITY"): sol üstte, kancayla çakışmasın
        bas = max(float(e["bas"]), kanca_sure if kanca else 0.0)
        if float(e["son"]) - bas < 0.6:
            continue
        temiz_e = str(e["metin"]).replace("{", "(").replace("}", ")").replace("\\", "/")
        satirlar.append(f"Dialogue: 2,{_ass_zaman(bas)},{_ass_zaman(float(e['son']))},Etiket,,0,0,0,,"
                        f"{{\\fad(120,120)\\c{vurgu}}}{temiz_e}")
    if acilis_notu:  # kampanyanın zorunlu bilgilendirmesi: ilk saniyelerde, en üstte, büyük harfe çevrilmeden
        temiz = acilis_notu.replace("{", "(").replace("}", ")").replace("\\", "/")
        satirlar.append(f"Dialogue: 3,0:00:00.00,{_ass_zaman(acilis_sure)},Not,,0,0,0,,{{\\fad(0,200)}}{temiz}")
    if toplam:
        ms = int(toplam * 1000)
        cizim = "m 0 0 l 1080 0 l 1080 14 l 0 14"
        satirlar.append(f"Dialogue: 1,0:00:00.00,{_ass_zaman(toplam)},Cubuk,,0,0,0,,"
                        f"{{\\an7\\pos(0,1906)\\1c&HFFFFFF&\\1a&HB0&\\p1}}{cizim}{{\\p0}}")
        satirlar.append(f"Dialogue: 1,0:00:00.00,{_ass_zaman(toplam)},Cubuk,,0,0,0,,"
                        f"{{\\an7\\pos(0,1906)\\1c{vurgu}\\clip(0,0,0,1920)\\t(0,{ms},\\clip(0,0,1080,1920))\\p1}}"
                        f"{cizim}{{\\p0}}")
    cikis.write_text("\n".join(satirlar) + "\n", encoding="utf-8")


def ses_dizisi(ses_dosyasi: Path):
    import shutil
    import subprocess

    import numpy as np

    ham = subprocess.run(
        [shutil.which("ffmpeg") or "ffmpeg", "-v", "error", "-i", str(ses_dosyasi), "-f", "s16le",
         "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True,
    ).stdout
    return np.frombuffer(ham, np.int16).astype(np.float32) / 32768.0


def sayi_parcalarini_birlestir(zamanlar: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Whisper sayıları böler ("17" ".4", "$15" ",000", "70" "%"): altyazıda "17 .4" görünmesin, tek kelime olsun."""
    import re as _re

    sonuc: list[dict[str, Any]] = []
    for z in zamanlar:
        w = str(z.get("kelime", ""))
        if sonuc and _re.match(r"^\s*([.,]\d|%)", w) and _re.search(r"\d\s*$", str(sonuc[-1]["kelime"])):
            sonuc[-1] = {**sonuc[-1], "kelime": str(sonuc[-1]["kelime"]).rstrip() + w.strip(), "son": z["son"]}
        else:
            sonuc.append(dict(z))
    return sonuc


def kelime_zamanlari(ses_dosyasi: Path, dil: str) -> list[dict[str, Any]]:
    with calisiyor(None, "sesi dinleyip altyazı için kelime zamanlarını çıkarıyor", yz="whisper"):
        return sayi_parcalarini_birlestir(_kelime_zamanlari(ses_dosyasi, dil))


def _kelime_zamanlari(ses_dosyasi: Path, dil: str) -> list[dict[str, Any]]:
    from faster_whisper import WhisperModel

    model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=2)  # bilgisayarı yormasın
    # Sesi FFmpeg ile 16 kHz diziye çeviriyoruz; böylece PyAV sürüm uyumsuzlukları sorun olmaz
    dizi = ses_dizisi(ses_dosyasi)
    try:
        parcalar, _ = model.transcribe(dizi, language=dil, word_timestamps=True, vad_filter=False)
        return [
            {"kelime": w.word, "bas": w.start, "son": w.end}
            for p in parcalar for w in (p.words or [])
        ]
    except (ValueError, IndexError) as e:
        # Oyun/müzik ağırlıklı seslerde kelime hizalama çökebiliyor: cümle zamanlarıyla devam
        log.warning("Kelime zamanları alınamadı (%s), cümle zamanları kullanılıyor", e)
        parcalar, _ = model.transcribe(dizi, language=dil, word_timestamps=False, vad_filter=True)
        sonuc: list[dict[str, Any]] = []
        for p in parcalar:
            for z in tahmini_zamanlar(p.text.strip(), max(p.end - p.start, 0.1)):
                sonuc.append({"kelime": z["kelime"], "bas": p.start + z["bas"], "son": p.start + z["son"]})
        return sonuc


def tahmini_zamanlar(metin: str, sure: float) -> list[dict[str, Any]]:
    """Whisper kullanılamazsa: kelimeleri uzunluklarına göre süreye yayar."""
    kelimeler = metin.split()
    agirlik = [len(k) + 2 for k in kelimeler]
    toplam = sum(agirlik) or 1
    t, sonuc = 0.0, []
    for k, a in zip(kelimeler, agirlik):
        d = sure * a / toplam
        sonuc.append({"kelime": k, "bas": t, "son": t + d})
        t += d
    return sonuc


def en_iyi_an(klip: Path, uzunluk: float) -> float:
    """Klip izin verilen süreden uzunsa, ses enerjisinin (bağırma, kahkaha, patlama) en yoğun olduğu
    `uzunluk` saniyelik pencerenin başlangıcını döner. Kısa kliplerde 0."""
    import numpy as np

    try:
        dizi = ses_dizisi(klip)  # 16 kHz mono
    except Exception:
        return 0.0
    toplam = len(dizi) / 16000
    if toplam <= uzunluk + 2:
        return 0.0
    saniye = int(toplam)
    rms = np.sqrt(np.array([np.mean(dizi[i * 16000:(i + 1) * 16000] ** 2) for i in range(saniye)]) + 1e-9)
    # ani yükselişleri (tepki anları) ödüllendir: enerji + pozitif değişim
    skor = rms + np.maximum(np.diff(rms, prepend=rms[0]), 0) * 2
    pencere = int(uzunluk)
    toplamlar = np.convolve(skor, np.ones(pencere), mode="valid")
    en_iyi = int(np.argmax(toplamlar))
    return float(max(0, en_iyi - 2))  # tepkiden önceki bağlam için 2 sn erken başla


def klip_sesini_kullan(is_: Is, k: dict[str, Any]) -> None:
    """Yayıncı sesi modu: TTS yok; klibin kendi sesi ana ses olur, altyazı yayıncının konuşmasından çıkarılır."""
    import shutil
    import subprocess

    ses_dosyasi = is_.klasor / "ses.wav"
    en_uzun = float(is_.veri.get("en_uzun_sn", 58))
    if "klip_baslangic" not in is_.veri:  # uzun klipte en hareketli anı seç
        is_.veri["klip_baslangic"] = en_iyi_an(Path(is_.veri["klip_yolu"]), en_uzun)
    bas = float(is_.veri["klip_baslangic"])
    subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-y", "-v", "error", "-ss", f"{bas:.2f}",
                    "-i", is_.veri["klip_yolu"], "-t", f"{en_uzun:.2f}", "-vn", "-ac", "1", "-ar", "22050",
                    str(ses_dosyasi)], check=True)
    with wave.open(str(ses_dosyasi), "rb") as wf:
        sure = wf.getnframes() / float(wf.getframerate())
    try:
        zamanlar = kelime_zamanlari(ses_dosyasi, k["dil"])
    except Exception as e:
        log.warning("%s: whisper çalışmadı (%s), altyazısız devam", is_.id, e)
        zamanlar = []
    zamanlar = [{"kelime": str(z["kelime"]), "bas": round(float(z["bas"]), 3), "son": round(float(z["son"]), 3)}
                for z in zamanlar]
    ass_yaz(kelimeleri_grupla(zamanlar), is_.klasor / "altyazi.ass", k.get("altyazi"),
            kanca=is_.veri.get("kanca_metni"), toplam=sure, dil=k.get("dil", "en"),
            acilis_notu=is_.veri.get("acilis_notu") or None, kapanis=is_.veri.get("kapanis_notu") or None,
            kanca_y=768)
    is_.veri.update({"ses": "ses.wav", "altyazi": "altyazi.ass", "sure": round(sure, 2),
                     "kelime_zamanlari": zamanlar})
    log.info("%s: yayıncı sesi kullanılıyor (%.1f sn)", is_.id, sure)


def seslendir(is_: Is, k: dict[str, Any]) -> None:
    if is_.veri.get("yayinci_sesi"):
        return klip_sesini_kullan(is_, k)
    ses_dosyasi = is_.klasor / "ses.wav"
    sure = sentezle(is_.veri["senaryo"], k["ses"], ses_dosyasi, hiz=k.get("ses_hizi", 1.08),
                    yedek=k.get("ses_yedek"))
    try:
        zamanlar = kelime_zamanlari(ses_dosyasi, k["dil"])
    except Exception as e:
        log.warning("%s: whisper çalışmadı (%s), tahmini altyazı kullanılıyor", is_.id, e)
        zamanlar = []
    if not zamanlar:
        zamanlar = tahmini_zamanlar(is_.veri["senaryo"], sure)
    zamanlar = [{"kelime": str(z["kelime"]), "bas": round(float(z["bas"]), 3), "son": round(float(z["son"]), 3)}
                for z in zamanlar]
    ass_yaz(kelimeleri_grupla(zamanlar), is_.klasor / "altyazi.ass", k.get("altyazi"),
            kanca=is_.veri.get("kanca_metni"), toplam=sure + 0.6, dil=k.get("dil", "en"))
    is_.veri.update({"ses": "ses.wav", "altyazi": "altyazi.ass", "sure": round(sure, 2),
                     "kelime_zamanlari": zamanlar})
    log.info("%s: ses hazır (%.1f sn)", is_.id, sure)
