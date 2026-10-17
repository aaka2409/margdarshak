#!/usr/bin/env python3
"""Design QA: compare where each line of text sits in a reference PDF and a generated PDF.

    python tools/textdiff.py reference.pdf out/report.pdf 7 [--all] [--map 7:8]

For every line found in both, prints the offset of the generated line (points):
dx / dy of its start, difference in width and type size.  Lines within half a
point are hidden unless --all is given.
"""
import argparse
import re

import pymupdf


def lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            spans = [s for s in l["spans"] if s["text"].strip()]
            if not spans:
                continue
            text = re.sub(r"\s+", "", "".join(s["text"] for s in spans))
            out.append({"key": text, "x0": l["bbox"][0], "x1": l["bbox"][2], "y": spans[0]["origin"][1],
                        "size": spans[0]["size"], "font": spans[0]["font"].split("+")[-1],
                        "raw": "".join(s["text"] for s in spans)})
    # letter-spaced labels come out as many tiny lines: merge runs on the same baseline
    out.sort(key=lambda d: (round(d["y"], 0), d["x0"]))
    merged = []
    for d in out:
        m = merged[-1] if merged else None
        if m and abs(m["y"] - d["y"]) < 0.6 and abs(m["size"] - d["size"]) < 0.2 and 0 <= d["x0"] - m["x1"] < m["size"] * 1.6:
            m["key"] += d["key"]; m["raw"] += d["raw"]; m["x1"] = d["x1"]
        else:
            merged.append(dict(d))
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reference"); ap.add_argument("generated"); ap.add_argument("pages")
    ap.add_argument("--all", action="store_true"); ap.add_argument("--map", default="")
    ap.add_argument("--tol", type=float, default=0.6)
    a = ap.parse_args()
    ref, gen = pymupdf.open(a.reference), pymupdf.open(a.generated)
    remap = dict((int(x.split(":")[0]), int(x.split(":")[1])) for x in a.map.split(",") if x)
    for p in (int(x) for x in a.pages.split(",")):
        R, G = lines(ref[p - 1]), lines(gen[remap.get(p, p) - 1])
        used = set()
        print(f"\n== page {p}: {len(R)} reference lines, {len(G)} generated")
        missing = 0
        for r in R:
            cands = [i for i, g in enumerate(G) if g["key"] == r["key"] and i not in used]
            if not cands:
                missing += 1
                if missing <= 12:
                    print(f"   not found (wraps differently?): y{r['y']:6.1f} {r['size']:4.1f} | {r['raw'][:60]}")
                continue
            i = min(cands, key=lambda i: abs(G[i]["y"] - r["y"]) + abs(G[i]["x0"] - r["x0"]))
            used.add(i); g = G[i]
            dx, dy, dw, ds = g["x0"] - r["x0"], g["y"] - r["y"], (g["x1"] - g["x0"]) - (r["x1"] - r["x0"]), g["size"] - r["size"]
            if a.all or max(abs(dx), abs(dy), abs(dw), abs(ds)) > a.tol:
                print(f"   dx{dx:+6.1f} dy{dy:+6.1f} dw{dw:+6.1f} ds{ds:+5.1f} | ref x{r['x0']:6.1f} y{r['y']:6.1f} {r['size']:4.1f} {g['font'][-14:]:14s}| {r['raw'][:44]}")
        extra = [g for i, g in enumerate(G) if i not in used]
        print(f"   matched {len(used)}, not found {missing}, extra in generated {len(extra)}")
        for g in extra[:8]:
            print(f"   extra: x{g['x0']:6.1f} y{g['y']:6.1f} {g['size']:4.1f} | {g['raw'][:60]}")


if __name__ == "__main__":
    main()
