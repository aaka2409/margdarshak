"""Where the birth chart comes from.

The report needs: Moon sign, ascendant, Sun sign, and the panchang details
printed on the profile page.  `VedicAstroProvider` asks vedicastroapi.com (the
service the 2026 report used).  If a request already carries a `chart` object
(tests, re-runs, or a different chart source) it is used as-is.

Unlike the 2026 code, a failed lookup is an error.  A report is never built
on an "Unknown" Moon sign or ascendant.
"""
from __future__ import annotations

import time

import requests

from .astro import SIGNS

BASE = "https://api.vedicastroapi.com/v3-json"
CHART_FIELDS = ["moon_sign", "sun_sign", "ascendant", "ascendant_lord", "rasi_lord", "nakshatra", "nakshatra_lord",
                "tithi", "yoga", "karana", "gana", "yoni", "nadi", "varna", "vasya", "paya", "tatva"]


class ChartError(Exception):
    """The birth chart could not be obtained."""


def chart_from_request(data: dict) -> dict | None:
    """A chart supplied with the request (key 'chart'), validated, or None."""
    chart = data.get("chart")
    if not chart:
        return None
    for key in ("moon_sign", "ascendant"):
        if str(chart.get(key, "")).strip().lower() not in SIGNS:
            raise ChartError(f"supplied chart has no valid {key.replace('_', ' ')}: {chart.get(key)!r}")
    return {k: chart.get(k, "") for k in CHART_FIELDS}


class VedicAstroProvider:
    def __init__(self, api_key: str, timeout: float = 20, retries: int = 2):
        if not api_key:
            raise ChartError("VEDIC_ASTRO_API_KEY is not set")
        self.api_key, self.timeout, self.retries = api_key, timeout, retries

    def _get(self, path: str, person, **extra):
        if person.lat in (None, "") or person.lon in (None, ""):
            raise ChartError("latitude and longitude of the birth place are required")
        if not person.tob:
            raise ChartError("time of birth is required")
        params = {"api_key": self.api_key, "dob": person.dob, "tob": person.tob, "lat": str(person.lat),
                  "lon": str(person.lon), "tz": person.tz, "lang": "en", **extra}
        last = None
        for attempt in range(self.retries + 1):
            try:
                r = requests.get(f"{BASE}/{path}", params=params, timeout=self.timeout)
                r.raise_for_status()
                body = r.json()
                if body.get("status") == 200 and body.get("response"):
                    return body["response"]
                last = f"{path}: {str(body.get('response') or body)[:160]}"
            except (requests.RequestException, ValueError) as exc:
                last = f"{path}: {type(exc).__name__}"
            time.sleep(0.6 * (attempt + 1))
        raise ChartError(f"chart service did not answer ({last})")

    def get_chart(self, person) -> dict:
        moon = self._get("horoscope/planet-report", person, planet="Moon")
        asc = self._get("horoscope/ascendant-report", person)
        ext = self._get("extended-horoscope/extended-kundli-details", person)
        moon0 = moon[0] if isinstance(moon, list) else moon
        asc0 = asc[0] if isinstance(asc, list) else asc
        chart = {
            "moon_sign": moon0.get("planet_zodiac", ""),
            "ascendant": asc0.get("ascendant", ""),
            "ascendant_lord": asc0.get("ascendant_lord", ""),
            "sun_sign": ext.get("sun_sign", ""),
            "rasi_lord": ext.get("rasi_lord", ""),
            **{k: ext.get(k, "") for k in ("nakshatra", "nakshatra_lord", "tithi", "yoga", "karana", "gana", "yoni",
                                           "nadi", "varna", "vasya", "paya", "tatva")},
        }
        for key in ("moon_sign", "ascendant"):
            if str(chart[key]).strip().lower() not in SIGNS:
                raise ChartError(f"chart service returned no valid {key.replace('_', ' ')} ({chart[key]!r})")
        return chart
