import shutil
import subprocess
import wave
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from ofis import cekirdek
from ofis.ajanlar import gorsel, kurgu, senarist, seslendirme
from ofis.ajanlar.yukleyici import sonraki_yayin_zamani
from ofis.yapay_zeka import json_ayikla


def test_kanallar_yukleniyor():
    aktif = cekirdek.kanallar()
    assert {k["id"] for k in aktif} == {"teknoloji_en", "finans_tr", "gta_en"}
    for k in cekirdek.kanallar(sadece_aktif=False):
        assert k["dil"] in {"tr", "en"} and k["ses"] and k["nis"]


def test_is_kaydet_yukle():
    i = cekirdek.Is(kanal="teknoloji_en", veri={"konu": "deneme"})
    i.kaydet()
    geri = cekirdek.Is.yukle(i.id)
    assert geri.veri["konu"] == "deneme" and geri.durum == "fikir"
    assert "deneme" in cekirdek.gecmis_basliklar("teknoloji_en")


def test_json_ayikla_dusunme_ve_kod_blogu():
    assert json_ayikla('<think>hmm</think>```json\n{"a": 1}\n```') == {"a": 1}
    assert json_ayikla('Tabii! İşte: {"b": [1, 2]} umarım olur') == {"b": [1, 2]}


def test_senaryo_dogrulama():
    k = {"kelime_araligi": [5, 10]}
    iyi = {"senaryo": "bir iki üç dört beş altı", "baslik": "Başlık #shorts", "gorsel_kelimeler": ["city"]}
    assert senarist.dogrula(iyi, k) == []
    kotu = {"senaryo": "kısa", "baslik": "", "gorsel_kelimeler": []}
    assert len(senarist.dogrula(kotu, k)) == 3


def test_izin_belgesi_olmayan_yayinci_kullanilmaz():
    # örnek yayıncının izin_belgesi boş: listede olmamalı
    assert all(y["ad"] != "Örnek Yayıncı" for y in gorsel.izinli_yayincilar())
    assert gorsel.klip_sec(cekirdek.kanal("gta_en")) is None


def test_altyazi_gruplama_ve_ass(tmp_path):
    zaman = seslendirme.tahmini_zamanlar("Merhaba dünya, bu bir deneme videosu.", 4.0)
    gruplar = seslendirme.kelimeleri_grupla(zaman)
    assert gruplar[0]["metin"] == "Merhaba dünya,"
    assert abs(gruplar[-1]["son"] - 4.0) < 1e-6
    yol = tmp_path / "a.ass"
    seslendirme.ass_yaz(gruplar, yol)
    metin = yol.read_text(encoding="utf-8")
    assert "PlayResY: 1920" in metin and "MERHABA DÜNYA," in metin


def test_yayin_zamani_dolu_saati_atlar():
    k = {"yayin_saatleri": ["18:00"], "saat_dilimi": "Europe/Istanbul"}
    tz = ZoneInfo("Europe/Istanbul")
    simdi = datetime(2026, 11, 24, 10, 0, tzinfo=tz)
    ilk = sonraki_yayin_zamani(k, [], simdi)
    assert ilk == datetime(2026, 11, 24, 18, 0, tzinfo=tz)
    ikinci = sonraki_yayin_zamani(k, [ilk], simdi)
    assert ikinci == datetime(2026, 11, 25, 18, 0, tzinfo=tz)


def test_final_komutu_ses_karisimi():
    arg = kurgu.final_komutu(30, "muzik.mp3", ("klip.mp4", 0.25))
    filtre = arg[arg.index("-filter_complex") + 1]
    assert "amix=inputs=3" in filtre and "ass=altyazi.ass" in filtre
    tek = kurgu.final_komutu(30, None, None)
    assert "amix" not in tek[tek.index("-filter_complex") + 1]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg yok")
def test_kurgu_uctan_uca(tmp_path, monkeypatch):
    """Sahte ses + test görüntüsüyle gerçek bir 9:16 video üretir."""
    i = cekirdek.Is(kanal="teknoloji_en")
    klasor = i.klasor
    # 3 saniyelik sessiz ses
    with wave.open(str(klasor / "ses.wav"), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050)
        wf.writeframes(b"\x00\x00" * 22050 * 3)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
                    "-t", "2", str(tmp_path / "a.mp4")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=blue:s=800x600",
                    "-frames:v", "1", str(tmp_path / "b.png")], check=True)
    seslendirme.ass_yaz(seslendirme.kelimeleri_grupla(seslendirme.tahmini_zamanlar("one two three four", 3)),
                        klasor / "altyazi.ass")
    i.veri = {"sure": 3.0, "sahneler": [{"tur": "video", "yol": str(tmp_path / "a.mp4")},
                                        {"tur": "resim", "yol": str(tmp_path / "b.png")}]}
    monkeypatch.setattr(kurgu, "muzik_sec", lambda k: None)
    kurgu.kurgula(i, {"id": "teknoloji_en"})
    cikti = klasor / "video.mp4"
    assert cikti.exists()
    olcu = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                           "stream=width,height", "-of", "csv=p=0", str(cikti)], capture_output=True, text=True)
    assert olcu.stdout.strip() == "1080,1920"


def test_mudur_isi_onaya_kadar_tasir(monkeypatch):
    from ofis import mudur

    cagrilar = []

    def sahte(ad):
        def f(is_, k):
            cagrilar.append(ad)
        return f

    monkeypatch.setattr(mudur, "ADIMLAR", {
        "fikir": (sahte("senarist"), "senaryo"), "senaryo": (sahte("ses"), "ses"),
        "ses": (sahte("gorsel"), "gorsel"), "gorsel": (sahte("kurgu"), "video"),
    })
    i = cekirdek.Is(kanal="finans_tr", veri={"konu": "x"})
    i.kaydet()
    mudur.is_ilerlet(i)
    assert cagrilar == ["senarist", "ses", "gorsel", "kurgu"]
    assert cekirdek.Is.yukle(i.id).durum == "onay_bekliyor"


def test_mudur_hatada_tekrar_dener_sonra_birakir(monkeypatch):
    from ofis import mudur

    def bozuk(is_, k):
        raise RuntimeError("bozuldu")

    monkeypatch.setattr(mudur, "ADIMLAR", {"fikir": (bozuk, "senaryo")})
    i = cekirdek.Is(kanal="finans_tr")
    for _ in range(mudur.EN_FAZLA_DENEME):
        mudur.is_ilerlet(i)
    assert i.durum == "hata" and len(i.hatalar) == mudur.EN_FAZLA_DENEME


def test_ai_gorsel_sahneleri_eklenir(monkeypatch, tmp_path):
    def sahte_ai(istem, hedef, seed=0):
        hedef.write_bytes(b"x")
        return hedef

    monkeypatch.setattr(gorsel, "ai_gorsel", sahte_ai)
    monkeypatch.setattr(gorsel, "stok_video", lambda kelime: [])
    monkeypatch.setattr(gorsel, "yerel_gorseller", lambda k: [])
    i = cekirdek.Is(kanal="gta_en", veri={"gorsel_kelimeler": ["a", "b", "c", "d", "e"]})
    gorsel.topla(i, cekirdek.kanal("gta_en"))
    assert [s["tur"] for s in i.veri["sahneler"]] == ["resim"] * 5
    assert i.veri["yapay_icerik"] is True


def test_stok_anahtari_yoksa_yapay_zeka_tamamlar(monkeypatch):
    monkeypatch.setattr(gorsel, "ai_gorsel", lambda istem, hedef, seed=0: hedef.write_bytes(b"x") or hedef)
    monkeypatch.setattr(gorsel, "stok_video", lambda kelime: [])
    monkeypatch.setattr(gorsel, "yerel_gorseller", lambda k: [])
    i = cekirdek.Is(kanal="finans_tr", veri={"gorsel_kelimeler": ["money", "bank"]})
    gorsel.topla(i, cekirdek.kanal("finans_tr"))
    assert len(i.veri["sahneler"]) == 5


def test_kisa_senaryo_genisletilir(monkeypatch):
    k = cekirdek.kanal("teknoloji_en")
    kisa = {"baslik": "T #shorts", "senaryo_cumleleri": ["Short hook here.", "Second one."], "aciklama": "a",
            "etiketler": ["x"], "gorsel_kelimeler": ["city"]}
    uzun = {"senaryo_cumleleri": [" ".join(["word"] * 12) + "." for _ in range(8)]}
    cevaplar = iter([kisa, uzun])
    monkeypatch.setattr(senarist, "sor_json", lambda *a, **kw: next(cevaplar))
    i = cekirdek.Is(kanal="teknoloji_en", veri={"konu": "AI", "kaynaklar": []})
    senarist.yaz(i, k)
    assert 70 <= len(i.veri["senaryo"].split()) <= 115
