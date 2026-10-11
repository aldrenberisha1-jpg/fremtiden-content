#!/usr/bin/env python3
"""Render an Instagram Reel (1080x1920, 30 fps, H.264 mp4, no audio) from a spec.

Usage: python3 render_reel.py specs/<file>.json
Spec: {"slug": "...", "scenes": [{"style": "dark"|"light", "label": "", "num": "", "title": "", "sub": "", "footer": "", "dur": 2.5}]}
Output: posts/<slug>/reel.mp4

Motion is physical: scenes slide up on a damped spring, text settles with slight overshoot.
Frames are rendered deterministically (setT(t) per frame), so the video never stutters.
"""
import json, sys, html, pathlib, subprocess, tempfile
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent
NAVY, SKY, PAPER = "#0D1326", "#4BA8FC", "#FBFBFD"
FPS = 30
FONTS = "".join(
    f"@font-face{{font-family:'PJS';font-weight:{w};src:url('{(ROOT/'fonts'/f'plus-jakarta-sans-latin-{w}-normal.woff2').as_uri()}')}}"
    for w in (500, 700, 800)
)


def fs(t):
    n = len(t)
    return 124 if n <= 24 else 104 if n <= 42 else 88 if n <= 64 else 76


def scene_html(s, i):
    dark = s.get("style", "dark") == "dark"
    bg, fg = (NAVY, "#FFFFFF") if dark else (PAPER, NAVY)
    e = lambda k: html.escape(s.get(k, ""))
    parts = []
    if s.get("label"):
        parts.append(f'<div class="el label">{e("label")}</div>')
    if s.get("num"):
        parts.append(f'<div class="el num">{e("num")}</div>')
    parts.append(f'<h1 class="el" style="font-size:{fs(s.get("title",""))}px">{e("title")}</h1>')
    if s.get("sub"):
        parts.append(f'<p class="el sub">{e("sub")}</p>')
    foot = f'<div class="el foot">{e("footer")}</div>' if s.get("footer") else ""
    return f"""<section class="sc" data-i="{i}" style="background:{bg};color:{fg}">
<div class="brand"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="{SKY}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 15l7-7 7 7"/></svg><span>Fremtiden Digitalt</span></div>
<div class="mid">{''.join(parts)}</div>{foot}</section>"""


def page(spec):
    scenes = spec["scenes"]
    starts, t = [], 0.0
    for s in scenes:
        starts.append(t)
        t += s.get("dur", 2.5)
    body = "".join(scene_html(s, i) for i, s in enumerate(scenes))
    return f"""<!doctype html><html lang="nb"><head><meta charset="utf-8"><style>
{FONTS}
*{{box-sizing:border-box}}body{{margin:0;overflow:hidden;background:{NAVY}}}
.sc{{position:absolute;left:0;top:0;width:1080px;height:1920px;padding:240px 88px 340px;font-family:'PJS',sans-serif;display:flex;flex-direction:column;justify-content:space-between;will-change:transform}}
.brand{{display:flex;align-items:center;gap:12px;font-size:30px;font-weight:700;letter-spacing:-.01em}}
.mid{{display:flex;flex-direction:column;gap:30px}}
.label{{font-size:28px;font-weight:700;letter-spacing:.08em;color:{SKY}}}
.num{{font-size:340px;line-height:.9;font-weight:800;letter-spacing:-.04em;color:{SKY}}}
h1{{margin:0;line-height:1.04;font-weight:800;letter-spacing:-.03em}}
.sub{{margin:0;font-size:38px;line-height:1.4;font-weight:500;opacity:.78}}
.foot{{font-size:32px;line-height:1.4;font-weight:500}}
</style></head><body>{body}<script>
const starts={json.dumps(starts)};
// damped spring step response: zeta<1 gives a small, natural overshoot
function spring(tau){{ if(tau<=0) return 0; const z=.62,w=15,wd=w*Math.sqrt(1-z*z);
  return 1-Math.exp(-z*w*tau)*(Math.cos(wd*tau)+(z*w/wd)*Math.sin(wd*tau)); }}
const secs=[...document.querySelectorAll('.sc')];
function setT(t){{ secs.forEach((sc,i)=>{{
  const dt=t-starts[i];
  sc.style.zIndex=i;
  sc.style.visibility = dt<0 ? 'hidden':'visible';
  sc.style.transform = i===0 ? 'none' : `translateY(${{(1-spring(dt/0.9))*1920}}px)`;
  [...sc.querySelectorAll('.el')].forEach((el,j)=>{{
    const d=dt-(i===0?0.15:0.30)-j*0.11;
    el.style.opacity=Math.max(0,Math.min(1,d/0.22));
    el.style.transform=`translateY(${{(1-spring(d/0.9))*70}}px)`;
  }});
}});}}
</script></body></html>""", t


def main(path):
    spec = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    out = ROOT / "posts" / spec["slug"]
    out.mkdir(parents=True, exist_ok=True)
    html_text, total = page(spec)
    total += 0.4  # short hold on the last frame
    n = int(round(total * FPS))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / "reel.html").write_text(html_text, encoding="utf-8")
        # fonts are loaded via file:// URLs, so the page must be a file:// page too
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1080, "height": 1920})
            pg.goto((tmp / "reel.html").as_uri())
            pg.evaluate("document.fonts.ready")
            for f in range(n):
                pg.evaluate(f"setT({f / FPS})")
                pg.screenshot(path=str(tmp / f"f{f:04d}.png"))
            b.close()
        mp4 = out / "reel.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(tmp / "f%04d.png"),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(mp4)],
            check=True,
        )
        # still frames for quick visual checks
        for label, t in (("mid", total * 0.45), ("end", total - 0.2)):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1",
                            str(tmp / f"check-{label}.png")], check=True)
            (out / f"_check-{label}.png").write_bytes((tmp / f"check-{label}.png").read_bytes())
    print("ok", mp4, f"{total:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1])
