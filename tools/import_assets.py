#!/usr/bin/env python3
"""Import the new artwork into report/static (run again whenever the artwork changes, e.g. the 2027 covers).

    python tools/import_assets.py \
        --front-cover  art/cover_front.jpg            # photo cover (the name / DOB placeholder is masked by the template)
        --page-bg      art/page_bg.jpg                # full-page night-sky background for text pages
        --chapters     art/chapters                   # 10 painted chapter openers, sorted 01..10 (png / jpg)
        --gems         art/gemstones                  # blue_sapphire, cats_eye, diamond, emerald, hessonite, pearl, red_coral, ruby, yellow_sapphire (png)
        --rudraksha    art/rudraksha                  # 01_mukhi.png ... 15_mukhi.png
        --zodiac       art/zodiac                     # 01_Aries.svg ... 12_Pisces.svg  (white glyphs)

Every option is optional; only what you pass is replaced.  A folder or a .zip is accepted for the last four.
Page-size images are written at 200 dpi (1654 x 2339 px, JPEG) so the PDF stays e-mailable.
Needs Pillow:  pip install pillow
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

STATIC = Path(__file__).resolve().parent.parent / "report" / "static"
PAGE = (1654, 2339)                                   # A4 at 200 dpi
SIGNS = ["aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra", "scorpio", "sagittarius", "capricorn",
         "aquarius", "pisces"]
GEMS = {"blue_sapphire": "blue_sapphire", "cats_eye": "cats_eye", "diamond": "diamond", "emerald": "emerald",
        "orange_gemstone": "hessonite", "hessonite": "hessonite", "pearl": "pearl", "red_coral": "red_coral",
        "ruby": "ruby", "yellow_sapphire": "yellow_sapphire"}


def _folder(src: str, tmp: Path) -> Path:
    p = Path(src)
    if p.is_file() and p.suffix.lower() == ".zip":
        out = tmp / p.stem
        out.mkdir(parents=True, exist_ok=True)
        zipfile.ZipFile(p).extractall(out)
        return out
    if not p.is_dir():
        sys.exit(f"not a folder or .zip: {src}  (a .rar must be unpacked first)")
    return p


def _files(folder: Path, *exts: str) -> list[Path]:
    return sorted(f for f in folder.rglob("*") if f.is_file() and f.suffix.lower() in exts and not f.name.startswith("."))


def _page_jpg(src: Path, dest: Path) -> None:
    im = Image.open(src).convert("RGB")
    if im.size != PAGE:
        im = im.resize(PAGE, Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=86, optimize=True, progressive=True)
    print(f"  {dest.relative_to(STATIC)}  {dest.stat().st_size // 1024} KB")


def _png(src: Path, dest: Path, longest: int) -> None:
    im = Image.open(src).convert("RGBA")
    if max(im.size) > longest:
        im.thumbnail((longest, longest), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "PNG", optimize=True)
    print(f"  {dest.relative_to(STATIC)}  {im.size[0]}x{im.size[1]}  {dest.stat().st_size // 1024} KB")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("front-cover", "page-bg", "chapters", "gems", "rudraksha", "zodiac"):
        ap.add_argument(f"--{name}")
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="margdarshak_art_"))
    try:
        if a.front_cover:
            print("front cover"); _page_jpg(Path(a.front_cover), STATIC / "img" / "cover_front.jpg")
        if a.page_bg:
            print("page background"); _page_jpg(Path(a.page_bg), STATIC / "img" / "bg_page.jpg")
        if a.chapters:
            print("chapter openers")
            imgs = _files(_folder(a.chapters, tmp), ".png", ".jpg", ".jpeg")
            if len(imgs) != 10:
                sys.exit(f"expected 10 chapter images, found {len(imgs)}")
            for i, f in enumerate(imgs, 1):
                _page_jpg(f, STATIC / "img" / "chapters" / f"ch{i:02d}.jpg")
        if a.gems:
            print("gemstones")
            for f in _files(_folder(a.gems, tmp), ".png"):
                key = GEMS.get(f.stem.lower())
                if key:
                    _png(f, STATIC / "img" / "gems" / f"{key}.png", 640)
                else:
                    print(f"  skipped {f.name} (unknown gemstone name)")
        if a.rudraksha:
            print("rudraksha")
            for f in _files(_folder(a.rudraksha, tmp), ".png"):
                m = re.match(r"(\d+)", f.stem)
                if m:
                    _png(f, STATIC / "img" / "rudraksha" / f"{int(m.group(1))}.png", 560)
        if a.zodiac:
            print("zodiac glyphs")
            for f in _files(_folder(a.zodiac, tmp), ".svg"):
                key = re.sub(r"^\d+_", "", f.stem).lower()
                if key in SIGNS:
                    dest = STATIC / "svg" / "zodiac" / f"{key}_zodiac_symbol.svg"
                    shutil.copyfile(f, dest)
                    print(f"  {dest.relative_to(STATIC)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
