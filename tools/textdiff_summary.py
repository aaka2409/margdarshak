#!/usr/bin/env python3
"""Design QA: one line per page saying how far the generated text is from the reference.

    python tools/textdiff_summary.py reference.pdf out/report.pdf [first-last]
"""
import sys
from collections import Counter

import pymupdf

from textdiff import lines

ref, gen = pymupdf.open(sys.argv[1]), pymupdf.open(sys.argv[2])
a, b = (int(x) for x in sys.argv[3].split("-")) if len(sys.argv) > 3 else (1, min(len(ref), len(gen)))
bad_pages = []
for p in range(a, b + 1):
    R, G = lines(ref[p - 1]), lines(gen[p - 1])
    used, off, miss = set(), Counter(), 0
    worst = 0.0
    for r in R:
        c = [i for i, g in enumerate(G) if g["key"] == r["key"] and i not in used]
        if not c:
            miss += 1; continue
        i = min(c, key=lambda i: abs(G[i]["y"] - r["y"]) + abs(G[i]["x0"] - r["x0"])); used.add(i); g = G[i]
        d = max(abs(g["x0"] - r["x0"]), abs(g["y"] - r["y"]), abs((g["x1"] - g["x0"]) - (r["x1"] - r["x0"])))
        worst = max(worst, d)
        off["<=1" if d <= 1.01 else ("<=3" if d <= 3 else ">3")] += 1
    flag = "" if (off[">3"] == 0 and miss <= 3) else "  <<<"
    if flag: bad_pages.append(p)
    print(f"p{p:3d}: lines {len(R):3d} | within 1pt {off['<=1']:3d} | 1-3pt {off['<=3']:3d} | >3pt {off['>3']:3d} | unmatched {miss:3d} | worst {worst:5.1f}{flag}")
print("pages needing attention:", bad_pages)
