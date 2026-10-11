#!/usr/bin/env python3
"""Render Instagram slides (1080x1350 PNG) for Fremtiden Digitalt.

Usage: python3 render.py spec.json
spec.json: {"slug": "2026-10-17-5-sekunder", "slides": [
  {"style": "dark"|"light", "label": "TIPS", "num": "1", "title": "...", "sub": "...", "footer": "..."}
]}
Output: posts/<slug>/slide-1.png ...
"""
import json, sys, html, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent
NAVY, SKY, PAPER = "#0D1326", "#4BA8FC", "#FBFBFD"

FONTS = "".join(
    f"@font-face{{font-family:'PJS';font-weight:{w};src:url('{(ROOT/'fonts'/f'plus-jakarta-sans-latin-{w}-normal.woff2').as_uri()}')}}"
    for w in (500, 700, 800)
)


def size(t):
    n = len(t)
    return 128 if n <= 24 else 112 if n <= 40 else 96 if n <= 60 else 80


def slide_html(s):
    dark = s.get("style", "dark") == "dark"
    bg, fg = (NAVY, "#FFFFFF") if dark else (PAPER, NAVY)
    e = lambda k: html.escape(s.get(k, ""))
    num = f'<div class="num">{e("num")}</div>' if s.get("num") else ""
    label = f'<div class="label">{e("label")}</div>' if s.get("label") else ""
    sub = f'<p class="sub">{e("sub")}</p>' if s.get("sub") else ""
    foot = f'<div class="foot">{e("footer")}</div>' if s.get("footer") else "<div></div>"
    return f"""<!doctype html><html lang="nb"><head><meta charset="utf-8"><style>
{FONTS}
*{{box-sizing:border-box}}body{{margin:0}}
.s{{width:1080px;height:1350px;padding:88px;background:{bg};color:{fg};font-family:'PJS',sans-serif;display:flex;flex-direction:column;justify-content:space-between}}
.brand{{display:flex;align-items:center;gap:12px;font-size:30px;font-weight:700;letter-spacing:-.01em}}
.mid{{display:flex;flex-direction:column;gap:28px}}
.label{{font-size:26px;font-weight:700;letter-spacing:.08em;color:{SKY}}}
.num{{font-size:320px;line-height:.9;font-weight:800;letter-spacing:-.04em;color:{SKY}}}
h1{{margin:0;font-size:{size(s.get('title',''))}px;line-height:1.04;font-weight:800;letter-spacing:-.03em}}
.sub{{margin:0;font-size:36px;line-height:1.4;font-weight:500;opacity:.78}}
.foot{{font-size:30px;line-height:1.4;font-weight:500}}
</style></head><body><div class="s">
<div class="brand"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="{SKY}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 15l7-7 7 7"/></svg><span>Fremtiden Digitalt</span></div>
<div class="mid">{label}{num}<h1>{e("title")}</h1>{sub}</div>
{foot}
</div></body></html>"""


def main(path):
    spec = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    out = ROOT / "posts" / spec["slug"]
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for i, s in enumerate(spec["slides"], 1):
            tmp = out / f"_s{i}.html"
            tmp.write_text(slide_html(s), encoding="utf-8")
            pg.goto(tmp.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.screenshot(path=str(out / f"slide-{i}.png"))
            tmp.unlink()
        b.close()
    print("ok", out)


if __name__ == "__main__":
    main(sys.argv[1])
