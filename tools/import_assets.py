#!/usr/bin/env python3
"""Import the new artwork into report/static (run again whenever the artwork changes, e.g. the 2027 covers).

    python tools/import_assets.py \
        --front-cover  art/cover_front.jpg            # photo cover (the name / DOB placeholder is masked by the template)
        --page-bg      art/page_bg.jpg                # full-page night-sky background for text pages
        --chapters     art/chapters                   # 10 painted chapter openers, sorted 01..10 (png / jpg)
        --gems         art/gemstones                  # blue_sapphire, cats_eye, diamond, emerald, hessonite, pearl, red_coral, ruby, yellow_sapphire (png)
        --rudraksha    art/rudraksha                  # 01_mukhi.png ... 15_mukhi.png
        --zodiac       art/zodiac                     # 01_Aries.svg ... 12_Pisces.svg  (white glyphs)

Chapter openers: the baked-in title (and its year) is painted out and the report prints the title itself (live text from the
content pack, so the year is always right).  Pass --keep-titles if the pictures carry no title or you want them as they are.
The cover: the baked "FOR / NAME / date" placeholder is painted out and the report prints the real name and date.
Pass --keep-cover-text to skip that.

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

import json

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import art_clean                                         # noqa: E402

STATIC = Path(__file__).resolve().parent.parent / "report" / "static"
PAGE = (1654, 2339)                                   # A4 at 200 dpi
SIGNS = ["aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra", "scorpio", "sagittarius", "capricorn",
         "aquarius", "pisces"]
# per chapter picture (1-10): flaws painted out.  "blur" = smeared patch, "object" = element removed from the sky.
FIXES = {
    7: [("blur", (640, 1030, 920, 1180), {"feather": 50, "sparkle": 150}),
        ("blur", (0, 1480, 470, 1800), {"feather": 90, "glow": (185, 1655, 60)})],
    8: [("object", (0, 220, 520, 600), {})],           # the ringed planet
}
# widen the paint-out where the detector stops short of a wide title (extra px left, right)
TITLE_EXTRA = {7: (200, 60)}
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


def _page_jpg(src: Path, dest: Path, prep=None) -> None:
    im = art_clean.fit_to_page(Image.open(src), PAGE)
    if prep:
        im = prep(im)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=86, optimize=True, progressive=True)
    print(f"  {dest.relative_to(STATIC)}  {dest.stat().st_size // 1024} KB")


def _png(src: Path, dest: Path, longest: int, clean=False) -> None:
    im = Image.open(src).convert("RGBA")
    if clean:
        im = art_clean.clean_gem(im)
    if max(im.size) > longest:
        im.thumbnail((longest, longest), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "PNG", optimize=True)
    print(f"  {dest.relative_to(STATIC)}  {im.size[0]}x{im.size[1]}  {dest.stat().st_size // 1024} KB")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("front-cover", "page-bg", "chapters", "gems", "rudraksha", "zodiac"):
        ap.add_argument(f"--{name}")
    ap.add_argument("--keep-titles", action="store_true")
    ap.add_argument("--keep-cover-text", action="store_true")
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="margdarshak_art_"))
    try:
        if a.front_cover:
            print("front cover")
            _page_jpg(Path(a.front_cover), STATIC / "img" / "cover_front.jpg",
                      prep=None if a.keep_cover_text else art_clean.erase_cover_placeholder)
        if a.page_bg:
            print("page background"); _page_jpg(Path(a.page_bg), STATIC / "img" / "bg_page.jpg")
        if a.chapters:
            print("chapter openers")
            imgs = _files(_folder(a.chapters, tmp), ".png", ".jpg", ".jpeg")
            if len(imgs) != 10:
                sys.exit(f"expected 10 chapter images, found {len(imgs)}")
            boxes = {}

            def make(i):
                def prep(im):
                    for kind, rect, kw in FIXES.get(i, []):          # retouching of known flaws in the supplied pictures
                        im = (art_clean.fix_blur_patch if kind == "blur" else art_clean.remove_bright_object)(im, rect, **kw)
                    if not a.keep_titles:
                        im, box = art_clean.erase_title(im, extra=TITLE_EXTRA.get(i, (0, 0)))
                        boxes[i] = [int(v) for v in box] if box else None
                    return art_clean.sharpen(im)
                return prep
            for i, f in enumerate(imgs, 1):
                _page_jpg(f, STATIC / "img" / "chapters" / f"ch{i:02d}.jpg", prep=make(i))
            if not a.keep_titles:
                # where each picture had its title (px on the 1654 x 2339 page): the template prints the live title there
                dest = STATIC.parent / "data" / "chapter_titles.json"
                dest.write_text(json.dumps({f"{k:02d}": v for k, v in boxes.items()}, indent=1), encoding="utf-8")
                print(f"  {dest.relative_to(STATIC.parent)}")
        if a.gems:
            print("gemstones")
            for f in _files(_folder(a.gems, tmp), ".png"):
                key = GEMS.get(f.stem.lower())
                if key:
                    _png(f, STATIC / "img" / "gems" / f"{key}.png", 640, clean=True)
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
