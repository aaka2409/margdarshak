"""The moon's phases for one calendar month, as the month openers print them.

Every customer gets the same sky, so this is year data, not customer data: report/data/moon_phases.json holds the exact
new / first-quarter / full / last-quarter moon times (UTC, from tools/moon_phases.py).  From them we print the four dates
and times in Indian Standard Time and place a small moon for every day of the month (its phase at noon IST, found
between the two phase events that surround it).  A year that is not in the file raises MoonDataError: the report is
refused rather than printed with invented dates.
"""
from __future__ import annotations

import calendar
import json
import math
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
PHASES = ("new", "first", "full", "last")
LABELS = {"new": "New Moon", "first": "First Quarter", "full": "Full Moon", "last": "Last Quarter"}
MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
_FILE = Path(__file__).parent / "data" / "moon_phases.json"

# the ring on the opener (page coordinates in pt)
CX, CY, RING_R, DISC = 297.6, 399.0, 158.0, 12.6


class MoonDataError(RuntimeError):
    pass


@lru_cache(maxsize=None)
def _events(year: int) -> tuple:
    try:
        table = json.loads(_FILE.read_text(encoding="utf-8"))
        rows = table[str(year)]
    except (OSError, ValueError, KeyError) as exc:
        raise MoonDataError(f"no moon-phase table for {year}: run  python3 tools/moon_phases.py {year} {year}") from exc
    out = [(datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc), name) for name, t in rows]
    out.sort()
    return tuple(out)


def _phase_at(events: tuple, when: datetime) -> float:
    """0 = new, .25 = first quarter, .5 = full, .75 = last quarter (steady between the events around `when`)."""
    for (t0, n0), (t1, _) in zip(events, events[1:]):
        if t0 <= when < t1:
            return ((PHASES.index(n0) + (when - t0) / (t1 - t0)) / 4) % 1.0
    raise MoonDataError(f"{when:%Y-%m-%d} is outside the moon-phase table")


def month_view(year: int, month: int) -> dict:
    """{"hindi", "cards": [4 x {phase,label,date,time}], "discs": [one per day {x,y,sprite,flip,key,day}]}"""
    events = _events(year)
    days = calendar.monthrange(year, month)[1]

    cards, key_days = [], {}
    for ph in PHASES:
        hit = next(((t.astimezone(IST), t) for t, n in events if n == ph
                    and t.astimezone(IST).year == year and t.astimezone(IST).month == month), None)
        if hit:
            local = hit[0]
            cards.append({"phase": ph, "label": LABELS[ph], "date": f"{local.day} {local:%b}", "time": f"{local:%H:%M} IST"})
            key_days[local.day] = ph
        else:                                   # a short February can miss one phase
            cards.append({"phase": ph, "label": LABELS[ph], "date": "", "time": ""})

    discs = []
    for d in range(1, days + 1):
        noon = datetime(year, month, d, 12, 0, tzinfo=IST).astimezone(timezone.utc)
        p = _phase_at(events, noon)
        lit = (1 - math.cos(2 * math.pi * p)) / 2                       # 0 new .. 1 full
        sprite = 1 if lit < 0.04 else max(1, min(12, round(lit * 12)))  # phase_01 (new) .. phase_12 (full)
        a = math.radians((d - 1) * 360 / days)                          # day 1 at the top, clockwise
        discs.append({"day": d, "sprite": sprite, "flip": p >= 0.5, "key": d in key_days,
                      "x": round(CX + RING_R * math.sin(a) - DISC / 2, 2),
                      "y": round(CY - RING_R * math.cos(a) - DISC / 2, 2)})
    return {"hindi": MONTHS_HI[month - 1], "cards": cards, "discs": discs}
