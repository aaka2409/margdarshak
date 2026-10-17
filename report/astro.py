"""Small, dependency-free astrology helpers used across the report."""
from __future__ import annotations

import re
from datetime import date

SIGNS = ["aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra", "scorpio",
         "sagittarius", "capricorn", "aquarius", "pisces"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]
WEEKDAY_PLANET = {"sunday": "sun", "monday": "moon", "tuesday": "mars", "wednesday": "mercury",
                  "thursday": "jupiter", "friday": "venus", "saturday": "saturn"}

# The eight life areas, in report order.  `key` is the monthly-content key,
# `yearly` the yearly-forecast file, `icon` the artwork family.
AREAS = [
    {"key": "relationship", "yearly": "relationship", "label": "Relationship", "icon": "relationship",
     "yearly_title": "Relationship Forecast {year}"},
    {"key": "education", "yearly": "education", "label": "Education", "icon": "education_book",
     "yearly_title": "Education Forecast {year}"},
    {"key": "career", "yearly": "career", "label": "Career", "icon": "career_growth",
     "yearly_title": "Career Forecast {year}"},
    {"key": "finance", "yearly": "finance", "label": "Finance", "icon": "finance_coin",
     "yearly_title": "Finance Forecast {year}"},
    {"key": "wealth_assets", "yearly": "wealth", "label": "Wealth & Assets", "icon": "wealth_assets",
     "yearly_title": "Wealth & Assets {year}"},
    {"key": "family", "yearly": "family", "label": "Family", "icon": "family_home",
     "yearly_title": "Family Forecast {year}"},
    {"key": "health_emotional", "yearly": "health", "label": "Health & Emotional Well-Being", "icon": "health_heart",
     "yearly_title": "Health & Emotional Well-Being {year}"},
    {"key": "travel_movement", "yearly": "travel", "label": "Travel & Movement", "icon": "travel_compass",
     "yearly_title": "Travel & Movement {year}"},
]

# Vedic special aspects, counted inclusively from the planet's own house.
ASPECTS = {"saturn": (3, 7, 10), "jupiter": (5, 7, 9), "rahu": (5, 7, 9), "ketu": (5, 7, 9)}

SIGN_ELEMENT = {"aries": "fire", "leo": "fire", "sagittarius": "fire",
                "taurus": "earth", "virgo": "earth", "capricorn": "earth",
                "gemini": "air", "libra": "air", "aquarius": "air",
                "cancer": "water", "scorpio": "water", "pisces": "water"}


class AstroError(ValueError):
    pass


def norm_sign(value: str | None) -> str:
    """'Aquarius ' -> 'aquarius'; raises on anything that is not a zodiac sign."""
    s = (value or "").strip().lower()
    if s not in SIGNS:
        raise AstroError(f"'{value}' is not a zodiac sign")
    return s


def house_of(sign: str, reference: str) -> int:
    """House number (1-12) of `sign` counted from the `reference` sign (ascendant or Moon sign)."""
    return (SIGNS.index(norm_sign(sign)) - SIGNS.index(norm_sign(reference))) % 12 + 1


def aspected_houses(house: int, planet: str) -> list[int]:
    """Houses a planet in `house` aspects, by its special aspects (the 7th included)."""
    return [((house - 1) + (n - 1)) % 12 + 1 for n in ASPECTS[planet]]


def activated_houses(planet_houses: dict[str, int]) -> list[int]:
    """Union of the houses occupied and aspected by the given planets, sorted."""
    out: set[int] = set()
    for planet, house in planet_houses.items():
        out.add(house)
        out.update(aspected_houses(house, planet))
    return sorted(out)


def parse_dob(dob: str) -> date:
    """Accepts DD/MM/YYYY (the format the order system sends) or YYYY-MM-DD."""
    dob = (dob or "").strip()
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", dob)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", dob)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    raise AstroError(f"date of birth '{dob}' is not in DD/MM/YYYY format")


def mulank(dob: str) -> int:
    """Mulank: the day of birth reduced to a single digit (1-9)."""
    n = parse_dob(dob).day
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"
