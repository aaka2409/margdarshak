#!/usr/bin/env python3
"""Cut fixed-weight font files from the variable originals.

Chromium embeds variable fonts in PDFs as Type 3 (drawn shapes).  Fixed
instances are embedded as real TrueType fonts instead: smaller files and
sharper text in every PDF viewer.  The cut files are already in
report/static/fonts, so you only need this when changing fonts:

    npm install @fontsource-variable/cormorant-garamond @fontsource-variable/dm-sans \
                @fontsource-variable/noto-serif-devanagari
    python tools/build_fonts.py ./node_modules

All three families are under the SIL Open Font License.
DM Sans is cut from the weight-only file (default optical size), which is
what the approved design was set in.
"""
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

OUT = Path(__file__).resolve().parent.parent / "report" / "static" / "fonts"
JOBS = [
    # package dir, source file pattern, weights, output stem, subsets, styles
    ("@fontsource-variable/cormorant-garamond/files", "cormorant-garamond-{sub}-wght-{style}.woff2",
     [300, 400, 500, 600], "cormorant-{sub}-{style}-{w}", ["latin", "latin-ext"], ["normal", "italic"]),
    ("@fontsource-variable/dm-sans/files", "dm-sans-{sub}-wght-{style}.woff2",
     [400, 500, 600], "dmsans-{sub}-{style}-{w}", ["latin", "latin-ext"], ["normal"]),
    ("@fontsource-variable/noto-serif-devanagari/files", "noto-serif-devanagari-{sub}-wght-{style}.woff2",
     [500, 600], "notoserifdeva-{sub}-{style}-{w}", ["devanagari"], ["normal"]),
]


def main():
    root = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.woff2"):
        old.unlink()
    for pkg, pattern, weights, stem, subsets, styles in JOBS:
        for sub in subsets:
            for style in styles:
                src = root / pkg / pattern.format(sub=sub, style=style)
                for w in weights:
                    font = TTFont(src)
                    inst = instancer.instantiateVariableFont(font, {"wght": w}, inplace=False)
                    inst.flavor = "woff2"
                    out = OUT / (stem.format(sub=sub, style=style, w=w) + ".woff2")
                    inst.save(out)
                    print(out.name, out.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
