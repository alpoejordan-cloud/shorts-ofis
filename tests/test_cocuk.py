"""Çocuk kanalları: hikaye kuralları, güvenlik, zamanlama, çizim ve kısa bir uçtan uca animasyon."""
import random
import shutil

import numpy as np
import pytest

from ofis import cekirdek
from ofis.cocuk import animasyon, cocuk_kanali_mi, hikaye, karakter, muzik, sahne
from ofis.cocuk import ses as cocuk_ses


def _hikaye(dil="en"):
    m = "Pip found a shiny red ball in the sunny garden today" if dil == "en" else \
        "Fıstık güneşli bahçede parlak kırmızı bir top buldu bugün çok sevindi"
    return {"baslik": "Pip and Momo share", "kanca_metni": "Whose ball is it?", "ders": "sharing",
            "sahneler": [{"yer": y, "karakterler": ["pip", "momo"],
                          "satirlar": [{"kim": "anlatici", "metin": m, "duygu": "mutlu"},
                                       {"kim": "pip", "metin": m, "duygu": "heyecanli"},
                                       {"kim": "momo", "metin": m, "duygu": "uzgun"}]}
                         for y in ("cayir", "orman", "gol")]}


def test_cocuk_kanallari_ayarli():
    for kid in ("cocuk_en", "cocuk_tr"):
        k = cekirdek.kanal(kid)
        assert cocuk_kanali_mi(k) and k["cocuklar_icin"] is True
        assert k["google_istemci"] != "client_secret.json"
        assert len(k["karakterler"]) >= 3
        assert all(c["tur"] in karakter.TURLER for c in k["karakterler"])


def test_hikaye_dogrulama():
    k = cekirdek.kanal("cocuk_en")
    h = _hikaye()
    assert hikaye.dogrula(h, k, {}) == []
    kotu = _hikaye()
    kotu["sahneler"][0]["yer"] = "uzay"
    kotu["sahneler"][1]["satirlar"][0]["kim"] = "luna"  # sahnede olmayan karakter konuşamaz
    kotu["sahneler"][2]["satirlar"][0]["metin"] = "A scary monster with a knife came"
    s = " ".join(hikaye.dogrula(kotu, k, {}))
    assert "'yer'" in s and "'kim'" in s and "monster" in s


def test_guvenlik_turkce_ekler():
    assert hikaye.guvenlik("Kanatlarını açtı, kanepede güne başladı", "tr") == []
    assert "canavar" in hikaye.guvenlik("Bir canavar geldi", "tr")
    assert hikaye.guvenlik("Fireflies glowed", "en") == []


def test_fikir_tekrar_etmez():
    k = cekirdek.kanal("cocuk_tr")
    f = hikaye.fikir_uret(k, 6, random.Random(1))
    assert len({x["tema"] for x in f}) == 6
    assert all(2 <= len(x["kadro"]) <= 3 and x["ana_yer"] in sahne.YERLER for x in f)


def test_zamanlama_ve_sure():
    h = _hikaye()
    satirlar, sahneler, toplam = cocuk_ses.zamanlama(h["sahneler"], [[2.0, 2.0, 2.0]] * 3)
    assert len(satirlar) == 9 and sahneler[0]["bas"] == 0
    assert all(a["son"] <= b["bas"] for a, b in zip(satirlar, satirlar[1:]))
    assert abs(sahneler[-1]["son"] - toplam) < 1e-6 and toplam < 30


def test_cizimler():
    for t in karakter.TURLER:
        s = karakter.sprite({"tur": t}, agiz_acik=True, duygu="saskin")
        assert s.mode == "RGBA" and s.getbbox()
    for y in sahne.YERLER:
        assert sahne.Canlandirici(y, 1, 5).kare(1.0).size == (1080, 1920)
    m = muzik.muzik_uret(5, "x")
    assert len(m) == 5 * muzik.HZ and np.max(np.abs(m)) <= 1.0


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg yok")
def test_kisa_animasyon(monkeypatch):
    k = cekirdek.kanal("cocuk_en")
    i = cekirdek.Is(kanal="cocuk_en", veri={"mod": "cocuk_hikaye", "kanca_metni": "Hi"})
    h = _hikaye()
    for sc in h["sahneler"]:
        sc["satirlar"] = sc["satirlar"][:1]
    i.veri["sahneler_hikaye"] = h["sahneler"]

    def sahte_satir(metin, kim, k, klasor, no):  # TTS yerine kısa ton
        t = np.arange(int(0.6 * muzik.HZ)) / muzik.HZ
        return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)

    monkeypatch.setattr(cocuk_ses, "satiri_seslendir", sahte_satir)
    cocuk_ses.seslendir(i, k)
    animasyon.sahne_hazirla(i, k)
    animasyon.canlandir(i, k)
    assert (i.klasor / "video.mp4").stat().st_size > 10000
    assert i.veri["kare_sayisi"] == int(np.ceil(i.veri["sure"] * animasyon.FPS))
