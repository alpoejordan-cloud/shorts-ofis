"""İkinci yapay zeka: Google Gemini (ücretsiz katman). Ollama yanında ikinci yapay zeka: konu puanlama, kanca/başlık seçimi,
senaryo akıcılığı, SEO önerisi ve denetim. Günlük istek sayısı sınırlıdır (GEMINI_GUNLUK_SINIR).

Ollama yazar, Gemini eleştirir, Ollama düzeltir (en fazla 2 tur). Anahtar yoksa, paket yoksa,
kota dolmuşsa ya da cevap bozuksa her fonksiyon sessizce None döner ve sistem yalnızca Ollama ile devam eder.
Anahtar: .env -> GEMINI_API_ANAHTARI (aistudio.google.com/apikey)
"""
from __future__ import annotations

import json
import time
from typing import Any

from .cekirdek import gunluk_al, ortam

log = gunluk_al("gemini")
_kapali_kadar = 0.0  # kota/erişim hatasından sonra bu saate kadar Gemini'ye hiç sorulmaz
_istemci: Any = None


# Ücretsiz katmanda denenen modeller (sırayla): biri 404/503 verirse sıradakine geçilir
YEDEK_MODELLER = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
_calisan_model: str | None = None


def model_adi() -> str:
    return _calisan_model or ortam("GEMINI_MODEL", "") or YEDEK_MODELLER[0]


def _model_sirasi() -> list[str]:
    ilk = model_adi()
    return [ilk] + [m for m in YEDEK_MODELLER if m != ilk]


def _model_yok_mu(e: Exception) -> bool:
    m = str(e)
    return "404" in m or "NOT_FOUND" in m or "503" in m or "UNAVAILABLE" in m


def _kota_mi(e: Exception) -> bool:
    m = str(e).lower()
    return "429" in m or "quota" in m or "resource_exhausted" in m


_dolu_modeller: dict[str, float] = {}  # günlük kotası dolan model -> bu saate kadar atlanır


def _sayac_yolu():
    from .cekirdek import VERI

    return VERI / "gemini_sayac.json"


def bugunku_istek() -> int:
    try:
        veri = json.loads(_sayac_yolu().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    return int(veri.get("sayi", 0)) if veri.get("tarih") == time.strftime("%Y-%m-%d") else 0


def _say() -> None:
    _sayac_yolu().write_text(json.dumps({"tarih": time.strftime("%Y-%m-%d"), "sayi": bugunku_istek() + 1}),
                             encoding="utf-8")


def gunluk_sinir() -> int:
    # ücretsiz katman günlük istek sınırının altında kalmak için (değiştir: .env GEMINI_GUNLUK_SINIR)
    return int(ortam("GEMINI_GUNLUK_SINIR", "150") or 150)


def hazir_mi() -> bool:
    if not ortam("GEMINI_API_ANAHTARI", "").strip() or time.time() < _kapali_kadar:
        return False
    if bugunku_istek() >= gunluk_sinir():
        return False
    try:
        import google.genai  # noqa: F401
    except ImportError:
        return False
    return True


def _kapat(sn: float, neden: str) -> None:
    global _kapali_kadar
    _kapali_kadar = time.time() + sn
    log.warning("Gemini %d dk devre dışı (%s); yalnızca Ollama ile devam", int(sn // 60), neden)


def sor_json(sistem: str, kullanici: str, sicaklik: float = 0.3) -> Any | None:
    """Gemini'ye sorar, JSON döner. Her türlü hatada None (sistem durmaz)."""
    global _istemci, _calisan_model
    if not hazir_mi():
        return None
    try:
        from google import genai
        from google.genai import types

        from .yapay_zeka import json_ayikla

        if _istemci is None:
            _istemci = genai.Client(api_key=ortam("GEMINI_API_ANAHTARI"))
        ayar = types.GenerateContentConfig(system_instruction=sistem, temperature=sicaklik,
                                           response_mime_type="application/json")
        son_hata: Exception | None = None
        for model in _model_sirasi():
            if _dolu_modeller.get(model, 0) > time.time():
                continue
            try:
                _say()
                from .olay import cagiran_gorev, calisiyor

                with calisiyor(None, cagiran_gorev(), yz="gemini", model=model):
                    cevap = _istemci.models.generate_content(model=model, contents=kullanici, config=ayar)
            except Exception as e:
                if _model_yok_mu(e):  # model kaldırılmış ya da yoğun: sıradakini dene
                    son_hata = e
                    continue
                if _kota_mi(e):  # bu modelin günlük kotası doldu: 1 saat atla, sıradaki modeli dene
                    _dolu_modeller[model] = time.time() + 3600
                    log.info("Gemini %s kotası doldu, sıradaki model deneniyor", model)
                    son_hata = e
                    continue
                raise
            _calisan_model = model
            return json_ayikla(cevap.text or "")
        raise son_hata or RuntimeError("Gemini modeli yok")
    except Exception as e:  # kota, ağ, geçersiz anahtar, bozuk JSON
        metin = str(e).lower()
        if "429" in metin or "quota" in metin or "resource_exhausted" in metin:
            _kapat(3600, "kota doldu")
        elif "api key" in metin or "permission" in metin or "401" in metin or "403" in metin:
            _kapat(6 * 3600, "anahtar geçersiz")
        else:
            log.info("Gemini cevap vermedi: %s", str(e)[:200])
        return None


def senaryo_denetle(s: dict[str, Any], k: dict[str, Any], fikir: dict[str, Any]) -> dict[str, Any] | None:
    """Senaryo/başlık/SEO denetimi. {"onay": bool, "sorunlar": [...], "uydurma_suphesi": [...]} döner."""
    sistem = (
        "You are a strict YouTube Shorts editor and fact-checker. You review a script written by another AI. "
        "Check: hook strength in the first sentence, retention (every sentence adds something), title clarity and "
        "SEO (main keyword early, under 60 chars, no clickbait lies), correct output language, and above all "
        "fabricated facts: numbers, dates, quotes or claims that are not supported by the topic/sources and are "
        "not presented as rumor or opinion. Respond with JSON only."
    )
    kullanici = json.dumps({
        "channel_niche": k.get("nis"), "language": k.get("dil"),
        "topic": fikir.get("konu"), "angle": fikir.get("aci"), "sources": fikir.get("kaynaklar", []),
        "title": s.get("baslik"), "hook_text": s.get("kanca_metni"), "narration": s.get("senaryo"),
        "description": s.get("aciklama"), "tags": s.get("etiketler"),
    }, ensure_ascii=False) + """

JSON fields:
- "onay": true only if the script is ready to publish as is
- "sorunlar": list of concrete problems with fix instructions (in English, max 6, empty if none)
- "uydurma_suphesi": list of exact claims/numbers that look invented or unverifiable (empty if none)
- "puan": overall quality 1-10"""
    cevap = sor_json(sistem, kullanici)
    if not isinstance(cevap, dict):
        return None
    return {
        "onay": bool(cevap.get("onay")),
        "sorunlar": [str(x) for x in cevap.get("sorunlar") or []][:6],
        "uydurma_suphesi": [str(x) for x in cevap.get("uydurma_suphesi") or []][:6],
        "puan": cevap.get("puan"),
    }


def fikirleri_elestir(fikirler: list[dict[str, Any]], k: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Fikir beyin fırtınası: her fikre puan ve eleştiri. [{"no", "puan", "elestiri", "daha_iyi_aci"}] döner."""
    sistem = (
        "You are a YouTube Shorts growth strategist. Another AI proposed video ideas. Score each idea 1-10 for "
        "viral potential in the channel's niche today, originality of the angle and factual safety (no unverifiable "
        "rumors presented as facts, no politics/tragedy). Give a sharper angle if you can. Respond with JSON only."
    )
    kullanici = json.dumps({
        "channel_niche": k.get("nis"), "language": k.get("dil"),
        "ideas": [{"no": n + 1, "konu": f.get("konu"), "aci": f.get("aci"), "neden": f.get("neden")}
                  for n, f in enumerate(fikirler)],
    }, ensure_ascii=False) + (
        '\n\nJSON: {"degerlendirme": [{"no": 1, "puan": 7, "elestiri": "...", '
        f'"daha_iyi_aci": "... (write in the channel language: {k.get("dil")})"}}]}}'
    )
    cevap = sor_json(sistem, kullanici, sicaklik=0.5)
    if not isinstance(cevap, dict) or not isinstance(cevap.get("degerlendirme"), list):
        return None
    return [d for d in cevap["degerlendirme"] if isinstance(d, dict)]


# ---- Genişletilmiş görevler (anahtar varsa). Her biri başarısızsa None döner; çağıran Ollama sonucunu korur. ----

def makaleleri_puanla(makaleler: list[dict[str, Any]], k: dict[str, Any]) -> list[int] | None:
    """RSS adaylarını izlenme potansiyeline göre sıralar; makale indekslerini en iyiden kötüye döner."""
    sistem = ("You are a YouTube Shorts growth strategist. Rank news articles by expected Shorts views for this "
              "channel: broad curiosity, freshness, strong visual/hook potential, fit to the niche. Respond with JSON only.")
    kullanici = json.dumps({
        "channel_niche": k.get("nis"), "language": k.get("dil"),
        "articles": [{"no": n + 1, "title": m.get("baslik"), "summary": str(m.get("ozet", ""))[:160],
                      "age_hours": m.get("yas_saat")} for n, m in enumerate(makaleler[:40])],
    }, ensure_ascii=False) + '\n\nJSON: {"siralama": [3, 1, 7, ...]}  (article numbers, best first, at least 15)'
    cevap = sor_json(sistem, kullanici, sicaklik=0.2)
    if not isinstance(cevap, dict) or not isinstance(cevap.get("siralama"), list):
        return None
    sira: list[int] = []
    for no in cevap["siralama"]:
        try:
            i = int(no) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= i < min(len(makaleler), 40) and i not in sira:
            sira.append(i)
    return sira or None


def kanca_ve_baslik(s: dict[str, Any], k: dict[str, Any], kaynak_metni: str) -> dict[str, str] | None:
    """5 kanca + 5 başlık seçeneği yazar, en iyisini seçer. {"kanca_metni", "baslik"}."""
    sistem = ("You write viral YouTube Shorts hooks and titles. Write 5 on-screen hook options (3-6 words, complete "
              "phrase, never cut off) and 5 title options (under 60 chars, curiosity + main keyword in the first "
              "3 words, no clickbait lies, ends with #shorts). Use ONLY facts in the source article; no new numbers "
              "or names. Then pick the best of each. Respond with JSON only.")
    kullanici = json.dumps({"language": k.get("dil"), "niche": k.get("nis"), "current_title": s.get("baslik"),
                            "current_hook": s.get("kanca_metni"), "narration": s.get("senaryo"),
                            "source_article": kaynak_metni[:4000]}, ensure_ascii=False) + (
        '\n\nJSON: {"kancalar": ["..."], "basliklar": ["..."], "en_iyi_kanca": "...", "en_iyi_baslik": "..."}')
    cevap = sor_json(sistem, kullanici, sicaklik=0.7)
    if not isinstance(cevap, dict) or not cevap.get("en_iyi_kanca") or not cevap.get("en_iyi_baslik"):
        return None
    return {"kanca_metni": str(cevap["en_iyi_kanca"]).strip(), "baslik": str(cevap["en_iyi_baslik"]).strip()}


def senaryoyu_akicilastir(s: dict[str, Any], k: dict[str, Any], kaynak_metni: str) -> list[str] | None:
    """Ollama taslağını akıcılık ve izleyici tutma için yeniden yazar (yalnız kaynak bilgileriyle)."""
    alt, ust = k.get("kelime_araligi", [60, 100])
    sistem = (
        "You are a senior YouTube Shorts script editor. Rewrite the draft narration for flow and retention: "
        "sentence 1 is a tension hook, every sentence adds new info, the last sentence loops back into sentence 1. "
        f"6-8 sentences, {alt}-{ust} words total, language: {k.get('dil')}. STRICT: use ONLY facts from the source "
        "article; do not add any number, date, name, company, product or claim that is not in it; keep rumors "
        "labelled as rumor/reportedly; at most one clearly marked opinion sentence. No labels, no emojis. "
        "Respond with JSON only.")
    kullanici = json.dumps({"draft": s.get("senaryo_cumleleri") or s.get("senaryo"),
                            "source_article": kaynak_metni[:5000]}, ensure_ascii=False) + (
        '\n\nJSON: {"senaryo_cumleleri": ["...", "..."]}')
    cevap = sor_json(sistem, kullanici, sicaklik=0.5)
    cumleler = cevap.get("senaryo_cumleleri") if isinstance(cevap, dict) else None
    return [str(c).strip() for c in cumleler if str(c).strip()] if isinstance(cumleler, list) and cumleler else None


def seo_onerisi(veri: dict[str, Any], k: dict[str, Any]) -> dict[str, Any] | None:
    """Videoya özel etiket (10-15) ve 2 cümlelik açıklama önerisi."""
    sistem = ("You are a YouTube SEO specialist for Shorts. Suggest 10-15 search tags people actually type and a "
              "2-sentence description with the main keyword in the first sentence. Use only facts in the narration. "
              "No links, no hashtags in tags. Respond with JSON only.")
    kullanici = json.dumps({"language": k.get("dil"), "niche": k.get("nis"), "title": veri.get("baslik"),
                            "narration": veri.get("senaryo")}, ensure_ascii=False) + (
        '\n\nJSON: {"etiketler": ["..."], "aciklama": "..."}')
    cevap = sor_json(sistem, kullanici, sicaklik=0.3)
    if not isinstance(cevap, dict):
        return None
    etiket = [str(e).strip().lstrip("#") for e in cevap.get("etiketler") or [] if str(e).strip()][:15]
    return {"etiketler": etiket, "aciklama": str(cevap.get("aciklama") or "").strip()}


def baglanti_testi() -> tuple[bool, str]:
    """Doktor için: anahtar var mı, geçerli mi, model erişilebilir mi (küçük bir istek). Anahtarı yazdırmaz."""
    anahtar = ortam("GEMINI_API_ANAHTARI", "").strip()
    if not anahtar:
        return False, "İsteğe bağlı: .env'de GEMINI_API_ANAHTARI satırı yok (aistudio.google.com/apikey)"
    try:
        from google import genai

        global _calisan_model
        istemci = genai.Client(api_key=anahtar)  # referans tutulmazsa istemci istekten önce kapanıyor
        son: Exception | None = None
        for model in _model_sirasi():
            try:
                istemci.models.generate_content(model=model, contents="Say OK")
            except Exception as e:
                if _model_yok_mu(e):
                    son = e
                    continue
                raise
            _say()
            _calisan_model = model
            return True, f"Gemini bağlı ({model}), bugün {bugunku_istek()}/{gunluk_sinir()} istek"
        raise son or RuntimeError("model yok")
    except ImportError:
        return False, "google-genai paketi yok: pip install -r requirements.txt"
    except Exception as e:
        m = str(e)
        if "API_KEY_INVALID" in m or "400" in m and "key" in m.lower():
            return False, "Anahtar geçersiz: aistudio.google.com/apikey adresinden yeni anahtar kopyala"
        if "403" in m or "PERMISSION" in m:
            return False, "Anahtarın bu API'ye izni yok (403): AI Studio'dan oluşturulan anahtarı kullan"
        if "429" in m or "RESOURCE_EXHAUSTED" in m:
            return True, "Anahtar geçerli; şu an kota dolu (429), sistem Ollama ile devam eder"
        if "404" in m or "not found" in m.lower():
            return False, f"Hiçbir model yanıt vermedi ({', '.join(_model_sirasi())}); daha sonra tekrar dene"
        return False, f"Gemini cevap vermedi: {m[:120]}"
