"""Kanal kimlikleri: profil fotoğrafı (800x800) ve banner (2560x1440) üretir.
Çalıştırma: python branding/uret.py   (Playwright + Chromium gerekir)
Banner'da yazılar YouTube'un her cihazda görünen güvenli alanında (1546x423, ortada) durur."""
from pathlib import Path

from playwright.sync_api import sync_playwright

CIKTI = Path(__file__).resolve().parent

ORTAK = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter Display','Inter',sans-serif;overflow:hidden}
.tam{position:absolute;inset:0}
"""

KANALLAR = {
    "teknoloji_en": {
        "ad": "Tech in 30",
        "profil": """
<div class="tam" style="background:radial-gradient(circle at 30% 25%,#123a5a 0,#05070d 70%)"></div>
<svg class="tam" viewBox="0 0 800 800">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4be3ff"/><stop offset="1" stop-color="#3b6bff"/></linearGradient></defs>
  <circle cx="400" cy="400" r="270" fill="none" stroke="#1c2a3d" stroke-width="34"/>
  <circle cx="400" cy="400" r="270" fill="none" stroke="url(#g)" stroke-width="34" stroke-linecap="round"
          stroke-dasharray="1272 1696" transform="rotate(-90 400 400)"/>
  <text x="400" y="468" text-anchor="middle" font-size="230" font-weight="900" fill="#fff" letter-spacing="-8">30</text>
  <text x="400" y="545" text-anchor="middle" font-size="44" font-weight="800" fill="#4be3ff" letter-spacing="10">SEC</text>
</svg>""",
        "banner": """
<div class="tam" style="background:linear-gradient(120deg,#05070d 0%,#0b1626 45%,#0d2440 100%)"></div>
<svg class="tam" viewBox="0 0 2560 1440" style="opacity:.55">
  <defs><pattern id="p" width="64" height="64" patternUnits="userSpaceOnUse"><path d="M64 0H0V64" fill="none" stroke="#16324d" stroke-width="2"/></pattern></defs>
  <rect width="2560" height="1440" fill="url(#p)"/>
  <circle cx="2150" cy="300" r="420" fill="#3b6bff" opacity=".18"/><circle cx="420" cy="1150" r="380" fill="#4be3ff" opacity=".12"/>
</svg>
<div class="tam" style="display:flex;align-items:center;justify-content:center;gap:64px">
  <svg width="300" height="300" viewBox="0 0 800 800">
    <defs><linearGradient id="g2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4be3ff"/><stop offset="1" stop-color="#3b6bff"/></linearGradient></defs>
    <circle cx="400" cy="400" r="270" fill="none" stroke="#1c2a3d" stroke-width="40"/>
    <circle cx="400" cy="400" r="270" fill="none" stroke="url(#g2)" stroke-width="40" stroke-linecap="round" stroke-dasharray="1272 1696" transform="rotate(-90 400 400)"/>
    <text x="400" y="480" text-anchor="middle" font-size="240" font-weight="900" fill="#fff" letter-spacing="-8">30</text>
  </svg>
  <div style="color:#fff">
    <div style="font-size:168px;font-weight:900;letter-spacing:-5px;line-height:1">TECH IN <span style="color:#4be3ff">30</span></div>
    <div style="font-size:52px;font-weight:600;color:#a9c4dd;margin-top:22px">AI &amp; tech news, explained in 30 seconds</div>
    <div style="font-size:40px;font-weight:800;color:#4be3ff;margin-top:18px;letter-spacing:6px">NEW SHORT EVERY DAY</div>
  </div>
</div>""",
    },
    "finans_tr": {
        "ad": "Cebine Bilgi",
        "profil": """
<div class="tam" style="background:radial-gradient(circle at 35% 25%,#1f6b4f 0,#0a2a20 70%)"></div>
<svg class="tam" viewBox="0 0 800 800">
  <defs><linearGradient id="au" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe08a"/><stop offset="1" stop-color="#e0a526"/></linearGradient></defs>
  <circle cx="400" cy="400" r="250" fill="url(#au)"/>
  <circle cx="400" cy="400" r="212" fill="none" stroke="#b07d10" stroke-width="10" stroke-dasharray="6 18"/>
  <path d="M250 470 L340 390 L410 440 L540 300" fill="none" stroke="#0a2a20" stroke-width="40" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M480 290 L548 290 L548 358" fill="none" stroke="#0a2a20" stroke-width="40" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
        "banner": """
<div class="tam" style="background:linear-gradient(115deg,#0a2a20 0%,#0f3d2e 50%,#14533e 100%)"></div>
<svg class="tam" viewBox="0 0 2560 1440" style="opacity:.5">
  <path d="M0 1200 L500 1050 L900 1120 L1400 860 L1850 930 L2560 560" fill="none" stroke="#2f8f68" stroke-width="10"/>
  <path d="M0 1300 L600 1180 L1100 1230 L1600 1010 L2100 1060 L2560 820" fill="none" stroke="#1f6b4f" stroke-width="8"/>
  <circle cx="2250" cy="260" r="300" fill="#f3c34f" opacity=".12"/>
</svg>
<div class="tam" style="display:flex;align-items:center;justify-content:center;gap:64px">
  <svg width="290" height="290" viewBox="0 0 800 800">
    <defs><linearGradient id="au2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe08a"/><stop offset="1" stop-color="#e0a526"/></linearGradient></defs>
    <circle cx="400" cy="400" r="300" fill="url(#au2)"/>
    <path d="M230 480 L335 385 L415 445 L565 285" fill="none" stroke="#0a2a20" stroke-width="46" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M495 275 L575 275 L575 355" fill="none" stroke="#0a2a20" stroke-width="46" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>
  <div style="color:#fff">
    <div style="font-size:164px;font-weight:900;letter-spacing:-4px;line-height:1">Cebine <span style="color:#f3c34f">Bilgi</span></div>
    <div style="font-size:52px;font-weight:600;color:#bfe3d2;margin-top:22px">Paranı akıllı yönet, 1 dakikada öğren</div>
    <div style="font-size:40px;font-weight:800;color:#f3c34f;margin-top:18px;letter-spacing:5px">HER GÜN YENİ VİDEO</div>
  </div>
</div>""",
    },
    "gta_en": {
        "ad": "Open World Insider",
        "profil": """
<div class="tam" style="background:linear-gradient(180deg,#1a0633 0%,#3b0b55 55%,#ff4f7b 100%)"></div>
<svg class="tam" viewBox="0 0 800 800">
  <defs><linearGradient id="sun" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd25e"/><stop offset="1" stop-color="#ff3d81"/></linearGradient>
  <clipPath id="c"><circle cx="400" cy="350" r="220"/></clipPath></defs>
  <g clip-path="url(#c)"><rect x="150" y="120" width="500" height="460" fill="url(#sun)"/>
  <rect x="150" y="410" width="500" height="18" fill="#3b0b55"/><rect x="150" y="460" width="500" height="22" fill="#3b0b55"/><rect x="150" y="515" width="500" height="28" fill="#3b0b55"/></g>
  <text x="400" y="680" text-anchor="middle" font-size="116" font-weight="900" fill="#fff" letter-spacing="6">OWI</text>
</svg>""",
        "banner": """
<div class="tam" style="background:linear-gradient(180deg,#12042a 0%,#2a0846 45%,#7a1a6b 75%,#ff5f6d 100%)"></div>
<svg class="tam" viewBox="0 0 2560 1440">
  <defs><linearGradient id="sun2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd25e"/><stop offset="1" stop-color="#ff3d81"/></linearGradient>
  <clipPath id="c2"><circle cx="1280" cy="1330" r="420"/></clipPath></defs>
  <g clip-path="url(#c2)" opacity=".6"><rect x="700" y="900" width="1200" height="300" fill="url(#sun2)"/>
  <rect x="700" y="1080" width="1200" height="18" fill="#7a1a6b"/><rect x="700" y="1130" width="1200" height="24" fill="#7a1a6b"/><rect x="700" y="1175" width="1200" height="25" fill="#7a1a6b"/></g>
  <g stroke="#ff7ad9" stroke-width="3" opacity=".35">
    <line x1="0" y1="1200" x2="2560" y2="1200"/><line x1="0" y1="1260" x2="2560" y2="1260"/><line x1="0" y1="1340" x2="2560" y2="1340"/><line x1="0" y1="1440" x2="2560" y2="1440"/>
    <line x1="1280" y1="1200" x2="1280" y2="1440"/><line x1="1280" y1="1200" x2="700" y2="1440"/><line x1="1280" y1="1200" x2="1860" y2="1440"/>
    <line x1="1280" y1="1200" x2="200" y2="1440"/><line x1="1280" y1="1200" x2="2360" y2="1440"/>
  </g>
</svg>
<div class="tam" style="display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:#fff">
  <div style="font-size:150px;font-weight:900;letter-spacing:-3px;line-height:1;text-shadow:0 0 40px rgba(255,61,129,.6)">OPEN WORLD <span style="color:#ffd25e">INSIDER</span></div>
  <div style="font-size:52px;font-weight:600;color:#f6cde6;margin-top:24px">Open-world game news, secrets &amp; tips in 60 seconds</div>
  <div style="font-size:40px;font-weight:800;color:#ffd25e;margin-top:18px;letter-spacing:6px">DAILY SHORTS</div>
</div>""",
    },
}


def sayfa(govde: str, g: int, y: int) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{ORTAK} body{{width:{g}px;height:{y}px;position:relative}}</style></head><body>{govde}</body></html>"


def main() -> None:
    with sync_playwright() as p:
        tarayici = p.chromium.launch()
        for kid, k in KANALLAR.items():
            for tur, (g, y) in (("profil", (800, 800)), ("banner", (2560, 1440))):
                s = tarayici.new_page(viewport={"width": g, "height": y})
                s.set_content(sayfa(k[tur], g, y))
                s.wait_for_timeout(200)
                hedef = CIKTI / kid / f"{tur}.png"
                hedef.parent.mkdir(exist_ok=True)
                s.screenshot(path=str(hedef))
                s.close()
                print("yazıldı:", hedef)
        tarayici.close()


if __name__ == "__main__":
    main()
