"""Margdarshak yearly prediction report engine."""
from __future__ import annotations

import os
from pathlib import Path

from .content import ContentError, ContentPack
from .model import Person, build
from .providers import ChartError, chart_from_request
from .render import RenderError, html_to_pdf, render_html

ROOT = Path(__file__).resolve().parent.parent
CONTENT_ROOT = Path(os.environ.get("CONTENT_ROOT") or ROOT / "content")   # CONTENT_ROOT=content_sample to test

__all__ = ["generate", "Person", "ContentPack", "ContentError", "ChartError", "RenderError", "CONTENT_ROOT"]


def generate(request: dict, year: int, output: Path | str, *, chart_provider=None,
             content_root: Path | str = CONTENT_ROOT, keep_html: Path | str | None = None,
             strict: bool = True, allow_sample: bool = False) -> dict:
    """Build one customer's report.

    request  the order data: name, dob (DD/MM/YYYY), tob, pob, sex, lat, lon, tz, email, user_id,
             and optionally a ready `chart`.
    year     which content pack to print (2026, 2027, ...).
    Returns  {"pages", "moon_sign", "ascendant", "mulank", "output"}.
    Raises   ValueError (bad order data), ChartError, ContentError, RenderError.
    """
    person = Person.from_request(request)
    chart = chart_from_request(request)
    if chart is None:
        if chart_provider is None:
            raise ChartError("no chart supplied and no chart provider configured")
        chart = chart_provider.get_chart(person)
    pack = ContentPack(content_root, year)
    if pack.meta.get("sample") and not allow_sample:
        raise ContentError(f"content/{year} is still the SAMPLE text (2026 wording). Replace it with the real {year} text and remove \"sample\" from year.json, or set ALLOW_SAMPLE_CONTENT=1 to test")
    ctx = build(person, chart, pack)
    result = html_to_pdf(render_html(ctx), output, keep_html=keep_html, strict=strict,
                         cover=Path(output).with_suffix(".jpg"))
    return {**result, "moon_sign": ctx["moon"], "ascendant": ctx["asc"], "mulank": ctx["mulank"], "output": str(output), "sample": bool(pack.meta.get("sample"))}
