"""Writes report/data/moon_phases.json: the exact new / first-quarter / full / last-quarter moon times (UTC) for the
years the reports are sold for.  Run it once per new year; reports only read the file, they never need PyEphem.

    pip install ephem
    python3 tools/moon_phases.py 2027 2029
"""
import json
import sys
from pathlib import Path

import ephem

OUT = Path(__file__).resolve().parent.parent / "report" / "data" / "moon_phases.json"
STEPS = (("new", ephem.next_new_moon), ("first", ephem.next_first_quarter_moon),
         ("full", ephem.next_full_moon), ("last", ephem.next_last_quarter_moon))


def events(year: int) -> list[list[str]]:
    """Every phase from 1 Dec of the previous year to 31 Jan of the next (so the days at the edges can be placed)."""
    start, end = ephem.Date(f"{year - 1}/12/01"), ephem.Date(f"{year + 1}/02/01")
    found = []
    for name, fn in STEPS:
        d = fn(start)
        while d < end:
            found.append((d.datetime(), name))
            d = fn(d)
    found.sort()
    return [[name, t.strftime("%Y-%m-%dT%H:%M:%SZ")] for t, name in found]


if __name__ == "__main__":
    first, last = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) == 3 else (2027, 2029)
    table = json.loads(OUT.read_text()) if OUT.exists() else {}
    for y in range(first, last + 1):
        table[str(y)] = events(y)
    OUT.write_text("{\n" + ",\n".join(f'"{y}":{json.dumps(v, separators=(",", ":"))}' for y, v in sorted(table.items())) + "\n}\n", encoding="utf-8")
    print(f"wrote {OUT} for {first}-{last}")
