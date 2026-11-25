"""İkinci yapay zeka: Google Gemini (ücretsiz katman). Yalnızca denetçi/eleştirmen olarak çalışır.

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


def model_adi() -> str:
    return ortam("GEMINI_MODEL", "gemini-2.5-flash")


def hazir_mi() -> bool:
    if not ortam("GEMINI_API_ANAHTARI", "").strip() or time.time() < _kapali_kadar:
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
    global _istemci
    if not hazir_mi():
        return None
    try:
        from google import genai
        from google.genai import types

        if _istemci is None:
            _istemci = genai.Client(api_key=ortam("GEMINI_API_ANAHTARI"))
        cevap = _istemci.models.generate_content(
            model=model_adi(),
            contents=kullanici,
            config=types.GenerateContentConfig(
                system_instruction=sistem, temperature=sicaklik, response_mime_type="application/json"),
        )
        from .yapay_zeka import json_ayikla

        return json_ayikla(cevap.text or "")
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
