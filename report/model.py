"""Turns one customer + one content pack into the data the templates print.

This is the whole "logic" of the report, unchanged from 2026:

    Moon sign            -> monthly forecasts and scores, the eight yearly forecasts
    Ascendant            -> the seven planet transits, gemstones
    Mulank (birth day)   -> lucky / unlucky, rudraksha, do's & don'ts, affirmation
    Mulank x Moon sign   -> personality overview, "how the year shapes you"
    Mulank x Moon element-> spiritual remedies

Nothing is guessed.  If the pack lacks the text for this customer, ContentError
is raised and no report is produced.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from dataclasses import dataclass, field

from . import lunar, svg
from .astro import (AREAS, MONTHS, WEEKDAY_PLANET, AstroError, activated_houses, house_of, mulank, norm_sign,
                    ordinal, parse_dob)
from .content import ContentError, ContentPack

MONTHLY_PLANETS = [("venus", "Venus"), ("mars", "Mars"), ("mercury", "Mercury"), ("sun", "Sun")]

PROFILE_FIELDS = [  # label, chart key  (reading order of the profile grid)
    ("Nakshatra Lord", "nakshatra_lord"), ("Sex", "@sex"), ("Yoga", "yoga"), ("Date of Birth", "@dob"),
    ("Karana", "karana"), ("Time of Birth", "@tob"), ("Gana", "gana"), ("Place of Birth", "@pob"),
    ("Yoni", "yoni"), ("Nadi", "nadi"), ("Varna", "varna"), ("Vashya", "vasya"),
    ("Ascendant Lord", "ascendant_lord"), ("Paya", "paya"), ("Rashi Lord", "rasi_lord"), ("Tatva", "tatva"),
    ("Nakshatra", "nakshatra"), ("Tithi", "tithi"),
]


@dataclass
class Person:
    name: str
    dob: str
    tob: str = ""
    pob: str = ""
    sex: str = ""
    email: str = ""
    user_id: str | int | None = None
    lat: float | str | None = None
    lon: float | str | None = None
    tz: float = 5.5
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_request(cls, data: dict) -> "Person":
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("name is required")
        dob = str(data.get("dob") or "").strip()
        parse_dob(dob)  # validates
        try:
            tz = float(data.get("tz", 5.5))
        except (TypeError, ValueError):
            raise ValueError(f"tz must be a number of hours east of UTC (found {data.get('tz')!r})")
        known = {"name", "dob", "tob", "pob", "sex", "email", "user_id", "lat", "lon", "tz"}
        return cls(name=name, dob=dob, tob=str(data.get("tob") or "").strip(), pob=str(data.get("pob") or "").strip(),
                   sex=str(data.get("sex") or "").strip(), email=str(data.get("email") or "").strip(),
                   user_id=data.get("user_id"), lat=data.get("lat"), lon=data.get("lon"), tz=tz,
                   extra={k: v for k, v in data.items() if k not in known})


def _first_sentence(text: str) -> str:
    plain = re.sub(r"</?[bi]>", "", text)
    m = re.match(r"(.+?[.!?][”\"’']?)(?:\s|$)", plain)
    return m.group(1) if m else plain


def _y(text, year: int):
    """Resolve {year} placeholders in titles."""
    if isinstance(text, list):
        return [_y(t, year) for t in text]
    return str(text).replace("{year}", str(year))


def _pretty_date(mmdd: str) -> str:
    m, d = (int(x) for x in mmdd.split("-"))
    return f"{MONTHS[m - 1].title()} {d}"


def build(person: Person, chart: dict, pack: ContentPack) -> dict:
    """Assemble everything one report prints.  `chart` comes from a ChartProvider."""
    year = pack.year
    try:
        moon = norm_sign(chart.get("moon_sign"))
        asc = norm_sign(chart.get("ascendant"))
    except AstroError as exc:
        raise ContentError(f"birth chart incomplete: {exc} (Moon sign and ascendant are both required)") from exc
    sun = (chart.get("sun_sign") or "").strip().lower()
    num = mulank(person.dob)
    element = pack.get("elements.json", moon, what="Moon-sign element")
    fixed = pack.load("fixed.json")
    meta = pack.meta
    chapters = {c["id"]: {**c, "title": _y(c["title"], year), "opener": _y(c.get("opener", []), year)}
                for c in meta["chapters"]}

    ctx: dict = {
        "year": year, "title_hi": meta["title_hi"], "title_en": meta["title_en"],
        "report_label": meta.get("report_label", "Personal Astrology Report"),
        "person": person, "chart": chart, "moon": moon, "sun": sun, "asc": asc, "mulank": num,
        "element": element, "chapters": chapters, "chapter_list": [c for c in chapters.values() if c.get("toc", True)],
        "fixed": fixed, "contact": meta.get("contact", {}),
        "back_cover": meta.get("back_cover", []), "back_cover_tagline": meta.get("back_cover_tagline", ""),
        "months_list": MONTHS,
    }

    # ---- profile ---------------------------------------------------------------------------
    rows = []
    for label, key in PROFILE_FIELDS:
        value = getattr(person, key[1:], "") if key.startswith("@") else chart.get(key, "")
        if str(value or "").strip():
            rows.append({"label": label, "value": str(value).strip()})
    ctx["profile_rows"] = rows
    born = f"Born {person.dob}"
    if person.tob:
        born += f" at {person.tob}"
    if person.pob:
        born += f", {person.pob}"
    ctx["born_line"] = born

    # ---- chapter 01 / 02 -------------------------------------------------------------------
    mirror = pack.get(f"overview/mulank{num}.json", moon, what="personality overview")
    ctx["mirror"] = {"lede": _first_sentence(mirror[0]), "paras": mirror}
    ctx["shape"] = {"paras": pack.get(f"significance/mulank{num}.json", moon, what="yearly overview")}

    # ---- chapter 03: months ----------------------------------------------------------------
    monthly = pack.load(f"monthly/{moon}.json")
    months = []
    for i, name in enumerate(MONTHS):
        scores = pack.get(f"monthly/{moon}.json", "scores", name, what="monthly scores")
        texts = pack.get(f"monthly/{moon}.json", "months", name, what="monthly forecast")
        areas = []
        for a in AREAS:
            if a["key"] not in scores or a["key"] not in texts:
                raise ContentError(f"monthly/{moon}.json: {name} has no '{a['key']}' entry")
            areas.append({"key": a["key"], "label": a["label"], "icon": a["icon"],
                          "level": svg.level_of(scores[a["key"]]), "paras": texts[a["key"]]})
        months.append({"name": name.title(), "abbr": name[:3].title(), "num": f"{i + 1:02d}", "index": i + 1,
                       "areas": areas, "radar": svg.radar(name[:3].title(), areas)})
    ctx["months"] = months
    try:                       # the sky is the same for everyone: phase dates and times for each month's opener
        ctx["moon_months"] = [lunar.month_view(year, i) for i in range(1, 13)]
    except lunar.MoonDataError as exc:
        raise ContentError(str(exc)) from exc
    ctx["glance_rows"] = [{"label": a["label"], "levels": [m["areas"][j]["level"] for m in months]}
                          for j, a in enumerate(AREAS)]

    # ---- chapter 03 continued: yearly forecasts --------------------------------------------
    yearly = []
    for i, a in enumerate(AREAS):
        entry = pack.get(f"yearly/{a['yearly']}.json", moon, what=f"{a['label']} yearly forecast")
        sections = [s for s in entry.get("sections", []) if not s.get("hidden")]
        yearly.append({"num": f"{i + 1:02d}", "title": a["yearly_title"].format(year=year), "icon": a["icon"],
                       "intro": entry.get("intro", []), "sections": sections})
    ctx["yearly"] = yearly

    # ---- chapter 04: transits (all counted from the ascendant) -----------------------------
    transits_meta = meta["transits"]
    jup = pack.get("transits/jupiter.json", asc, what="Jupiter transit")
    periods = []
    for p in jup["periods"]:
        if "house" in p:
            periods.append({"house": p["house"], "house_label": f"{ordinal(p['house'])} House",
                            "dates": f"{p['from']} to {p['to']}", "in_label": f"Jupiter in {p['sign']}",
                            "from": p["from"], "to": p["to"],
                            "label": f"Jupiter in {p['sign']} ({ordinal(p['house'])} House)", "body": p["body"]})
        else:  # heading in free form: print it as written, no timeline entry
            periods.append({"house": None, "house_label": p["heading"], "dates": "", "in_label": "",
                            "label": None, "body": p["body"]})
    timeline_periods = [p for p in periods if p["label"]]
    if len(timeline_periods) != len(periods) or not timeline_periods:
        # fall back to the year's transit calendar so the diagram is still right
        timeline_periods = [{"from": _pretty_date(t["from"]), "to": _pretty_date(t["to"]),
                             "label": f"Jupiter in {t['sign']} ({ordinal(house_of(t['sign'], asc))} House)"}
                            for t in transits_meta["jupiter"]]
    for p in periods:
        if p["house"] is not None:
            sign = p["in_label"].split(" in ")[-1]
            expected = house_of(sign, asc)
            if expected != p["house"]:
                raise ContentError(
                    f"transits/jupiter.json [{asc}]: heading says {p['label']}, but {sign} is the "
                    f"{ordinal(expected)} house from a {asc.title()} ascendant")
    xs = [svg._year_fraction_x(p["from"]) for p in timeline_periods]
    xs[0] = 5.0
    ends = xs[1:] + [161.0]
    bar, last_end = [], -1.0
    for a, b, p in zip(xs, ends, timeline_periods):
        left = round((a - 5) / 156 * 100, 2)
        row = 1 if left < last_end else 0           # label would run into the previous one: drop it a line
        last_end = left + len(p["label"]) * 1.05 if row == 0 else last_end
        bar.append({"left": left, "width": round((b - a) / 156 * 100, 2), "label": p["label"], "row": row})
    ctx["jupiter"] = {"periods": periods, "closing": jup.get("closing", []),
                      "timeline": svg.timeline(timeline_periods), "bar": bar}

    def house_charts(planets: list[str], title: str) -> list[dict]:
        spans = transits_meta[planets[0]]
        charts = []
        for i, span in enumerate(spans):
            placed = {}
            for pl in planets:
                sign = transits_meta[pl][i]["sign"] if i < len(transits_meta[pl]) else transits_meta[pl][-1]["sign"]
                placed[pl] = house_of(sign, asc)
            active = activated_houses(placed)
            whole_year = len(spans) == 1
            charts.append({
                "svg": svg.kundali_houses(active), "active": active,
                "title": f"{title} · Houses activated this year" if whole_year else
                         f"{title} · {_pretty_date(span['from'])} to {_pretty_date(span['to'])}",
                "caption": f"Houses from your ascendant · {asc.title()}",
                "placed": ", ".join(f"{pl.title()} in {transits_meta[pl][min(i, len(transits_meta[pl]) - 1)]['sign']} "
                                    f"({ordinal(h)} house)" for pl, h in placed.items()),
            })
        return charts

    ctx["saturn"] = {"paras": pack.get("transits/saturn.json", asc, what="Saturn transit"),
                     "charts": house_charts(["saturn"], "Saturn")}
    ctx["rahu"] = {"paras": pack.get("transits/rahu.json", asc, what="Rahu-Ketu transit"),
                   "charts": house_charts(["rahu", "ketu"], "Rahu-Ketu")}
    ctx["planet_months"] = []
    for i, (key, label) in enumerate(MONTHLY_PLANETS):
        entries = pack.get(f"transits/{key}.json", asc, what=f"{label} transit")
        ctx["planet_months"].append({
            "key": key, "label": label, "num": f"{i + 4:02d}",
            "months": [{"name": e["month"].title(), "num": f"{j + 1:02d}", "index": j + 1, "body": e["body"]}
                       for j, e in enumerate(entries)]})

    # ---- chapter 05: energies --------------------------------------------------------------
    m = pack.get("mulank.json", num, what=f"Mulank {num} guidance")

    def energies(kind: str) -> dict:
        e = m[kind]
        lucky = kind == "lucky"
        day = e["day"].strip().lower()
        if day not in WEEKDAY_PLANET:
            raise ContentError(f"mulank.json: Mulank {num} {kind} day '{e['day']}' is not a weekday")
        return {**e,
                "dates_label": ", ".join(str(d) for d in e["dates"]),
                "colours_label": e.get("colours_label") or ", ".join(e["colours"]),
                "calendar": svg.calendar(e["dates"], lucky),
                "swatches": svg.swatches([pack.swatch(c) for c in e["colours"]], lucky),
                "week": svg.week_ring(day, WEEKDAY_PLANET[day], lucky)}

    ctx["lucky"], ctx["unlucky"] = energies("lucky"), energies("unlucky")
    beads = m["rudraksha"]["beads"]
    ctx["rudraksha"] = {"beads": beads, "label": " · ".join(f"{b} MUKHI" for b in beads),
                        "description": m["rudraksha"]["description"], "art": svg.rudraksha_group(beads),
                        "emblem": svg.rudraksha_emblem(beads[0])}

    gems = pack.load("gemstones.json")
    mine = pack.get("gemstones.json", "by_ascendant", asc, what="gemstones")
    aliases = gems.get("aliases", {})
    lucky_gems = []
    for g in mine["lucky"]:
        key = aliases.get(g, g)
        desc = gems.get("stones", {}).get(key)
        if not desc:
            raise ContentError(f"gemstones.json: lucky stone '{g}' ({asc}) has no description")
        lucky_gems.append({"name": g, "text": desc, "slug": svg.gem_slug(key)})
    ctx["gems"] = {"lucky": lucky_gems,
                   "unlucky": [{"name": g, "slug": svg.gem_slug(aliases.get(g, g))} for g in mine.get("unlucky", [])],
                   "process": gems["process"], "emblem": svg.gem_emblem(aliases.get(mine["lucky"][0], mine["lucky"][0]))}

    # ---- chapters 06-08 --------------------------------------------------------------------
    ctx["dos"], ctx["donts"] = m["dos"], m["donts"]
    rem = pack.get("mulank.json", num, "remedies", element, what="spiritual remedies")
    ctx["remedies"] = {"intro": rem["intro"],
                       "items": [{"num": f"{i + 1:02d}", "text": t, "art": svg.remedy_medallion(svg.remedy_kind(t))}
                                 for i, t in enumerate(rem["items"])]}
    aff = m["affirmation"]
    ritual = aff["ritual"]
    kind = svg.remedy_kind(ritual.get("name", "") + " " + " ".join(r["text"] for r in ritual["rows"][:1]))
    ctx["affirmation"] = {**aff, "ritual_emblem": svg.icon_emblem(kind)}

    # ---- artwork that carries the customer's signs ------------------------------------------
    # where the painted openers had their title (pt from the page top); the template prints the live title there
    try:
        boxes = json.loads((Path(__file__).parent / "data" / "chapter_titles.json").read_text(encoding="utf-8"))
        ctx["chapter_title_y"] = {k: round(v[1] * 841.9 / 2339 - 2, 1) for k, v in boxes.items() if v}
    except (OSError, ValueError):
        ctx["chapter_title_y"] = {}

    ctx["art"] = {
        "defs": svg.shared_defs(),
        "cover_wheel": svg.cover_wheel(moon), "back_ring": svg.back_ring(moon),
        "mirror": svg.mirror_illustration(moon), "tailpiece": svg.tailpiece(moon),
        "kundali": svg.kundali_emblem(moon), "sign_icon": svg.sign_icon(moon),
        "constellation": svg.constellation(moon),
        "badge_moon": svg.badge(moon, "moon"),
        "badge_sun": svg.badge(sun, "sun") if sun else "",
        "badge_asc": svg.badge(asc, "ascendant"),
        "glyph_moon": svg.sign_icon(moon, 6, svg.GOLD_LIGHT),
        "glyph_sun": svg.sign_icon(sun, 6, svg.GOLD_LIGHT) if sun else "",
        "glyph_asc": svg.sign_icon(asc, 6, svg.GOLD_LIGHT),
        "indicator": {lvl: svg.indicator(lvl, 0.7) for lvl in svg.LEVELS},
        "indicator_small": {lvl: svg.indicator(lvl, 0.36) for lvl in svg.LEVELS},
        "watermark": svg.sign_icon(moon, 60, "#ffffff"),
        "month_strips": [svg.month_strip(i) for i in range(1, 13)],
        "month_ring": svg.month_ring(),
        "moon_emblems": [svg.moon_emblem(i) for i in range(1, 13)],
        "moon_small": [svg.wrap((-11, -11, 22, 22), svg.moon(0, 0, 10, i, 12), cls="moon-small") for i in range(1, 13)],
        "toc_moons": [svg.wrap((-11, -11, 22, 22), svg.moon(0, 0, 10, i + 1, 11, glow=0.3 if i == 10 else 0), cls="moon-small")
                      for i in range(11)],
    }
    return ctx
