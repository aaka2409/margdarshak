#!/usr/bin/env python3
"""Live test of the chart lookup only (no report text needed):  python chart_check.py req.json"""
import json
import sys

from report import config
from report.astro import mulank
from report.model import Person

data = json.load(open(sys.argv[1], encoding="utf-8"))
data.pop("chart", None)
prov = config.chart_provider()
if prov is None:
    sys.exit("VEDIC_ASTRO_API_KEY is empty: put it in .env")
chart = prov.get_chart(Person.from_request(data))
print(json.dumps(chart if isinstance(chart, dict) else chart.__dict__, indent=1, ensure_ascii=False))
print("Mulank:", mulank(data["dob"]))
