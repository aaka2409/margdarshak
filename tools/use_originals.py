#!/usr/bin/env python3
"""Rebuild chapter openers from the ORIGINAL artwork (art_originals/chNN_original.png).

The 4K versions of some openers lost fine detail (arcs, constellations); the originals are the faithful art.  Each original
carries a gold double frame and a baked title: the frame is cropped away, the page-shaped crop is scaled to the A4 page
(1654 x 2339), the title is painted out (the report prints it live) and the picture is cleaned.

    python tools/use_originals.py            # rebuilds the chapters listed in SPEC
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import art_clean                                                    # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PAGE = (1654, 2339)
# crop = (x0, y0, x1, y1) inside the frame, in original pixels; erase = rectangles in PAGE pixels that held the title;
# box = where the live title is printed (page px, x0 y0 x1 y1 - only y0 is used)
SPEC = {
    1: dict(crop=(39, 100, 657, 975), erase=[(250, 0, 1420, 350)], passes=2, box=[555, 100, 1099, 300], amount=0.8),
    4: dict(crop=(39, 100, 657, 975), erase=[(150, 0, 1500, 135), (380, 125, 1300, 372)], passes=2, box=[486, 90, 1168, 300], amount=0.8),
    7: dict(crop=(95, 130, 1953, 2757), erase=[(0, 90, 1654, 532)], vertical=True, box=[453, 169, 1275, 405], amount=0.6),
}


def match_colour(img: Image.Image, ref_path: Path) -> Image.Image:
    """Give the original the colour grading of the book's other openers (mean and spread of L, a, b match the reference)."""
    src = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2LAB).astype(np.float32)
    ref = cv2.cvtColor(np.array(Image.open(ref_path).convert("RGB")), cv2.COLOR_RGB2LAB).astype(np.float32)
    for c in range(3):
        ms, ss = src[..., c].mean(), src[..., c].std() + 1e-6
        mr, sr = ref[..., c].mean(), ref[..., c].std()
        src[..., c] = (src[..., c] - ms) * (sr / ss) + mr
    return Image.fromarray(cv2.cvtColor(np.clip(src, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB))


def main() -> int:
    titles_path = ROOT / "report" / "data" / "chapter_titles.json"
    titles = json.loads(titles_path.read_text(encoding="utf-8"))
    for n, s in SPEC.items():
        src = ROOT / "art_originals" / f"ch{n:02d}_original.png"
        im = Image.open(src).convert("RGB").crop(s["crop"]).resize(PAGE, Image.LANCZOS)
        ref = ROOT / "art_originals" / "color_ref" / f"ch{n:02d}.jpg"
        if ref.exists():
            im = match_colour(im, ref)
        rgb = np.array(im)
        for _ in range(s.get("passes", 1)):
            for (x0, y0, x1, y1) in s["erase"]:
                rgb = (art_clean.fill_vertical if s.get("vertical") else art_clean._fill_rect)(rgb, x0, y0, x1, y1, feather=40)
        out = art_clean.sharpen(Image.fromarray(rgb), amount=s["amount"])
        dest = ROOT / "report" / "static" / "img" / "chapters" / f"ch{n:02d}.jpg"
        out.save(dest, "JPEG", quality=86, optimize=True, progressive=True)
        titles[f"{n:02d}"] = s["box"]
        print(f"ch{n:02d}: {dest.stat().st_size // 1024} KB")
    titles_path.write_text(json.dumps(titles, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
