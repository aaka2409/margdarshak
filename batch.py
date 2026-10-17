#!/usr/bin/env python3
"""Generate reports for a whole list of customers.

    python batch.py customers.csv --year 2027 --out-dir reports --workers 3
    python batch.py customers.xlsx --year 2027 --email         # also e-mail each PDF
    python batch.py customers.json --resume                    # re-run later: finished PDFs are skipped

Input: .csv / .xlsx / .json with one row per customer and the columns
    name, dob (DD/MM/YYYY), tob (HH:MM), pob, lat, lon, tz, email, sex, user_id
(a row may also carry a ready "chart" in JSON input, see fixtures/).  Rows missing lat/lon/tob
can only be served when the row has a chart.

Every row is reported in reports/batch_log.csv (ok / failed + the reason).  One bad row never stops the others.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

FIELDS = ["row", "name", "email", "status", "pages", "seconds", "file", "error"]


def read_rows(path: Path) -> list[dict]:
    ext = path.suffix.lower()
    if ext == ".json":
        data = json.load(open(path, encoding="utf-8"))
        return data if isinstance(data, list) else [data]
    if ext == ".csv":
        with open(path, encoding="utf-8-sig", newline="") as fh:
            return [{k.strip().lower(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(fh)]
    if ext in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        ws = load_workbook(path, read_only=True, data_only=True).active
        rows = ws.iter_rows(values_only=True)
        head = [str(h).strip().lower() if h is not None else "" for h in next(rows)]
        return [{h: ("" if v is None else str(v).strip()) for h, v in zip(head, r) if h} for r in rows if any(r)]
    raise SystemExit(f"unsupported input type '{ext}' (use .csv, .xlsx or .json)")


def file_name(i: int, row: dict, year: int) -> str:
    who = re.sub(r"[^A-Za-z0-9]+", "_", str(row.get("name", "customer"))).strip("_") or "customer"
    ident = re.sub(r"[^A-Za-z0-9]+", "", str(row.get("user_id") or f"r{i}"))
    return f"{ident}_{who}_{year}.pdf"


def work(i: int, row: dict, year: int, out: str, send: bool, draft: bool) -> dict:
    """Runs in a worker process."""
    import report
    from report import config
    t0 = time.time()
    res = {"row": i, "name": row.get("name", ""), "email": row.get("email", ""), "file": out}
    try:
        info = report.generate(row, year, out, chart_provider=config.chart_provider(), strict=not draft,
                              allow_sample=config.ALLOW_SAMPLE_CONTENT)
        if send:
            import mailer
            mailer.send_report(row.get("email", ""), row.get("name", "User"), year, out)
        res.update(status="ok", pages=info["pages"], error="")
    except Exception as exc:       # noqa: BLE001 - recorded per row, the batch carries on
        res.update(status="failed", pages="", error=f"{type(exc).__name__}: {exc}"[:600])
    res["seconds"] = round(time.time() - t0, 1)
    return res


def main() -> int:
    from report import config
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--year", type=int, default=config.REPORT_YEAR)
    ap.add_argument("--out-dir", default="reports")
    ap.add_argument("--workers", type=int, default=2, help="reports built at once (each uses a browser; 2-4 is sensible)")
    ap.add_argument("--email", action="store_true", help="e-mail each PDF to the customer's address")
    ap.add_argument("--resume", action="store_true", help="skip customers whose PDF already exists")
    ap.add_argument("--limit", type=int, default=0, help="only the first N rows (to test)")
    ap.add_argument("--draft", action="store_true", help="print even when the layout check fails")
    a = ap.parse_args()

    rows = read_rows(Path(a.input))
    if a.limit:
        rows = rows[: a.limit]
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "batch_log.csv"
    new_log = not log_path.exists()
    jobs, skipped = [], 0
    for i, row in enumerate(rows, 1):
        out = out_dir / file_name(i, row, a.year)
        if a.resume and out.exists():
            skipped += 1
            continue
        jobs.append((i, row, str(out)))
    print(f"{len(rows)} customers, {skipped} already done, {len(jobs)} to build with {a.workers} worker(s)")

    ok = failed = 0
    t0 = time.time()
    with open(log_path, "a", encoding="utf-8", newline="") as fh, ProcessPoolExecutor(a.workers) as pool:
        w = csv.DictWriter(fh, FIELDS)
        if new_log:
            w.writeheader()
        futures = [pool.submit(work, i, r, a.year, o, a.email, a.draft) for i, r, o in jobs]
        for n, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            w.writerow({k: r.get(k, "") for k in FIELDS})
            fh.flush()
            ok += r["status"] == "ok"
            failed += r["status"] != "ok"
            tail = "" if r["status"] == "ok" else f"  <- {r['error']}"
            print(f"[{n}/{len(jobs)}] row {r['row']} {r['name']}: {r['status']} ({r['seconds']}s){tail}")
    print(f"\nfinished in {time.time() - t0:.0f}s: {ok} ok, {failed} failed.  Log: {log_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
