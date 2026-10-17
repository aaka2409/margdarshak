#!/usr/bin/env python3
"""Content-pack tool: start a new year's pack, and check how much of it is written.

    python pack.py new 2027 --from 2026     # create content/2027 with TODO placeholders in the same shape
    python pack.py check 2027               # list everything still missing (exit code 1 if anything is)

A report can only be printed when `check` is clean: every Moon sign, ascendant and Mulank must have
its text.  Nothing is ever copied silently from last year -- only the files named in year.json >
"inherit_files" (the Mulank x Moon-sign overview) are read from the parent pack.
"""
from __future__ import annotations

import argparse
import collections
import copy
import json
import sys
from pathlib import Path

from report import config
from report.astro import SIGNS, house_of, ordinal
from report import CONTENT_ROOT
from report.content import ContentError, ContentPack
from report.model import _pretty_date

TODO = "TODO"
KEEP_STR = {"key", "month", "from", "to", "sign", "colours_label", "day", "name"}   # structural, not prose
KEEP_ANY = {"colours", "beads"}
COPY_VERBATIM = {"elements.json", "gemstones.json"}     # year-independent lookup tables: review, but not rewritten yearly
SKIP = {"year.json", "_review.json"}
EMPTY_LIST_KEYS = {"dates", "scores"}                    # numbers that belong to the new year: must be filled in


def skeleton(node, key=None):
    if isinstance(node, dict):
        if key == "scores":
            return {m: {c: None for c in v} for m, v in node.items()}
        return {k: skeleton(v, k) for k, v in node.items() if k != "hidden"}
    if isinstance(node, list):
        if key in EMPTY_LIST_KEYS:
            return []
        if key in KEEP_ANY:
            return copy.deepcopy(node)
        if node and all(isinstance(x, str) for x in node):
            return [TODO]
        return [skeleton(x, key) for x in node]
    if isinstance(node, str):
        if key in KEEP_STR or (key and key.endswith("_url")):
            return node
        return TODO
    return node


def jupiter_skeleton(source: dict, transits: list[dict]) -> dict:
    out = {}
    for asc in SIGNS:
        periods = []
        for t in transits:
            h = house_of(t["sign"], asc)
            a, b = _pretty_date(t["from"]), _pretty_date(t["to"])
            periods.append({"heading": f"{a} to {b} — Jupiter in {t['sign']} ({ordinal(h)} house)",
                            "from": a, "to": b, "sign": t["sign"], "house": h, "body": [TODO]})
        out[asc] = {"periods": periods, "closing": [TODO]}
    return out


def cmd_new(args) -> int:
    root = Path(args.root)
    dest, src = root / str(args.year), root / str(args.source)
    if not (src / "year.json").exists():
        print(f"source pack {src} not found", file=sys.stderr)
        return 1
    if dest.exists() and any(dest.iterdir()) and not args.force:
        print(f"{dest} already has files; use --force to add the missing ones (existing files are never overwritten)")
    dest.mkdir(parents=True, exist_ok=True)
    year_json = dest / "year.json"
    if not year_json.exists():
        print(f"{year_json} is missing: create it first (titles, transit calendar); see content/2027/year.json",
              file=sys.stderr)
        return 1
    transits = json.load(open(year_json, encoding="utf-8"))["transits"]["jupiter"]
    made = 0
    for f in sorted(src.rglob("*.json")):
        rel = f.relative_to(src)
        if rel.name in SKIP or rel.parts[0] == "overview":
            continue
        out = dest / rel
        if out.exists():
            continue
        data = json.load(open(f, encoding="utf-8"))
        if rel.as_posix() == "transits/jupiter.json":
            data = jupiter_skeleton(data, transits)
        elif rel.name not in COPY_VERBATIM:
            data = skeleton(data)
        out.parent.mkdir(parents=True, exist_ok=True)
        json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        made += 1
    print(f"created {made} files in {dest}; run:  python pack.py check {args.year}")
    return 0


def cmd_sample(args) -> int:
    """TEST ONLY: a 2027-looking pack made from the 2026 text (years swapped), so the whole pipeline can be tried
    before the real 2027 text exists.  Written to content_sample/, never to content/."""
    import shutil
    src = Path(args.root) / str(args.source)
    dest = Path(args.root).parent / "content_sample" / str(args.year)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    for f in dest.rglob("*.json"):
        if f.name != "year.json":
            text = f.read_text(encoding="utf-8").replace(str(args.source), str(args.year))
            f.write_text(text, encoding="utf-8")
    real = json.load(open(Path(args.root) / str(args.year) / "year.json", encoding="utf-8"))
    real.pop("inherits", None)
    real.pop("inherit_files", None)
    json.dump(real, open(dest / "year.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"SAMPLE pack written to {dest}  (2026 wording, 2027 titles and transit dates; NOT for customers)")
    print(f"use it:  set CONTENT_ROOT={dest.parent}   (macOS/Linux: export CONTENT_ROOT=...)")
    return 0


def cmd_check(args) -> int:
    try:
        pack = ContentPack(args.root, args.year)
    except ContentError as exc:
        print(exc, file=sys.stderr)
        return 1
    errors, warnings = pack.validate()
    by_file = collections.OrderedDict()
    for e in errors:
        by_file.setdefault(e.split(":")[0].split(" ")[0], []).append(e)
    for f, items in by_file.items():
        print(f"{f}: {len(items)} problem(s)")
        for e in items[: args.show]:
            print("   ", e)
        if len(items) > args.show:
            print(f"    ... and {len(items) - args.show} more")
    for w in warnings:
        print("warning:", w)
    print(f"\n{args.year}: {len(errors)} problem(s), {len(warnings)} warning(s)  ->  "
          + ("READY: every customer combination can be served" if not errors else "NOT READY"))
    return 1 if errors else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(CONTENT_ROOT))
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("year", type=int)
    n.add_argument("--from", dest="source", type=int, required=True)
    n.add_argument("--force", action="store_true")
    n.set_defaults(fn=cmd_new)
    s = sub.add_parser("sample")
    s.add_argument("year", type=int)
    s.add_argument("--from", dest="source", type=int, default=2026)
    s.set_defaults(fn=cmd_sample)
    c = sub.add_parser("check")
    c.add_argument("year", type=int)
    c.add_argument("--show", type=int, default=3, help="problems to list per file")
    c.set_defaults(fn=cmd_check)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
