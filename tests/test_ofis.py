import shutil
import subprocess
import wave
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from ofis import cekirdek
from ofis.ajanlar import gorsel, kurgu, senarist, seslendirme
from ofis.ajanlar.yukleyici import sonraki_yayin_zamani
from ofis.yapay_zeka import json_ayikla


def test_kanallar_yukleniyor():
    aktif = cekirdek.kanallar()
    assert {k["id"] for k in aktif} == {"teknoloji_en", "gta_en"}  # finans_tr beklemede
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
    secim = gorsel.klip_sec(cekirdek.kanal("gta_en"))
    assert secim is None or secim["yayinci"] != "Örnek Yayıncı"


def test_altyazi_gruplama_ve_ass(tmp_path):
    zaman = seslendirme.tahmini_zamanlar("Merhaba dünya, bu bir deneme videosu.", 4.0)
    gruplar = seslendirme.kelimeleri_grupla(zaman)
    assert gruplar[0]["metin"] == "Merhaba dünya,"
    assert abs(gruplar[-1]["son"] - 4.0) < 1e-6
    yol = tmp_path / "a.ass"
    seslendirme.ass_yaz(gruplar, yol)
    metin = yol.read_text(encoding="utf-8")
    assert "PlayResY: 1920" in metin and "MERHABA" in metin and "DÜNYA," in metin


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
    i.veri = {"sure": 7.5, "sahneler": [{"tur": "video", "yol": str(tmp_path / "a.mp4")},
                                        {"tur": "resim", "yol": str(tmp_path / "b.png")},
                                        {"tur": "desen", "renkler": ["0x0f2027", "0x2c5364"]}]}
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
    monkeypatch.setattr(mudur, "BEKLEME_SN", 0)
    i = cekirdek.Is(kanal="finans_tr")
    mudur.is_ilerlet(i)  # aynı çalışmada EN_FAZLA_DENEME kez dener, sonra bırakır
    assert i.durum == "hata" and len(i.hatalar) == mudur.EN_FAZLA_DENEME


def test_ai_gorsel_sahneleri_eklenir(monkeypatch, tmp_path):
    def sahte_ai(istem, hedef, seed=0):
        hedef.write_bytes(b"x")
        return hedef

    monkeypatch.setattr(gorsel, "ai_gorsel", sahte_ai)
    monkeypatch.setattr(gorsel, "stok_video", lambda kelime: [])
    monkeypatch.setattr(gorsel, "foto_adaylari", lambda kelime: [])
    monkeypatch.setattr(gorsel, "yerel_gorseller", lambda k: [])
    i = cekirdek.Is(kanal="gta_en", veri={"gorsel_kelimeler": ["a", "b", "c", "d", "e"]})
    gorsel.topla(i, cekirdek.kanal("gta_en"))
    assert [s["tur"] for s in i.veri["sahneler"]] == ["resim"] * 5
    assert i.veri["yapay_icerik"] is True


def test_stok_anahtari_yoksa_yapay_zeka_tamamlar(monkeypatch):
    monkeypatch.setattr(gorsel, "ai_gorsel", lambda istem, hedef, seed=0: hedef.write_bytes(b"x") or hedef)
    monkeypatch.setattr(gorsel, "stok_video", lambda kelime: [])
    monkeypatch.setattr(gorsel, "foto_adaylari", lambda kelime: [])
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


def test_ses_dizisi_16khz(tmp_path):
    yol = tmp_path / "s.wav"
    with wave.open(str(yol), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050)
        wf.writeframes(b"\x00\x00" * 22050)
    dizi = seslendirme.ses_dizisi(yol)
    assert abs(len(dizi) - 16000) < 200


def test_gorsel_yoksa_renk_gecisi_eklenir(monkeypatch):
    monkeypatch.setattr(gorsel, "ai_gorsel", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("402 Payment Required")))
    monkeypatch.setattr(gorsel, "stok_video", lambda kelime: [])
    monkeypatch.setattr(gorsel, "foto_adaylari", lambda kelime: [])
    monkeypatch.setattr(gorsel, "yerel_gorseller", lambda k: [])
    i = cekirdek.Is(kanal="teknoloji_en", veri={"gorsel_kelimeler": ["a"]})
    gorsel.topla(i, cekirdek.kanal("teknoloji_en"))
    assert [s["tur"] for s in i.veri["sahneler"]] == ["desen"] * 4


def test_acik_resim_kredisi_aciklamaya_eklenir(monkeypatch, tmp_path):
    monkeypatch.setattr(gorsel, "stok_video", lambda kelime: [])
    monkeypatch.setattr(gorsel, "ai_gorsel", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("402")))
    monkeypatch.setattr(gorsel, "yerel_gorseller", lambda k: [])
    monkeypatch.setattr(gorsel, "acik_resim", lambda kelime, adet=4: [
        {"id": f"ov-{kelime}", "link": "http://x", "sayfa": "http://p", "sahip": "Ali", "baslik": "Phone",
         "lisans": "CC BY 2.0"}])
    monkeypatch.setattr(gorsel, "resim_indir", lambda url, hedef: hedef.write_bytes(b"x") or hedef)
    i = cekirdek.Is(kanal="teknoloji_en", veri={"gorsel_kelimeler": ["phone", "laptop"], "aciklama": "A"})
    gorsel.topla(i, cekirdek.kanal("teknoloji_en"))
    assert [s["tur"] for s in i.veri["sahneler"]][:2] == ["resim", "resim"]
    assert "Image credits" in i.veri["aciklama"] and "CC BY 2.0" in i.veri["aciklama"]


def test_kesim_plani_sik_kesme_ve_sure():
    sahneler = [{"tur": "desen"}, {"tur": "resim", "yol": "a.jpg"}]
    plan = kurgu.kesim_plani(sahneler, 36.0, 2.4, tohum="x")
    assert len(plan) == 15
    gorunen = sum(p["sure"] for p in plan) - kurgu.GECIS * (len(plan) - 1)
    assert abs(gorunen - 36.0) < 1e-6
    assert all(a["hareket"] != b["hareket"] for a, b in zip(plan, plan[1:]))


def test_ass_kanca_ve_ilerleme_cubugu(tmp_path):
    zaman = seslendirme.tahmini_zamanlar("This changes everything for your phone today.", 3.0)
    yol = tmp_path / "a.ass"
    seslendirme.ass_yaz(seslendirme.kelimeleri_grupla(zaman), yol, kanca="Nobody noticed this change", toplam=3.6)
    metin = yol.read_text(encoding="utf-8")
    assert ",Kanca,," in metin and "NOBODY NOTICED" in metin
    assert "\\clip(0,0,1080,1920)" in metin and ",Cubuk,," in metin
    assert metin.count(",Ana,,") == len("This changes everything for your phone today.".split())


def test_muzik_atfi_aciklamaya_eklenir(tmp_path):
    (tmp_path / "LISANSLAR.txt").write_text(
        "# yorum\nserbest.mp3 | CC0 | \"Free\" by A (CC0)\natifli.mp3 | CC BY 4.0 | Music: \"Song\" by B (CC BY 4.0)\n",
        encoding="utf-8")
    i = cekirdek.Is(kanal="teknoloji_en", veri={"aciklama": "Desc", "lisanslar": []})
    kurgu.muzik_atfini_ekle(i, str(tmp_path / "serbest.mp3"))
    assert i.veri["aciklama"] == "Desc" and i.veri["lisanslar"] == ['Müzik: "Free" by A (CC0)']
    kurgu.muzik_atfini_ekle(i, str(tmp_path / "atifli.mp3"))
    assert i.veri["aciklama"].endswith('Music: "Song" by B (CC BY 4.0)')
    kurgu.muzik_atfini_ekle(i, str(tmp_path / "atifli.mp3"))  # iki kez eklenmez
    assert i.veri["aciklama"].count("Song") == 1
    assert kurgu.muzik_atfi(str(tmp_path / "yok.mp3")) is None


def test_trend_ingilizce_kanalda_turkce_konuyu_duzeltir(monkeypatch):
    from ofis.ajanlar import trend

    from ofis import kaynak
    monkeypatch.setattr(kaynak, "makaleler", lambda k: [
        {"kaynak": "a", "baslik": "AI security flaw found", "link": "https://a/9", "ozet": ""}])
    monkeypatch.setattr(kaynak, "metin_al", lambda link: "AI security " * 60)
    monkeypatch.setattr(trend, "gemini_beyin_firtinasi", lambda f, *a, **kw: f)
    cevaplar = iter([
        {"fikirler": [{"makale_no": 1, "konu": "Yapay zekâ ve güvenlik", "aci": "Neden önemli?"}]},
        {"fikirler": [{"makale_no": 1, "konu": "AI and security", "aci": "Why it matters"}]},
    ])
    monkeypatch.setattr(trend, "sor_json", lambda *a, **kw: next(cevaplar))
    fikirler = trend.fikir_bul(cekirdek.kanal("teknoloji_en"), 1)
    assert fikirler[0]["konu"] == "AI and security"
    assert trend.dil_uygun({"konu": "Kanal dili Türkçe"}, cekirdek.kanal("finans_tr"))


def test_turkce_gorsel_kelimeleri_cevrilir_ve_buyuk_harf(monkeypatch, tmp_path):
    monkeypatch.setattr(senarist, "sor_json", lambda *a, **kw: {"terms": ["money", "budget planner"]})
    assert senarist.gorsel_kelimeleri_ingilizce(["para", "bütçe"], "tr") == ["money", "budget planner"]
    assert senarist.gorsel_kelimeleri_ingilizce(["phone"], "en") == ["phone"]
    yol = tmp_path / "t.ass"
    seslendirme.ass_yaz(seslendirme.kelimeleri_grupla(seslendirme.tahmini_zamanlar("için sınav", 1.0)), yol, dil="tr")
    assert "İÇİN" in yol.read_text(encoding="utf-8") and "SINAV" in yol.read_text(encoding="utf-8")


def test_acilis_notu_ilk_iki_saniyede(tmp_path):
    yol = tmp_path / "n.ass"
    seslendirme.ass_yaz(seslendirme.kelimeleri_grupla(seslendirme.tahmini_zamanlar("one two", 1.0)), yol,
                        acilis_notu="Clip from @Dom's stream", toplam=3.0)
    satir = [s for s in yol.read_text(encoding="utf-8").splitlines() if ",Not,," in s]
    assert len(satir) == 1 and satir[0].startswith("Dialogue: 3,0:00:00.00,0:00:02.00,")
    assert "Clip from @Dom's stream" in satir[0]


def test_kampanya_yayincilari_izin_belgesiyle_gelir():
    adlar = {y["ad"]: y for y in gorsel.izinli_yayincilar()}
    assert "Dasgasd3m (Dom)" in adlar and "Bobby VanRiper" not in adlar  # Bobby durduruldu
    assert all(y["izin_belgesi"].startswith("https://contentrewards.com/") for y in adlar.values())
    assert all(y.get("yayinci_sesi") for y in adlar.values())


def test_ass_kapanis_cagrisi_son_uc_saniye(tmp_path):
    yol = tmp_path / "k.ass"
    seslendirme.ass_yaz([], yol, toplam=20.0, kapanis="Follow Bobby on Twitch")
    satir = [s for s in yol.read_text(encoding="utf-8").splitlines() if "Follow Bobby" in s]
    assert satir and satir[0].startswith("Dialogue: 2,0:00:17.00,0:00:20.00,Kanca")


def test_altyazida_kufur_maskelenir():
    assert seslendirme.kufur_maskele("get the fuck out, shit") == "get the f*** out, s***"
    assert seslendirme.kufur_maskele("Dickens classic") == "Dickens classic"


def test_kampanya_gonderim_hatirlatici(monkeypatch):
    from ofis.ajanlar import hatirlatici

    tz = ZoneInfo("Europe/Istanbul")
    yayin = datetime(2026, 11, 25, 17, 0, tzinfo=tz)
    i = cekirdek.Is(kanal="gta_en", veri={"kampanya": "https://contentrewards.com/c/campaigns/x", "baslik": "T"})
    hatirlatici.gonderim_kaydi(i, "abc", yayin)
    i.durum = "yuklendi"
    i.kaydet()
    bildirimler = []
    sahte = lambda b, m: bildirimler.append(m)  # noqa: E731
    assert hatirlatici.kontrol(yayin - timedelta(minutes=5), bildir=sahte) == 0
    assert hatirlatici.kontrol(yayin + timedelta(minutes=2), bildir=sahte) == 1
    assert hatirlatici.kontrol(yayin + timedelta(minutes=10), bildir=sahte) == 0  # tek bildirim
    hatirlatici.kontrol(yayin + timedelta(minutes=31), bildir=sahte)
    assert cekirdek.Is.yukle(i.id).veri["kampanya_gonderim"]["durum"] == "sure_doldu"


def test_dikey_yerlesim_filtreleri():
    f = kurgu.dikey_yerlesim(1920, 1080, [0, 0, 400, 284])
    assert "vstack" in f and "crop=400:284:0:0" in f
    assert "vstack" not in kurgu.dikey_yerlesim(1920, 1080, None)


def test_seo_baslik_aciklama_etiket():
    from ofis.ajanlar import seo

    k = cekirdek.kanal("gta_en")
    veri = {"baslik": "Dom crashes a plane and the whole server laughs at him for ages #shorts",
            "aciklama": "Clip: dasgasd3m on Kick. Watch Dom live: https://kick.com/dasgasd3m #dasgasdom3\n\n"
                        "Dom crashes a plane.\n\n#dasgasdom3 #GTA6",
            "kredi": "Clip: dasgasd3m on Kick. Watch Dom live: https://kick.com/dasgasd3m #dasgasdom3",
            "zorunlu_etiketler": ["#dasgasdom3", "#GTA6"], "yayinci": "Dasgasd3m (Dom)",
            "etiketler": ["plane crash", "funny"]}
    s = seo.uygula(veri, k)
    assert len(s["title"]) <= 60 and s["title"].startswith("GTA 6") and s["title"].endswith("#shorts")
    assert s["description"].splitlines()[0].startswith("GTA 6")
    assert "kick.com/dasgasd3m" in s["description"] and "#dasgasdom3" in s["description"]
    assert 10 <= len(s["tags"]) <= 15 and sum(len(t) + 4 for t in s["tags"]) <= 500
    assert s["tags"][0] == "Dasgasd3m" and s["defaultLanguage"] == "en" and s["categoryId"] == "20"


def test_seo_ana_anahtar_hep_basta():
    from ofis.ajanlar import seo

    k = cekirdek.kanal("gta_en")
    assert seo.baslik("Bobby VanRiper GTA VI Shark #shorts", k) == "GTA 6: Bobby VanRiper Shark #shorts"
    assert seo.baslik("GTA 6 trailer breakdown", k) == "GTA 6 trailer breakdown #shorts"


def test_en_iyi_an_gurultulu_bolumu_bulur(tmp_path, monkeypatch):
    import numpy as np

    dizi = np.zeros(16000 * 90, dtype=np.float32)
    dizi[16000 * 60:16000 * 70] = 0.8  # 60-70. saniyede bağırış
    monkeypatch.setattr(seslendirme, "ses_dizisi", lambda yol: dizi)
    bas = seslendirme.en_iyi_an(tmp_path / "x.mp4", 30)
    assert 35 <= bas <= 60
    monkeypatch.setattr(seslendirme, "ses_dizisi", lambda yol: dizi[: 16000 * 20])
    assert seslendirme.en_iyi_an(tmp_path / "x.mp4", 30) == 0.0


def test_kokoro_calismazsa_piper_yedegi(monkeypatch, tmp_path):
    def bozuk(*a, **kw):
        raise RuntimeError("kokoro yok")

    cagrilan = []
    monkeypatch.setattr(seslendirme, "_kokoro_sentezle", bozuk)
    monkeypatch.setattr(seslendirme, "_ses_yukle", lambda ad: cagrilan.append(ad) or (_ for _ in ()).throw(StopIteration))
    with pytest.raises(StopIteration):
        seslendirme.sentezle("hi", "kokoro:af_heart", tmp_path / "a.wav", yedek="en_US-ryan-high")
    assert cagrilan == ["en_US-ryan-high"]


def test_temizlik_ve_gunluk_ozet():
    from datetime import datetime, timedelta

    from ofis import temizlik

    i = cekirdek.Is(kanal="teknoloji_en", veri={"baslik": "Eski"})
    i.durum = "yuklendi"
    i.kaydet()
    (i.klasor / "ham_video.mp4").write_bytes(b"x" * 2048)
    (i.klasor / "video.mp4").write_bytes(b"x")
    temizlik.temizle(ara_gun=3, video_gun=30, simdi=datetime.now() + timedelta(days=5))
    assert not (i.klasor / "ham_video.mp4").exists() and (i.klasor / "video.mp4").exists()
    metin = temizlik.gunluk_ozet()
    assert "Günlük özet" in metin and "teknoloji_en" in metin


def test_kanca_metni_alti_kelimeyi_gecmez():
    assert senarist.kanca_duzelt({"kanca_metni": "one two three four five six seven"}) == "one two three four five six"
    assert senarist.kanca_duzelt({"baslik": "Big News Today #shorts"}) == "Big News Today"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg yok")
def test_oyun_kaydindan_farkli_anlar_secilir(tmp_path, monkeypatch):
    klasor = tmp_path / "oyun"
    klasor.mkdir()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
                    "-t", "60", str(klasor / "kayit.mp4")], check=True)
    monkeypatch.setattr(gorsel, "KOK", tmp_path)
    k = {"id": "gta_en", "oyun_kayit_klasoru": "oyun", "oyun_sahne_adedi": 5}
    sahneler = gorsel.oyun_kaydi_sahneleri(k, "a")
    assert len(sahneler) == 5 and len({s["bas"] for s in sahneler}) == 5
    assert all(s["tur"] == "video" for s in sahneler)


def test_klip_basligi_zayifsa_kalip():
    from ofis.ajanlar.senarist import klip_basligi
    assert klip_basligi("Dasgasd3m #shorts", "Dasgasd3m (Dom)", "Gas price rant") == "Dasgasd3m: Gas price rant"
    assert klip_basligi("Dom loses it over GTA 6 gas prices #shorts", "Dasgasd3m", "x").startswith("Dom loses")


def test_gecici_hatada_hemen_yeniden_dener(monkeypatch, tmp_path):
    from ofis import cekirdek, mudur

    monkeypatch.setattr(mudur, "BEKLEME_SN", 0)
    monkeypatch.setattr(cekirdek.Is, "kaydet", lambda self: None)
    sayac = {"n": 0}

    def bazen_hata(is_, k):
        sayac["n"] += 1
        if sayac["n"] < 2:
            raise RuntimeError("ollama meşgul")

    adimlar = {"fikir": (bazen_hata, "video")}
    monkeypatch.setattr(mudur, "ADIMLAR", adimlar)
    i = cekirdek.Is(kanal="teknoloji_en", veri={})
    mudur.is_ilerlet(i)
    assert sayac["n"] == 2 and i.durum == "onay_bekliyor" and i.deneme == 0


def test_kalite_dil_ve_sayi():
    from ofis import kalite
    assert kalite.dil_tutuyor_mu("This is why the new phone is fast and you want it", "en")
    assert not kalite.dil_tutuyor_mu("Bu telefon neden bu kadar hızlı ve çok pahalı bir şey değil", "en")
    assert kalite.dil_tutuyor_mu("Bu telefon neden bu kadar hızlı ve çok pahalı", "tr")


def test_otomatik_onay_kapaliysa_ve_kampanyada_masaya(monkeypatch):
    from ofis import mudur
    i = cekirdek.Is(kanal="gta_en", veri={"kampanya": "https://x"})
    assert mudur.otomatik_onay_uygun(i, {"otomatik_onay": False}) is False
    assert mudur.otomatik_onay_uygun(i, {"otomatik_onay": True}) is False
    assert "kampanya" in i.veri["kalite_sorunlari"][0]
    from ofis import kalite
    monkeypatch.setattr(kalite, "kontrol", lambda is_, k: [])
    j = cekirdek.Is(kanal="teknoloji_en", veri={})
    assert mudur.otomatik_onay_uygun(j, {"otomatik_onay": True}) is True
    monkeypatch.setattr(kalite, "kontrol", lambda is_, k: ["ses seviyesi"])
    assert mudur.otomatik_onay_uygun(j, {"otomatik_onay": True}) is False


def test_gemini_anahtarsiz_sessizce_none(monkeypatch):
    from ofis import gemini
    from ofis.ajanlar import senarist
    monkeypatch.setenv("GEMINI_API_ANAHTARI", "")
    assert gemini.hazir_mi() is False and gemini.sor_json("a", "b") is None
    s = {"baslik": "x"}
    assert senarist.gemini_ile_iyilestir(s, {}, {}, "", "") == (s, None)


def test_pasif_yayinci_klibi_secilmez(monkeypatch):
    from ofis.ajanlar import gorsel
    monkeypatch.setattr(gorsel, "yaml_oku", lambda ad: {"izinli_yayincilar": [
        {"ad": "A", "izin_belgesi": "u", "klasor": "k", "aktif": False}, {"ad": "B", "izin_belgesi": "u", "klasor": "k"}]})
    assert [y["ad"] for y in gorsel.izinli_yayincilar()] == ["B"]


def test_kalite_gemini_onayi_ve_etiket(tmp_path, monkeypatch):
    from ofis import kalite
    monkeypatch.setattr(kalite, "klasor", lambda is_: tmp_path)
    (tmp_path / "video.mp4").write_bytes(b"x")
    monkeypatch.setattr(kalite, "_ffprobe", lambda y: {"streams": [{"codec_type": "audio"}], "format": {"duration": "30"}})
    monkeypatch.setattr(kalite, "ses_seviyesi", lambda y: -14.0)
    (tmp_path / "altyazi.ass").write_text("Dialogue:\nDialogue:\nDialogue:\n", encoding="utf-8")
    v = {"mod": "normal", "baslik": "This is the new phone you want", "kanca_metni": "New phone",
         "senaryo": "This is why the phone is fast. Why this matters: you and the battery."}
    s = kalite.kontrol(cekirdek.Is(kanal="teknoloji_en", veri=v), {"dil": "en"})
    assert any("kaynak makale metni yok" in x for x in s) and any("etiketi" in x for x in s)
    v2 = {**v, "senaryo": "This is why the phone is fast and you want it.", "gemini_denetim": {"onay": True},
          "kaynak_metin": str(tmp_path / "k.txt")}
    (tmp_path / "k.txt").write_text("The phone is fast.", encoding="utf-8")
    assert kalite.kontrol(cekirdek.Is(kanal="teknoloji_en", veri=v2), {"dil": "en"}) == []


def test_seo_tech_basligina_ai_zorlanmaz():
    from ofis.ajanlar import seo
    k = {"id": "teknoloji_en"}
    assert seo.baslik("Tech Privacy Shifts 2026 #shorts", k) == "Tech Privacy Shifts 2026 #shorts"
    assert seo.baslik("New phone leaks #shorts", k).startswith("AI: ")


def test_kaynakla_karsilastir():
    from ofis.kalite import kaynakla_karsilastir
    kaynak = "Rockstar confirmed GTA 6 sold 25 million copies. A leak claims a PC port; the rumor is unconfirmed by insiders."
    iyi = "GTA 6 sold 25 million copies, says Rockstar. A rumor says a PC port is coming. I think that's huge."
    assert kaynakla_karsilastir(iyi, kaynak) == []
    kotu = "GTA 6 sold 40 million copies. Then Take-Two said a PC port is coming."
    s = kaynakla_karsilastir(kotu, kaynak)
    assert any("40" in x for x in s) and any("Take-Two" in x for x in s) and any("rumor" in x for x in s)


def test_aciklama_temizle_ve_kaynak_uyusma():
    from ofis import kaynak
    from ofis.ajanlar.senarist import aciklama_temizle
    assert aciklama_temizle("Big news today. Source: Reuters\n\nSources:\nhttps://x.com/a") == "Big news today."
    assert kaynak.uyusuyor("GTA 6 Call of Duty players", "Call of Duty lost players when GTA 6 came out", "")
    assert not kaynak.uyusuyor("Apple iPhone battery recall", "Call of Duty lost players", "Activision report")


def test_trend_fikri_makaleye_baglar(monkeypatch):
    from ofis import kaynak
    from ofis.ajanlar import trend
    makaleler = [{"kaynak": "a", "baslik": "Call of Duty lost players to GTA 6", "link": "https://a/1", "ozet": ""},
                 {"kaynak": "b", "baslik": "Nintendo price", "link": "https://b/2", "ozet": ""}]
    monkeypatch.setattr(kaynak, "makaleler", lambda k: makaleler)
    monkeypatch.setattr(kaynak, "metin_al", lambda link: "x" * 500 + " call of duty players gta")
    monkeypatch.setattr(trend, "sor_json", lambda *a, **kw: {"fikirler": [
        {"makale_no": 2, "konu": "Apple battery recall", "aci": "x"},          # makaleyle uyuşmuyor -> elenir
        {"makale_no": 1, "konu": "Call of Duty players left for GTA 6", "aci": "y"}]})
    monkeypatch.setattr(trend, "gemini_beyin_firtinasi", lambda f, *a, **kw: f)
    monkeypatch.setattr(trend, "isler", lambda **kw: [], raising=False)
    sonuc = trend.fikir_bul({"id": "zz_test", "dil": "en", "nis": "gaming"}, 1)
    assert len(sonuc) == 1 and sonuc[0]["kaynaklar"] == ["https://a/1"] and sonuc[0]["kaynak_metin"]


def test_yarim_kanca_yakalanir(tmp_path, monkeypatch):
    from ofis import kalite
    monkeypatch.setattr(kalite, "klasor", lambda is_: tmp_path)
    (tmp_path / "video.mp4").write_bytes(b"x")
    monkeypatch.setattr(kalite, "_ffprobe", lambda y: {"streams": [{"codec_type": "audio"}], "format": {"duration": "30"}})
    monkeypatch.setattr(kalite, "ses_seviyesi", lambda y: -14.0)
    v = {"mod": "izinli_klip", "baslik": "This is the clip you want", "kanca_metni": "Everyone thinks it's a glitch, but"}
    assert any("yarım" in x for x in kalite.kontrol(cekirdek.Is(kanal="gta_en", veri=v), {"dil": "en"}))


def test_konu_filtresi():
    from ofis.kaynak import yasak_konu
    assert yasak_konu("Dozens of oil tankers hacked; U.S. suspects Iran") == "savaş"
    assert yasak_konu("The race to port GTA 6 to PC from a leaked build, illegally") == "korsanlık"
    assert yasak_konu("Man arrested after shooting") == "suç"
    assert yasak_konu("New vaccine claims to cure disease") == "sağlık"
    assert yasak_konu("Cumhurbaşkanı açıkladı") == "siyaset"
    assert yasak_konu("Bitcoin 100 bin doları aştı", {"id": "finans_tr"}) == "hisse/coin tavsiyesi"
    assert yasak_konu("Bitcoin rallies", {"id": "teknoloji_en"}) is None
    assert yasak_konu("Apple unveils a new iPhone with a bigger battery") is None
    assert yasak_konu("GTA 6 sold 25 million copies in its first week") is None


def test_kanca_yarim_kesilmez():
    from ofis.ajanlar import senarist
    assert senarist.kanca_duzelt({"kanca_metni": "Everyone thinks it's a glitch, but it's war"}) == "Everyone thinks it's a glitch"
    assert senarist.kanca_yarim_mi("You didn't know this but")
    assert not senarist.kanca_yarim_mi("GTA 6 broke a record")


def test_konu_filtresi_yanlis_pozitif_yok():
    from ofis.kaynak import yasak_konu
    for temiz in ["Should You Participate in the Safe Word Mission in GTA 6?", "particularly good phone",
                  "İngiltere'de aşırı sıcak", "GTA 6 60fps glitch isn't all it's cracked up to be",
                  "GTA 6 is great because of all its murderous NPCs"]:
        assert yasak_konu(temiz) is None, temiz
    assert yasak_konu("Covid aşısı yeniden gündemde") == "sağlık"


def test_uretim_pencereleri(monkeypatch):
    from datetime import datetime
    from ofis import mudur
    tech = {"id": "teknoloji_en", "gunluk_video": 2, "yayin_saatleri": ["17:00", "23:00"]}
    finans = {"id": "finans_tr", "gunluk_video": 1, "yayin_saatleri": ["20:00"]}
    assert mudur.penceredeki_slotlar(tech, "gece") == 1 and mudur.penceredeki_slotlar(tech, "aksam") == 1
    assert mudur.penceredeki_slotlar(finans, "gece") == 1 and mudur.penceredeki_slotlar(finans, "aksam") == 0
    monkeypatch.setattr(mudur, "isler", lambda *a, **kw: [])
    assert mudur.gunluk_hedef(tech, datetime(2026, 11, 25, 2, 30)) == 1
    assert mudur.gunluk_hedef(tech, datetime(2026, 11, 25, 18, 30)) == 1
    assert mudur.gunluk_hedef(finans, datetime(2026, 11, 25, 18, 30)) == 0


def test_pencere_utc_kaydini_yerel_saate_cevirir():
    from ofis import mudur
    z = mudur._yerel("2026-11-25T23:30:00+00:00")
    assert z.tzinfo is None


def test_gemini_sayac_ve_sinir(monkeypatch, tmp_path):
    from ofis import gemini
    monkeypatch.setattr(gemini, "_sayac_yolu", lambda: tmp_path / "s.json")
    monkeypatch.setenv("GEMINI_API_ANAHTARI", "x")
    monkeypatch.setenv("GEMINI_GUNLUK_SINIR", "2")
    assert gemini.hazir_mi()
    gemini._say(); gemini._say()
    assert gemini.bugunku_istek() == 2 and not gemini.hazir_mi()


def test_gemini_gelistirme_kaynak_disini_reddeder(monkeypatch):
    from ofis import gemini
    from ofis.ajanlar import senarist
    kaynak = "GTA 6 sold 25 million copies in a week, Rockstar said."
    monkeypatch.setattr(gemini, "hazir_mi", lambda: True)
    monkeypatch.setattr(gemini, "senaryoyu_akicilastir", lambda *a: ["GTA 6 sold 40 million copies, says Take-Two."])
    monkeypatch.setattr(gemini, "kanca_ve_baslik", lambda *a: {"kanca_metni": "25 million in a week", "baslik": "GTA 6 hit 25 million? #shorts"})
    monkeypatch.setattr(gemini, "seo_onerisi", lambda *a: {"etiketler": ["GTA 6 sales"], "aciklama": "GTA 6 sold 99 million."})
    s = {"senaryo": "eski", "baslik": "eski #shorts", "kanca_metni": "eski kanca", "etiketler": ["gta"], "aciklama": "eski"}
    sonuc = senarist.gemini_ile_gelistir(s, {"kelime_araligi": [1, 50]}, kaynak)
    assert sonuc["senaryo"] == "eski"                                  # kaynakta olmayan 40 / Take-Two reddedildi
    assert sonuc["kanca_metni"] == "25 million in a week"              # kaynakla uyumlu kanca alındı
    assert sonuc["etiketler"][0] == "GTA 6 sales" and sonuc["aciklama"] == "eski"  # 99 kaynakta yok


def test_analist_oneri_uretir():
    from ofis.ajanlar import analist
    o = {"video": 4, "format_ortalamalari": {"a": 100, "b": 900}, "kanca_ortalamalari": {"x": 50, "y": 70},
         "kaynak_ortalamalari": {}, "en_iyi": [{"konu": "GTA 6 sales"}]}
    notlar = analist.oneriler(o)
    assert any("'b'" in n for n in notlar) and any("GTA 6 sales" in n for n in notlar)


def test_gune_ozel_yayin_saatleri():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    k = {"yayin_saatleri": ["17:00", "23:00"], "gun_yayin_saatleri": {"2026-11-25": ["15:00", "23:00"]}}
    simdi = datetime(2026, 11, 25, 11, 0, tzinfo=ZoneInfo("Europe/Istanbul"))
    ilk = sonraki_yayin_zamani(k, [], simdi)
    assert ilk.hour == 15
    assert sonraki_yayin_zamani(k, [ilk], simdi).hour == 23
    assert sonraki_yayin_zamani(k, [ilk, ilk.replace(hour=23)], simdi).day == 26


def test_uzun_kanca_kisaltilir_yarimsa_reddedilir():
    from ofis.ajanlar import senarist
    k = {"kelime_araligi": [1, 50]}
    uzun = {"senaryo": "a b c", "baslik": "T", "gorsel_kelimeler": ["x"],
            "kanca_metni": "GTA 6 hides a secret nobody found yet"}
    assert senarist.dogrula(uzun, k) == []
    yarim = {**uzun, "kanca_metni": "Everyone thinks GTA is"}
    assert senarist.dogrula(yarim, k)


# ---- Kontrol paneli ve canlı olaylar ----
def test_olay_calisiyor_acik_ve_bitmis():
    from ofis import olay
    with olay.calisiyor("senarist", "senaryo yazıyor", is_id="is-1", kanal="teknoloji_en"):
        with olay.calisiyor(None, "düşünüyor", yz="ollama"):
            acik = olay.acik_isler(olay.oku())
            assert {o["ajan"] for o in acik} >= {"senarist"}
            assert any(o["yz"] == "ollama" and o["ajan"] == "senarist" and o["is"] == "is-1" for o in acik)
    assert not [o for o in olay.acik_isler(olay.oku()) if o["mesaj"] in ("senaryo yazıyor", "düşünüyor")]
    try:
        with olay.calisiyor("kurgu", "patlayan iş"):
            raise RuntimeError("bozuldu")
    except RuntimeError:
        pass
    son = olay.oku()[-1]
    assert son["tur"] == "hata" and "bozuldu" in son["mesaj"]


def test_olay_log_satirlari_akisa_duser():
    from ofis import olay
    from ofis.cekirdek import gunluk_al
    gunluk_al("analist").info("deneme satırı 123")
    assert any(o["mesaj"] == "deneme satırı 123" and o["ajan"] == "analist" for o in olay.oku())


def test_panel_kanal_ayari_yorumlari_korur(monkeypatch, tmp_path):
    import shutil

    import yaml

    from ofis import panel
    from ofis.cekirdek import AYAR
    shutil.copy(AYAR / "kanallar.yaml", tmp_path / "kanallar.yaml")
    monkeypatch.setattr(panel, "AYAR", tmp_path)
    once = (tmp_path / "kanallar.yaml").read_text(encoding="utf-8")
    panel.kanal_ayari_yaz("gta_en", "otomatik_onay", False)
    panel.kanal_ayari_yaz("teknoloji_en", "gunluk_video", 3)
    sonra = (tmp_path / "kanallar.yaml").read_text(encoding="utf-8")
    k = {x["id"]: x for x in yaml.safe_load(sonra)["kanallar"]}
    assert k["gta_en"]["otomatik_onay"] is False and k["teknoloji_en"]["otomatik_onay"] is True
    assert k["teknoloji_en"]["gunluk_video"] == 3 and k["gta_en"]["gunluk_video"] == 2
    assert sonra.count("\n") == once.count("\n") and "# Her kanalın kendi" in sonra


def test_panel_api_ve_eylemler():
    import json as _json
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer

    from ofis import panel
    from ofis.cekirdek import Is
    i = Is(kanal="teknoloji_en", durum="onay_bekliyor", veri={"baslik": "Panel deneme", "senaryo": "metin"})
    i.kaydet()
    h = Is(kanal="gta_en", durum="hata", hatalar=["25.11 07:40 ses: bozuk"])
    h.kaydet()
    sunucu = ThreadingHTTPServer(("127.0.0.1", 0), panel.Isleyici)
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    adres = f"http://127.0.0.1:{sunucu.server_address[1]}"
    try:
        sayfa = urllib.request.urlopen(adres + "/").read().decode("utf-8")
        assert panel.JETON in sayfa and "Canlı Ofis" in sayfa
        for yol in ("/api/canli", "/api/isler", "/api/sistem", "/api/rapor", "/api/gunluk"):
            assert isinstance(_json.loads(urllib.request.urlopen(adres + yol).read()), dict)
        veri = _json.loads(urllib.request.urlopen(adres + "/api/isler").read())
        assert any(x["id"] == i.id for x in veri["onay"]) and any(x["id"] == h.id for x in veri["hatalar"])
        sistem = _json.loads(urllib.request.urlopen(adres + "/api/sistem").read())
        assert "GEMINI_API_ANAHTARI" not in _json.dumps(sistem)  # sırlar asla panelde yok

        def post(g, jeton=panel.JETON):
            istek = urllib.request.Request(adres + "/api/eylem", data=_json.dumps(g).encode(), method="POST",
                                           headers={"Content-Type": "application/json", "X-Panel-Jeton": jeton})
            try:
                return _json.loads(urllib.request.urlopen(istek).read())
            except urllib.error.HTTPError as e:
                return {"kod": e.code}
        assert post({"eylem": "onayla", "id": i.id}, jeton="yanlis") == {"kod": 403}
        assert Is.yukle(i.id).durum == "onay_bekliyor"
        assert post({"eylem": "onayla", "id": i.id})["tamam"]
        assert Is.yukle(i.id).durum == "onaylandi"
        assert post({"eylem": "tekrar_dene", "id": h.id})["tamam"]
        assert Is.yukle(h.id).durum == "ses" and Is.yukle(h.id).deneme == 0
        assert post({"eylem": "ayar", "kanal": "gta_en", "alan": "ses", "deger": 1}) == {"kod": 400}
    finally:
        sunucu.shutdown()
