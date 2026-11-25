"""Hikaye: çocuk kanalları için özgün, kısa, dersli hikayeler.

1. fikir_uret: tema (paylaşmak, cesaret, renkler, sayılar...), mekan ve karakterleri sırayla döndürür;
   son videolarda kullanılan tema/ikili tekrar edilmez (seri üretim kalıbı olmasın).
2. yaz: Ollama hikayeyi sahne sahne JSON olarak yazar (konuşan, metin, duygu). Gemini varsa
   hikayeyi cilalar ve 3-8 yaş uygunluğunu denetler. Kurallara uymayan taslak yeniden yazılır.

Kurallar: korkutucu, şiddet, tehlikeli taklit edilebilir davranış, marka, ünlü/telifli karakter,
reklam ve "abone ol" baskısı yok. Her hikayede net ve olumlu bir ders var.
"""
from __future__ import annotations

import json
import random
import re
from collections import Counter
from typing import Any

from ..cekirdek import Is, gunluk_al, isler
from ..yapay_zeka import sor_json
from .sahne import YER_ADLARI, YERLER

log = gunluk_al("hikaye")

TEMALAR = {
    "en": [
        "sharing toys with a friend", "saying sorry and making up", "being brave on the first day of school",
        "trying a new vegetable", "helping a friend who is sad", "telling the truth after a small mistake",
        "waiting patiently for a turn", "learning colors of the rainbow", "counting to five together",
        "shapes all around us (circle, square, triangle)", "cleaning up after playing", "being kind to a new friend",
        "not giving up when something is hard", "saying thank you", "a gentle bedtime and not fearing the dark",
        "teamwork to finish a task", "why we brush our teeth", "the four seasons", "where animals live",
        "listening to each other", "including someone who is left out", "taking care of a little plant",
        "big and small, fast and slow (opposites)", "being a good loser in a game", "sharing a snack fairly",
        "asking for help", "washing hands before eating", "calming down when angry (deep breaths)",
        "the days of the week", "a happy surprise for a friend's birthday",
    ],
    "tr": [
        "oyuncaklarını arkadaşıyla paylaşmak", "özür dileyip barışmak", "okulun ilk gününde cesur olmak",
        "yeni bir sebzeyi denemek", "üzgün bir arkadaşa yardım etmek", "küçük bir hatadan sonra doğruyu söylemek",
        "sırasını sabırla beklemek", "gökkuşağının renklerini öğrenmek", "birlikte beşe kadar saymak",
        "çevremizdeki şekiller (daire, kare, üçgen)", "oyundan sonra ortalığı toplamak",
        "yeni bir arkadaşa nazik olmak", "zor bir şeyde pes etmemek", "teşekkür etmek",
        "uyku vakti ve karanlıktan korkmamak", "birlikte çalışıp işi bitirmek", "neden dişlerimizi fırçalarız",
        "dört mevsim", "hayvanlar nerede yaşar", "birbirini dinlemek", "dışarıda kalan birini oyuna katmak",
        "küçük bir fideye bakmak", "büyük-küçük, hızlı-yavaş (zıt kavramlar)", "oyunda kaybetmeyi kabullenmek",
        "atıştırmalığı adil paylaşmak", "yardım istemek", "yemekten önce elleri yıkamak",
        "kızınca sakinleşmek (derin nefes)", "haftanın günleri", "arkadaşa doğum günü sürprizi",
    ],
}
DUYGULAR = ("mutlu", "saskin", "uzgun", "heyecanli")
ANLATICI = "anlatici"
YASAK = {
    "en": ["kill", "dead", "die", "blood", "gun", "knife", "monster", "ghost", "scary", "terrified", "hate",
           "stupid", "idiot", "shut up", "fire", "poison", "lost forever", "kidnap", "fight", "punch", "hit him",
           "hit her", "subscribe", "like and", "buy", "toy store", "disney", "pokemon", "peppa", "bluey",
           "paw patrol", "cocomelon", "spider-man", "spiderman", "elsa", "mickey", "barbie", "minecraft"],
    "tr": ["öldür", "ölü", "öldü", "kan ", "silah", "bıçak", "canavar", "hayalet", "korkunç", "nefret", "aptal",
           "salak", "sus be", "yangın", "zehir", "kaçırıl", "kavga", "yumrukla", "abone ol", "satın al",
           "disney", "pokemon", "peppa", "bluey", "paw patrol", "cocomelon", "örümcek adam", "elsa", "mickey",
           "barbie", "minecraft", "pepee", "rafadan", "kral şakir", "niloya", "maşa"],
}
DIL_ADI = {"tr": "Türkçe (Turkish)", "en": "English"}


def tema_listesi(k: dict[str, Any]) -> list[str]:
    return list(k.get("temalar") or TEMALAR.get(k.get("dil", "en"), TEMALAR["en"]))


def fikir_uret(k: dict[str, Any], adet: int, rnd: random.Random | None = None) -> list[dict[str, Any]]:
    """En az kullanılan tema, mekan ve karakter ikililerinden yeni hikaye fikirleri."""
    rnd = rnd or random.Random()
    gecmis = [i.veri for i in isler(kanal_id=k["id"])][-40:]
    tema_say = Counter(v.get("tema") for v in gecmis)
    yer_say = Counter(v.get("ana_yer") for v in gecmis)
    kadro = [str(c["id"]) for c in k.get("karakterler", [])]
    kar_say = Counter(c for v in gecmis for c in v.get("kadro", []))
    fikirler = []
    for _ in range(adet):
        temalar = tema_listesi(k)
        en_az = min(tema_say.get(t, 0) for t in temalar)
        tema = rnd.choice([t for t in temalar if tema_say.get(t, 0) == en_az])
        yerler = [y for y in k.get("yerler", YERLER) if y in YERLER] or list(YERLER)
        en_az_y = min(yer_say.get(y, 0) for y in yerler)
        yer = rnd.choice([y for y in yerler if yer_say.get(y, 0) == en_az_y])
        sirali = sorted(kadro, key=lambda c: (kar_say.get(c, 0), rnd.random()))
        secilen = sirali[: rnd.choice([2, 2, 3])] if len(sirali) >= 2 else sirali
        tema_say[tema] += 1
        yer_say[yer] += 1
        for c in secilen:
            kar_say[c] += 1
        fikirler.append({"mod": "cocuk_hikaye", "tema": tema, "ana_yer": yer, "kadro": secilen,
                         "konu": f"{tema} | {yer} | {', '.join(secilen)}"})
    return fikirler


def _kelime(metin: str) -> int:
    return len(str(metin).split())


def dogrula(h: Any, k: dict[str, Any], fikir: dict[str, Any]) -> list[str]:
    """Hikaye JSON'unun kurallara uyup uymadığı. Boş liste = geçti."""
    if not isinstance(h, dict):
        return ["JSON object expected"]
    sorunlar: list[str] = []
    kadro = {str(c["id"]) for c in k.get("karakterler", [])}
    sahneler = h.get("sahneler")
    if not isinstance(sahneler, list) or not 3 <= len(sahneler) <= 5:
        return ["'sahneler' must be a list of 3 to 5 scenes"]
    toplam = 0
    for i, s in enumerate(sahneler):
        if not isinstance(s, dict):
            return [f"scene {i + 1} must be an object"]
        if s.get("yer") not in YERLER:
            sorunlar.append(f"scene {i + 1}: 'yer' must be one of {list(YERLER)}")
        kar = s.get("karakterler")
        if not isinstance(kar, list) or not 1 <= len(kar) <= 3 or not set(map(str, kar)) <= kadro:
            sorunlar.append(f"scene {i + 1}: 'karakterler' must be 1-3 ids from {sorted(kadro)}")
            kar = []
        satirlar = s.get("satirlar")
        if not isinstance(satirlar, list) or not satirlar:
            sorunlar.append(f"scene {i + 1}: 'satirlar' is empty")
            continue
        for j, st in enumerate(satirlar):
            if not isinstance(st, dict) or not str(st.get("metin", "")).strip():
                sorunlar.append(f"scene {i + 1} line {j + 1}: empty")
                continue
            if st.get("kim") != ANLATICI and st.get("kim") not in kar:
                sorunlar.append(f"scene {i + 1} line {j + 1}: 'kim' must be '{ANLATICI}' or a character in this scene")
            if st.get("duygu") not in DUYGULAR:
                st["duygu"] = "mutlu"
            if _kelime(st["metin"]) > 24:
                sorunlar.append(f"scene {i + 1} line {j + 1}: too long, max 20 words per line")
            toplam += _kelime(st["metin"])
    alt, ust = k.get("kelime_araligi", [85, 120])
    if not int(alt * 0.85) <= toplam <= int(ust * 1.1):
        sorunlar.append(f"story has {toplam} words, it must be {alt}-{ust} words")
    if not h.get("baslik") or len(str(h["baslik"])) > 80:
        sorunlar.append("'baslik' empty or longer than 70 characters")
    kanca = str(h.get("kanca_metni", ""))
    if not kanca or _kelime(kanca) > 6:
        sorunlar.append("'kanca_metni' must be 2-6 words")
    if not str(h.get("ders", "")).strip():
        sorunlar.append("'ders' (the lesson) is empty")
    metin = " ".join([str(h.get("baslik", "")), kanca] + [str(st.get("metin", "")) for s in sahneler
                                                           for st in s.get("satirlar", []) if isinstance(st, dict)])
    yasak = guvenlik(metin, k.get("dil", "en"))
    if yasak:
        sorunlar.append("not allowed for young children, remove: " + ", ".join(yasak))
    if k.get("dil") == "en" and sum(c in "ğüşıöçĞÜŞİÖÇ" for c in metin) > 2:
        sorunlar.append("write in English only")
    if k.get("dil") == "tr" and not re.search(r"[ğüşıöçĞÜŞİÖÇ]", metin):
        sorunlar.append("Türkçe yaz (Turkish only)")
    return sorunlar


def guvenlik(metin: str, dil: str) -> list[str]:
    """Küçük çocuklara uygun olmayan sözcükler. İngilizce sözcükler tam kelime, Türkçeler kök olarak aranır
    (ek alabilsin); sonunda boşluk olan Türkçe sözcük ("kan ") tam kelime aranır (kanat, kanepe takılmasın)."""
    kucuk = " " + metin.replace("İ", "i").replace("I", "ı" if dil == "tr" else "i").lower() + " "
    bulunan = []
    listeler = [(w, True) for w in YASAK["en"]] + ([(w, w.endswith(" ")) for w in YASAK["tr"]] if dil == "tr" else [])
    for w, tam in listeler:
        desen = r"(?<![a-zçğıöşü])" + re.escape(w.strip()) + (r"(?![a-zçğıöşü])" if tam else "")
        if re.search(desen, kucuk):
            bulunan.append(w.strip())
    return sorted(set(bulunan))


def _kadro_metni(k: dict[str, Any], ids: list[str]) -> str:
    satirlar = []
    for c in k.get("karakterler", []):
        isaret = " (USE IN THIS STORY)" if str(c["id"]) in ids else ""
        satirlar.append(f'- id "{c["id"]}": {c.get("ad", c["id"])}, {c.get("kisilik", "")}{isaret}')
    return "\n".join(satirlar)


def istem(k: dict[str, Any], fikir: dict[str, Any]) -> tuple[str, str]:
    dil = DIL_ADI.get(k.get("dil", "en"), "English")
    alt, ust = k.get("kelime_araligi", [85, 120])
    son = [i.veri.get("baslik") for i in isler(kanal_id=k["id"]) if i.veri.get("baslik")][-12:]
    sistem = (
        f"You are an award-winning children's picture-book author writing very short animated stories for "
        f"ages 3-7. Write ONLY in {dil}. Use simple words, short sentences, warmth and gentle humor. Every story "
        "has a tiny problem, a kind solution and a clear positive lesson. Characters are original animal friends. "
        "Nothing scary, violent, dangerous to imitate, mean, sad for long, commercial or about real brands, "
        "celebrities or other cartoons. Never ask viewers to subscribe or buy anything. Respond with JSON only."
    )
    yerler = ", ".join(f"{y} ({YER_ADLARI[y]})" for y in YERLER)
    kullanici = f"""OUTPUT LANGUAGE: {dil}. All text values must be in {dil}.
Channel: {k.get('nis', '')}
Lesson/theme of this story: {fikir['tema']}
Main place: {fikir['ana_yer']}
Characters (use ONLY these ids, mainly the ones marked):
{_kadro_metni(k, fikir.get('kadro', []))}
Places you can use (scene 'yer' value): {yerler}
Do NOT repeat these earlier stories: {json.dumps(son, ensure_ascii=False)}

Story rules:
- 3 to 5 scenes, total {alt}-{ust} words (about 45 seconds when read aloud slowly).
- The FIRST line is a hook that makes a child curious right away (a question, a surprise, a funny problem); no greeting.
- Characters talk to each other (dialogue), the narrator ("{ANLATICI}") connects the scenes. Each line max 18 words.
- The LAST line is said by the narrator: the lesson in one warm, simple sentence.
- Characters are named by their names in the text; keep their personality.

JSON fields:
- "baslik": YouTube title under 60 characters: character names + what happens, curious and friendly, in {dil}
- "kanca_metni": 2-5 word on-screen hook for the first 3 seconds, no emojis
- "ders": the lesson in a short phrase
- "sahneler": list of scenes, each {{"yer": place id, "karakterler": [character ids in the scene], "satirlar": [{{"kim": "{ANLATICI}" or a character id in the scene, "metin": "spoken line", "duygu": one of {list(DUYGULAR)}}}]}}
- "aciklama": 2 sentence YouTube description for parents (what the story teaches), in {dil}
- "etiketler": 8-12 tags in {dil}"""
    return sistem, kullanici


def gemini_cila(h: dict[str, Any], k: dict[str, Any], fikir: dict[str, Any], sistem: str) -> dict[str, Any] | None:
    from .. import gemini

    if not gemini.hazir_mi():
        return None
    istek = (f"Improve this children's story for ages 3-7 so it is more charming, funny and easy to follow, "
             f"with a strong first-second hook and natural dialogue. Keep the same JSON structure, the same "
             f"character ids and place ids, the same language and the same length rules "
             f"({k.get('kelime_araligi', [85, 120])}). Lesson: {fikir['tema']}.\n\n"
             f"{json.dumps(h, ensure_ascii=False)}")
    yeni = gemini.sor_json(sistem, istek, sicaklik=0.7)
    return yeni if isinstance(yeni, dict) else None


def gemini_denetim(h: dict[str, Any], k: dict[str, Any]) -> dict[str, Any] | None:
    """Çocuk güvenliği ve kalite denetimi: {"onay", "puan", "sorunlar"}."""
    from .. import gemini

    if not gemini.hazir_mi():
        return None
    sistem = ("You review stories for a YouTube channel that is 'Made for Kids' (ages 3-7). Be strict about "
              "safety and YouTube's kids quality principles. Respond with JSON only.")
    istek = (f"Language should be {DIL_ADI.get(k.get('dil', 'en'))}. Check: age-appropriate, nothing scary/violent/"
             "dangerous to imitate, no brands or existing cartoon characters, kind and positive lesson, coherent "
             "and easy to follow, correct and natural grammar, an engaging first line, no calls to subscribe/buy.\n"
             'JSON: {"onay": true/false, "puan": 1-10, "sorunlar": ["..."]}\n\n'
             + json.dumps(h, ensure_ascii=False))
    cevap = gemini.sor_json(sistem, istek, sicaklik=0.1)
    if not isinstance(cevap, dict) or "onay" not in cevap:
        return None
    puan = int(cevap.get("puan") or 0) if str(cevap.get("puan", "0")).isdigit() else 0
    return {"onay": bool(cevap.get("onay")) and puan >= 7, "puan": puan,
            "sorunlar": [str(x) for x in cevap.get("sorunlar", [])][:6], "uydurma_suphesi": []}


def yaz(is_: Is, k: dict[str, Any]) -> None:
    fikir = is_.veri
    sistem, kullanici = istem(k, fikir)
    h: Any = None
    sorunlar: list[str] = []
    for _ in range(3):
        h = sor_json(sistem, kullanici, sicaklik=0.85)
        sorunlar = dogrula(h, k, fikir)
        if not sorunlar:
            break
        log.info("%s: hikaye düzeltiliyor (%s)", is_.id, "; ".join(sorunlar[:4]))
        kullanici += "\n\nYour previous answer had problems, fix ALL of them: " + "; ".join(sorunlar[:8])
    else:
        raise ValueError(f"Hikaye 3 denemede kurallara uymadı: {sorunlar[:4]}")
    cila = gemini_cila(h, k, fikir, sistem)
    if cila and not dogrula(cila, k, fikir):
        h = cila
        log.info("%s: hikaye Gemini ile cilalandı", is_.id)
    denetim = gemini_denetim(h, k)
    if denetim and not denetim["onay"]:  # bir tur düzeltme
        log.info("%s: Gemini çocuk denetimi (puan %s): %s", is_.id, denetim["puan"], "; ".join(denetim["sorunlar"]))
        try:
            yeni = sor_json(sistem, kullanici + "\n\nYour previous JSON:\n" + json.dumps(h, ensure_ascii=False)
                            + "\n\nEditor feedback, fix ALL of it:\n- " + "\n- ".join(denetim["sorunlar"]),
                            sicaklik=0.6)
        except Exception as e:
            yeni = None
            log.info("%s: düzeltme alınamadı: %s", is_.id, e)
        if isinstance(yeni, dict) and not dogrula(yeni, k, fikir):
            h = yeni
            denetim = gemini_denetim(h, k) or denetim
    hikayeyi_kaydet(is_, k, h, denetim)


def hikayeyi_kaydet(is_: Is, k: dict[str, Any], h: dict[str, Any], denetim: dict[str, Any] | None) -> None:
    """Doğrulanmış hikayeyi işe yazar (başlık, sahneler, açıklama, etiketler)."""
    fikir = is_.veri
    sahneler = [{"yer": s["yer"], "karakterler": [str(c) for c in s["karakterler"]],
                 "satirlar": [{"kim": str(st["kim"]), "metin": str(st["metin"]).strip(),
                               "duygu": st.get("duygu", "mutlu")} for st in s["satirlar"]]} for s in h["sahneler"]]
    adlar = {str(c["id"]): str(c.get("ad", c["id"])) for c in k.get("karakterler", [])}
    kullanilan = [adlar[c] for c in dict.fromkeys(c for s in sahneler for c in s["karakterler"])]
    senaryo = " ".join(st["metin"] for s in sahneler for st in s["satirlar"])
    aciklama = str(h.get("aciklama", "")).strip()
    ders_satiri = ("Lesson: " if k.get("dil") == "en" else "Bu hikayenin dersi: ") + str(h.get("ders", "")).strip()
    aciklama = "\n\n".join(x for x in [aciklama, ders_satiri, k.get("aciklama_eki", "")] if x)
    is_.veri.update({
        "format": "hikaye: " + fikir["tema"],
        "baslik": str(h["baslik"]).replace("#shorts", "").strip(),
        "kanca_metni": str(h["kanca_metni"]).strip(),
        "ders": str(h.get("ders", "")).strip(),
        "sahneler_hikaye": sahneler,
        "senaryo": senaryo,
        "aciklama": aciklama,
        "etiketler": [str(e) for e in h.get("etiketler", [])][:12] + kullanilan,
        "gorsel_kelimeler": [],
        "yapay_icerik": False,  # çizgi animasyon: gerçekçi yapay zeka içeriği değil
        "cocuk_denetim": denetim,
    })
    log.info("%s: hikaye hazır: %s (%d sahne, %d kelime)", is_.id, is_.veri["baslik"], len(sahneler),
             _kelime(senaryo))


def hazir_hikaye_is(k: dict[str, Any], h: dict[str, Any], tema: str = "") -> Is:
    """Elle (ya da Claude tarafından) yazılmış hazır hikayeden iş açar: kurallar ve Gemini çocuk
    denetimi aynen uygulanır, yazım adımı atlanır. Dosya biçimi: hikayeler/*.json"""
    tema = tema or str(h.get("tema") or h.get("ders") or "hazır hikaye")
    ilk = h.get("sahneler", [{}])[0]
    i = Is(kanal=k["id"], veri={"mod": "cocuk_hikaye", "tema": tema, "ana_yer": ilk.get("yer", "cayir"),
                                "kadro": list(dict.fromkeys(c for s in h.get("sahneler", [])
                                                            for c in s.get("karakterler", []))),
                                "konu": f"{tema} | {h.get('baslik', '')}", "hazir_hikaye": True})
    sorunlar = dogrula(h, k, i.veri)
    if sorunlar:
        raise ValueError("Hazır hikaye kurallara uymuyor: " + "; ".join(sorunlar))
    hikayeyi_kaydet(i, k, h, gemini_denetim(h, k))
    i.durum = "senaryo"
    i.kaydet()
    return i
