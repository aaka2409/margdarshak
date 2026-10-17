#!/usr/bin/env python3
"""Design QA: put pages of a reference PDF and a generated PDF side by side.

    python tools/compare.py reference.pdf out/report.pdf 1,2,7 --out out/compare [--dpi 72]

Writes one PNG per page: reference on the left, generated on the right.
"""
import argparse
import os

import pymupdf
from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reference"); ap.add_argument("generated"); ap.add_argument("pages")
    ap.add_argument("--out", default="out/compare"); ap.add_argument("--dpi", type=int, default=72)
    ap.add_argument("--map", default="", help="generated page numbers if they differ, e.g. 7:8,9:10")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ref, gen = pymupdf.open(a.reference), pymupdf.open(a.generated)
    remap = dict((int(x.split(":")[0]), int(x.split(":")[1])) for x in a.map.split(",") if x)
    for p in (int(x) for x in a.pages.split(",")):
        g = remap.get(p, p)
        ims = []
        for doc, n in ((ref, p), (gen, g)):
            pix = doc[n - 1].get_pixmap(dpi=a.dpi)
            ims.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        w, h = ims[0].size
        sheet = Image.new("RGB", (w * 2 + 6, h), "#b00")
        sheet.paste(ims[0], (0, 0)); sheet.paste(ims[1].resize((w, h)), (w + 6, 0))
        sheet.save(f"{a.out}/p{p:03d}.png")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
