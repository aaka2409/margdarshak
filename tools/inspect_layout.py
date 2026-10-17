#!/usr/bin/env python3
"""Design QA: print where elements sit on a page of the laid-out report (points from the page's top-left).

    python tools/inspect_layout.py out/report.html 14 ".area-head, .area-head b, .col > p:first-of-type"
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

html, page_no, selector = Path(sys.argv[1]).resolve(), int(sys.argv[2]), sys.argv[3]
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 794, "height": 1123})
    pg.goto(html.as_uri()); pg.wait_for_function("window.__report !== undefined")
    rows = pg.evaluate("""([n, sel]) => {
        const page = document.querySelectorAll('.page')[n - 1]; const o = page.getBoundingClientRect(); const k = 72 / 96;
        return Array.from(page.querySelectorAll(sel)).map(e => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
            return [e.tagName.toLowerCase() + (e.className && e.className.baseVal === undefined ? '.' + String(e.className).split(' ').join('.') : ''),
                    (r.left - o.left) * k, (r.top - o.top) * k, r.width * k, r.height * k, cs.marginTop, cs.paddingTop, (e.textContent || '').trim().slice(0, 28)]; }); }""",
        [page_no, selector])
    for tag, x, y, w, h, mt, pt, txt in rows:
        print(f"{tag[:34]:34s} x{x:7.1f} y{y:7.1f} w{w:7.1f} h{h:6.1f} bottom{y + h:7.1f}  mt={mt} pt={pt} | {txt}")
    b.close()
