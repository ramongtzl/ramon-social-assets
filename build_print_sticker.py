# -*- coding: utf-8 -*-
"""Build the round 3" "Hablo español" sticker (black, WhatsApp QR) for print.

Same look as the black business card: Fraunces headline in orange, white
body text, blue/orange chart logo. The QR opens WhatsApp with a pre-filled
message so every chat says where the sticker was seen.

Output (print/sticker-hablo-espanol/):
    sticker-<slug>.pdf          print file, 3.25" square = 3" cut + 0.125" bleed
    sticker-<slug>.png          same at 300 dpi
    sticker-<slug>-proof.png    with cut line (dashed) and safe area (dotted)

Run:  python build_print_sticker.py                       generic sticker
      python build_print_sticker.py --lugar "Taqueria X"  one QR per restaurant

Needs: pip install qrcode   and Node Playwright (renders the PDF/PNG).
"""
import os, sys, base64, subprocess, urllib.parse
import qrcode
from qrcode.constants import ERROR_CORRECT_Q

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "print", "sticker-hablo-espanol")
FONTS = os.path.join(HERE, "print", "fonts")

WHATSAPP = "17788630019"
BLACK, ORANGE, BLUE, WHITE, MUTED = "#0d0d0d", "#f39a3d", "#3e9ad6", "#ffffff", "#9aa6b8"

# Units are 1/100 inch: 325 = 3" cut + 1/8" bleed per side.
SIZE, C = 325, 162.5
CUT_R, SAFE_R = 150, 137.5


def wa_link(lugar=None):
    msg = "Hola Ramon, vi tu sticker" + (f" en {lugar}" if lugar else "")
    return f"https://wa.me/{WHATSAPP}?text={urllib.parse.quote(msg)}"


def qr_svg(data, x, y, size):
    """QR as one SVG path inside a white rounded box (box includes quiet zone)."""
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_Q, border=0)
    qr.add_data(data)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    quiet = 2
    mod = size / (n + 2 * quiet)
    ox, oy = x + quiet * mod, y + quiet * mod
    d = "".join(f"M{ox + c * mod:.3f} {oy + r * mod:.3f}h{mod:.3f}v{mod:.3f}h-{mod:.3f}z"
                for r, row in enumerate(m) for c, v in enumerate(row) if v)
    return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="7" fill="{WHITE}"/>'
            f'<path d="{d}" fill="{BLACK}" shape-rendering="crispEdges"/>')


def logo_svg(cx, top, w):
    """Rising chart line with three peak dots (last one orange) over a base line."""
    s = w / 36
    pts = [(0, 30), (9, 21), (12, 9), (17.5, 19), (22, 7), (27.5, 15), (31, 3), (36, 11)]
    p = " ".join(f"{cx + (px - 18) * s:.2f},{top + py * s:.2f}" for px, py in pts)
    def dot(px, py, col):
        return f'<circle cx="{cx + (px - 18) * s:.2f}" cy="{top + py * s:.2f}" r="{2.6 * s:.2f}" fill="{col}"/>'
    return (f'<polyline points="{p}" fill="none" stroke="{BLUE}" stroke-width="{2.4 * s:.2f}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<line x1="{cx - 12 * s:.2f}" y1="{top + 36 * s:.2f}" x2="{cx + 18 * s:.2f}" y2="{top + 36 * s:.2f}" '
            f'stroke="{BLUE}" stroke-width="{2.2 * s:.2f}" stroke-linecap="round"/>'
            + dot(12, 9, BLUE) + dot(22, 7, BLUE) + dot(31, 3, ORANGE))


def text(y, s, size, fill, family="sans", weight=400, spacing=0):
    fam = "Fraunces" if family == "serif" else "'Source Sans 3'"
    return (f'<text x="{C}" y="{y}" text-anchor="middle" font-family="{fam}" font-size="{size}" '
            f'font-weight="{weight}" letter-spacing="{spacing}" fill="{fill}">{s}</text>')


def sticker_svg(link, proof=False):
    qr_size = 100  # 1" box; the code itself is ~0.9" (2.3 cm)
    parts = [
        f'<circle cx="{C}" cy="{C}" r="{C}" fill="{BLACK}"/>',
        logo_svg(C, 34, 34),
        text(90, "Hablo español", 27, ORANGE, "serif", 700),
        text(107, "¿Comprar o vender casa?", 11.5, WHITE),
        qr_svg(link, C - qr_size / 2, 115, qr_size),
        text(231, "ESCANÉAME · WHATSAPP", 10, ORANGE, weight=700, spacing=1.2),
        text(252, f'Ramon Gutierrez <tspan fill="{ORANGE}" font-size="9.7" font-weight="600">MBA</tspan>',
             15.5, WHITE, weight=700),
        text(267, "REALTOR® · eXp Realty", 10.5, MUTED),
        text(283, "ramonhouses.com/es", 11, ORANGE, weight=600),
    ]
    if proof:
        parts += [
            f'<circle cx="{C}" cy="{C}" r="{CUT_R}" fill="none" stroke="#ff2d55" stroke-width="0.8" stroke-dasharray="4 3"/>',
            f'<circle cx="{C}" cy="{C}" r="{SAFE_R}" fill="none" stroke="#36d399" stroke-width="0.6" stroke-dasharray="1 2"/>',
        ]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
            f'width="{SIZE / 100}in" height="{SIZE / 100}in">{"".join(parts)}</svg>')


def page(svg, proof=False):
    def face(fam, file, weight):
        b64 = base64.b64encode(open(os.path.join(FONTS, file), "rb").read()).decode()
        return f"@font-face{{font-family:'{fam}';font-weight:{weight};src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
    bg = "#ffffff" if proof else BLACK
    return ("<!doctype html><html><head><meta charset='utf-8'><style>"
            + face("Fraunces", "fraunces-700.woff2", 700) + face("Source Sans 3", "sourcesans3.woff2", "200 900")
            + f"@page{{size:3.25in 3.25in;margin:0}}html,body{{margin:0;padding:0;background:{bg}}}"
            + "svg{display:block}</style></head><body>" + svg + "</body></html>")


RENDER_JS = r"""
const { chromium } = require('playwright');
(async () => {
  const [html, proof, pdf, png, proofPng] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 312, height: 312 }, deviceScaleFactor: 300 / 96 });
  for (const [src, out, isPdf] of [[html, pdf, true], [html, png, false], [proof, proofPng, false]]) {
    await p.goto('file://' + src);
    await p.evaluate(() => document.fonts.ready);
    if (isPdf) await p.pdf({ path: out, width: '3.25in', height: '3.25in', printBackground: true, pageRanges: '1' });
    else await p.screenshot({ path: out, clip: { x: 0, y: 0, width: 312, height: 312 }, omitBackground: true });
  }
  await b.close();
})();
"""


def slugify(s):
    import unicodedata, re
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def main():
    lugar = sys.argv[sys.argv.index("--lugar") + 1] if "--lugar" in sys.argv else None
    slug = slugify(lugar) if lugar else "general"
    link = wa_link(lugar)
    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(OUT, ".build")
    os.makedirs(tmp, exist_ok=True)
    html, proof = os.path.join(tmp, "sticker.html"), os.path.join(tmp, "proof.html")
    open(html, "w", encoding="utf-8").write(page(sticker_svg(link)))
    open(proof, "w", encoding="utf-8").write(page(sticker_svg(link, proof=True), proof=True))
    js = os.path.join(tmp, "render.js")
    open(js, "w").write(RENDER_JS)
    base = os.path.join(OUT, f"sticker-{slug}")
    env = dict(os.environ)
    env["NODE_PATH"] = os.pathsep.join(filter(None, [env.get("NODE_PATH"), subprocess.run(
        ["npm", "root", "-g"], capture_output=True, text=True, shell=os.name == "nt").stdout.strip()]))
    subprocess.run(["node", js, html, proof, base + ".pdf", base + ".png", base + "-proof.png"],
                   check=True, env=env)
    print(f"{base}.pdf / .png / -proof.png\nQR -> {link}")


if __name__ == "__main__":
    main()
