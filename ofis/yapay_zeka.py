"""Bilgisayardaki açık kaynak dil modeline (Ollama) bağlanır."""
from __future__ import annotations

import json
import re
from typing import Any

import requests

from .cekirdek import ortam


class YapayZekaHatasi(RuntimeError):
    pass


def _adres() -> str:
    return ortam("OLLAMA_ADRES", "http://127.0.0.1:11434").rstrip("/")


def model_adi() -> str:
    return ortam("OLLAMA_MODEL", "qwen2.5:7b")


def json_ayikla(metin: str) -> Any:
    """Modelin cevabından JSON'u çıkarır; düşünme etiketlerini ve ``` bloklarını temizler."""
    metin = re.sub(r"<think>.*?</think>", "", metin, flags=re.S).strip()
    metin = re.sub(r"^```(?:json)?|```$", "", metin, flags=re.M).strip()
    try:
        return json.loads(metin)
    except json.JSONDecodeError:
        pass
    for ac, kapa in (("{", "}"), ("[", "]")):
        bas, son = metin.find(ac), metin.rfind(kapa)
        if bas != -1 and son > bas:
            try:
                return json.loads(metin[bas : son + 1])
            except json.JSONDecodeError:
                continue
    raise YapayZekaHatasi(f"Modelin cevabı JSON değil: {metin[:300]}")


def sor_json(sistem: str, kullanici: str, sicaklik: float = 0.8, deneme: int = 3) -> Any:
    son_hata: Exception | None = None
    for _ in range(deneme):
        try:
            cevap = requests.post(
                f"{_adres()}/api/chat",
                json={
                    "model": model_adi(),
                    "messages": [
                        {"role": "system", "content": sistem},
                        {"role": "user", "content": kullanici},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": sicaklik, "num_ctx": 8192},
                },
                timeout=900,
            )
            cevap.raise_for_status()
            return json_ayikla(cevap.json()["message"]["content"])
        except (requests.RequestException, KeyError, YapayZekaHatasi) as e:
            son_hata = e
    raise YapayZekaHatasi(f"Model cevap vermedi: {son_hata}")


def calisiyor_mu() -> tuple[bool, str]:
    try:
        r = requests.get(f"{_adres()}/api/tags", timeout=5)
        r.raise_for_status()
        modeller = [m["name"] for m in r.json().get("models", [])]
    except requests.RequestException:
        return False, "Ollama çalışmıyor. Ollama uygulamasını aç veya 'ollama serve' çalıştır."
    istenen = model_adi() if ":" in model_adi() else f"{model_adi()}:latest"
    if istenen not in modeller:
        return False, f"Model yüklü değil. Şunu çalıştır: ollama pull {model_adi()}"
    return True, f"Ollama hazır, model: {model_adi()}"
