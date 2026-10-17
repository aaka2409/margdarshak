#!/usr/bin/env python3
"""Build one report from the command line.

    python generate.py fixtures/sample_customer.json --year 2026 --out out/report.pdf

The input is the same JSON the order system posts to the API.  If it contains
a "chart" object that is used; otherwise the chart service is called.
"""
import argparse
import json
import sys
import time

import report
from report import config


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("request", help="JSON file with the customer's details")
    ap.add_argument("--year", type=int, default=config.REPORT_YEAR)
    ap.add_argument("--out", default=None, help="output PDF (default: out/<name>_<year>.pdf)")
    ap.add_argument("--keep-html", default=None, help="also save the intermediate HTML here")
    ap.add_argument("--draft", action="store_true", help="print even if the layout check fails (for design work only)")
    args = ap.parse_args()
    data = json.load(open(args.request, encoding="utf-8"))
    out = args.out or f"out/{data.get('name', 'report').replace(' ', '_')}_{args.year}.pdf"
    t0 = time.time()
    try:
        res = report.generate(data, args.year, out, chart_provider=config.chart_provider(), keep_html=args.keep_html,
                              strict=not args.draft, allow_sample=True)
    except (ValueError, report.ChartError, report.ContentError, report.RenderError) as exc:
        print(f"NOT GENERATED: {exc}", file=sys.stderr)
        return 1
    if res.get('sample'):
        print('  NOTE: this used SAMPLE text (2026 wording). Test only.', file=sys.stderr)
    for p in res.get("problems", []):
        print(f"  LAYOUT PROBLEM: {p}", file=sys.stderr)
    print(f"{res['output']}: {res['pages']} pages, Moon {res['moon_sign']}, ascendant {res['ascendant']}, "
          f"Mulank {res['mulank']} ({time.time() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
