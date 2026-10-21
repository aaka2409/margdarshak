"""HTML -> PDF.  One browser, one document, one PDF.

The template is rendered to a single HTML file, opened in headless Chromium,
paginated by static/js/paginate.js, checked, and printed.  If the layout
script reports any problem (text that does not fit, a font or image that
failed to load) no PDF is produced: a report is either complete or it is an
error, never a silently broken file.
"""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup, escape

HERE = Path(__file__).parent
STATIC = HERE / "static"
_DEVANAGARI = re.compile(r"([ऀ-ॿ][ऀ-ॿ\s‌‍।॥]*[ऀ-ॿ]|[ऀ-ॿ])")


class RenderError(Exception):
    """The report could not be laid out completely."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


def _rich(text, dropcap: bool = False) -> Markup:
    """Escape body text, keeping only <b>/<i>; optionally raise the first letter as a drop cap."""
    s = str(escape(text))
    s = re.sub(r"&lt;(/?)(b|i)&gt;", r"<\1\2>", s)
    if dropcap:
        m = re.match(r"^((?:<[bi]>)*)([“\"‘']?[A-Za-z0-9])", s)
        if m:
            s = f'{m.group(1)}<span class="dc">{m.group(2)}</span>{s[m.end():]}'
    return Markup(s)


def _mantra(text) -> Markup:
    """Set Devanagari runs (beej mantras) in the Devanagari face and gold."""
    s = str(escape(text))
    return Markup(_DEVANAGARI.sub(r'<span class="deva">\1</span>', s))


def environment() -> Environment:
    env = Environment(loader=FileSystemLoader(str(HERE / "templates")), undefined=StrictUndefined,
                      autoescape=select_autoescape(["html", "j2"], default=True), trim_blocks=True, lstrip_blocks=True)
    env.filters["rich"] = _rich
    env.filters["mantra"] = _mantra
    return env


def render_html(ctx: dict, static_url: str | None = None) -> str:
    return environment().get_template("report.html.j2").render(static=static_url or STATIC.as_uri(), **ctx)


def _shrink(pdf: Path) -> None:
    """Lossless clean-up (shared objects, deflate): ~20% smaller, pixel-identical.  Skipped if PyMuPDF is missing."""
    try:
        import pymupdf
    except ImportError:
        return
    small = pdf.with_suffix(".small.pdf")
    try:
        doc = pymupdf.open(str(pdf))
        doc.save(str(small), garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, use_objstms=1)
        doc.close()
        if 0 < small.stat().st_size < pdf.stat().st_size:
            small.replace(pdf)
    except Exception:                      # noqa: BLE001 - the unshrunk PDF is still perfectly good
        pass
    finally:
        small.unlink(missing_ok=True)


def html_to_pdf(html: str, output: Path | str, keep_html: Path | str | None = None, timeout_ms: int = 180_000,
                strict: bool = True, cover: Path | str | None = None) -> dict:
    """Print `html` to `output`.  Returns {"pages": n}.  Raises RenderError on any layout problem."""
    from playwright.sync_api import sync_playwright

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="margdarshak_"))
    try:
        src = workdir / "report.html"
        src.write_text(html, encoding="utf-8")
        if keep_html:
            Path(keep_html).write_text(html, encoding="utf-8")
        tmp_pdf = workdir / "report.pdf"
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--font-render-hinting=none"])
            try:
                page = browser.new_page(viewport={"width": 794, "height": 1123})
                page.set_default_timeout(timeout_ms)
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(f"script error: {e}"))
                page.on("requestfailed", lambda r: errors.append(f"could not load {r.url.rsplit('/', 1)[-1]}"))
                page.goto(src.as_uri(), wait_until="load")
                page.wait_for_function("window.__report !== undefined", timeout=timeout_ms)
                result = page.evaluate("window.__report")
                problems = list(dict.fromkeys(errors + list(result.get("problems", []))))
                if problems and strict:
                    raise RenderError(problems)
                if cover:                                   # page 1 as a picture, for the e-mail
                    try:
                        page.locator(".page").first.screenshot(path=str(cover), type="jpeg", quality=86)
                    except Exception:                       # noqa: BLE001 - the e-mail simply goes without the picture
                        Path(cover).unlink(missing_ok=True)
                page.emulate_media(media="print")
                page.pdf(path=str(tmp_pdf), width="210mm", height="297mm", print_background=True,
                         margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}, prefer_css_page_size=True)
            finally:
                browser.close()
        _shrink(tmp_pdf)
        shutil.move(str(tmp_pdf), str(output))
        return {"pages": int(result["pages"]), "problems": problems}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
