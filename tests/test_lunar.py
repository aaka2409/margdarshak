"""Moon-phase facts printed on the month openers: python -m pytest -q tests/test_lunar.py  (instant, no browser)"""
import calendar
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from report import lunar  # noqa: E402


def test_january_2027_matches_the_reference_design():
    cards = lunar.month_view(2027, 1)["cards"]
    assert [(c["date"], c["time"]) for c in cards] == [
        ("8 Jan", "01:54 IST"), ("16 Jan", "02:04 IST"), ("22 Jan", "17:47 IST"), ("29 Jan", "16:25 IST")]
    assert [c["label"] for c in cards] == ["New Moon", "First Quarter", "Full Moon", "Last Quarter"]


@pytest.mark.parametrize("month", range(1, 13))
def test_every_month_of_2027_has_a_ring_of_the_right_size(month):
    v = lunar.month_view(2027, month)
    assert len(v["discs"]) == calendar.monthrange(2027, month)[1]            # one small moon per day
    assert all(c["date"] and c["time"].endswith("IST") for c in v["cards"])   # all four phases occur every month of 2027
    assert sum(d["key"] for d in v["discs"]) == 4                             # and each is marked on the ring
    assert all(1 <= d["sprite"] <= 12 for d in v["discs"])


def test_ring_shows_the_real_phase_on_the_key_days():
    v = lunar.month_view(2027, 1)
    by_day = {d["day"]: d for d in v["discs"]}
    assert by_day[8]["sprite"] == 1 and by_day[8]["key"]                      # new moon: dark
    assert by_day[22]["sprite"] == 12 and by_day[22]["key"]                   # full moon: bright
    assert not by_day[10]["flip"] and by_day[25]["flip"]                      # waxing and waning face opposite ways


def test_a_year_without_a_table_is_refused():
    with pytest.raises(lunar.MoonDataError):
        lunar.month_view(1999, 1)
