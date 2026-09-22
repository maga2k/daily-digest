"""Rende un PostPlan in cartella: slide HTML + PNG 1080x1350, caption, fonti, anteprima."""
from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from newsbot.config import ROOT
from newsbot.models import PostPlan, Profile

log = logging.getLogger(__name__)

TEMPLATES = Path(__file__).parent / "templates"
FONTS_DIR = ROOT / "assets" / "fonts"
W, H = 1080, 1350


def fonts_css(fonts_dir: Path = FONTS_DIR) -> str:
    """Genera @font-face per ogni font in assets/fonts (nome famiglia = nome file senza estensione).
    Poi in profiles.yaml -> style: font_serif: '"NomeFile", Georgia, serif'."""
    css = []
    if fonts_dir.exists():
        for f in sorted(fonts_dir.iterdir()):
            if f.suffix.lower() in (".woff2", ".woff", ".ttf", ".otf"):
                css.append(f'@font-face{{font-family:"{f.stem}";src:url("{f.resolve().as_uri()}");font-display:block;}}')
    return "\n".join(css)


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)


def _screenshots(html_files: list[Path], png_files: list[Path]) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("playwright non installato: salto i PNG (pip install playwright && playwright install chromium)")
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": W, "height": H})
            for h, png in zip(html_files, png_files):
                page.goto(h.resolve().as_uri())
                page.wait_for_load_state("load")
                page.evaluate("document.fonts.ready.then(() => true)")
                page.wait_for_timeout(150)
                page.screenshot(path=str(png), clip={"x": 0, "y": 0, "width": W, "height": H})
            browser.close()
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("screenshot fallito (%s). Hai lanciato `playwright install chromium`?", exc)
        return False


def _preview_html(n: int, has_png: bool) -> str:
    cells = []
    for i in range(1, n + 1):
        inner = (f'<img src="slide_{i}.png">' if has_png
                 else f'<iframe src="slide_{i}.html" width="{W}" height="{H}"></iframe>')
        cells.append(f'<div class="c">{inner}</div>')
    return f"""<!doctype html><meta charset="utf-8"><title>Anteprima</title>
<style>body{{margin:0;padding:24px;background:#222;display:flex;flex-wrap:wrap;gap:16px;font-family:sans-serif}}
.c{{width:324px;height:405px;overflow:hidden;position:relative;background:#fff}}
.c img{{width:324px;height:405px}}
.c iframe{{border:0;transform:scale(.3);transform-origin:0 0;position:absolute}}</style>
{''.join(cells)}"""


def render_post(plan: PostPlan, profile: Profile, out_dir: Path, png: bool = True) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    env = _env()
    tpl = env.get_template("slide.html.j2")
    style = {"accent": "#2B4EFF", "accent_soft": "#DDE4FF", **profile.style}
    css_fonts = fonts_css()
    total = len(plan.slides)
    html_files, png_files = [], []
    for idx, slide in enumerate(plan.slides):
        html = tpl.render(slide=slide, idx=idx, total=total, profile=profile, style=style,
                          fonts_css=css_fonts)
        hp = out_dir / f"slide_{idx + 1}.html"
        hp.write_text(html, encoding="utf-8")
        html_files.append(hp)
        png_files.append(out_dir / f"slide_{idx + 1}.png")

    has_png = _screenshots(html_files, png_files) if png else False
    (out_dir / "caption.txt").write_text(plan.caption, encoding="utf-8")
    (out_dir / "fonti.json").write_text(json.dumps(plan.sources, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "plan.json").write_text(json.dumps(dataclasses.asdict(plan), ensure_ascii=False, indent=2, default=str),
                                       encoding="utf-8")
    (out_dir / "preview.html").write_text(_preview_html(total, has_png), encoding="utf-8")
    if plan.warnings:
        (out_dir / "DA_CONTROLLARE.txt").write_text(
            "\n".join(f"- {w}" for w in plan.warnings), encoding="utf-8")
    return out_dir
