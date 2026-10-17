"""Content packs: everything the astrologer writes for one year, as plain JSON.

    content/<year>/
        year.json                    titles, transit calendar, colour swatches
        fixed.json                   disclaimer, letters, rudraksha rules
        overview/mulank<1-9>.json    {moon sign: [paragraphs]}        (year-independent)
        significance/mulank<n>.json  {moon sign: [paragraphs]}
        monthly/<moon sign>.json     {scores, months}
        yearly/<area>.json           {moon sign: {intro, sections}}
        transits/<planet>.json       {ascendant: ...}
        mulank.json                  lucky/unlucky, rudraksha, do's, remedies, affirmation
        gemstones.json               {by_ascendant, stones, process}
        elements.json                {moon sign: element}

A pack may name a parent pack in year.json ("inherits": "2026").  Files missing
from the pack are then read from the parent, so year-independent text does not
have to be copied.  Nothing is ever silently skipped: a missing entry raises
ContentError naming the exact file and key.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .astro import AREAS, MONTHS, SIGNS

CATEGORY_KEYS = [a["key"] for a in AREAS]
YEARLY_FILES = [a["yearly"] for a in AREAS]
MONTHLY_PLANETS = ["venus", "mars", "mercury", "sun"]
ELEMENTS = ["fire", "earth", "air", "water"]


class ContentError(Exception):
    """Raised when the pack cannot supply text a report needs."""


class ContentPack:
    def __init__(self, root: Path | str, year: int | str):
        self.root = Path(root)
        self.year = int(year)
        self.dir = self.root / str(self.year)
        if not (self.dir / "year.json").exists():
            raise ContentError(f"no content pack for {self.year}: {self.dir / 'year.json'} is missing")
        self.meta = self._read(self.dir / "year.json")
        parent = self.meta.get("inherits")
        self.parent = ContentPack(self.root, parent) if parent else None

    # ------------------------------------------------------------------ loading
    @staticmethod
    @lru_cache(maxsize=256)
    def _read_cached(path: str, mtime: float):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def _read(self, path: Path):
        try:
            return self._read_cached(str(path), path.stat().st_mtime)
        except json.JSONDecodeError as exc:
            raise ContentError(f"{path} is not valid JSON: {exc}") from exc

    def find(self, rel: str) -> Path | None:
        """Path of `rel` in this pack or the nearest parent that has it."""
        p = self.dir / rel
        if p.exists():
            return p
        # Only files the pack explicitly lists in "inherit_files" (e.g. ["overview/"]) may come from the
        # parent pack, so last year's year-bound text can never be printed by accident.
        if self.parent and any(rel.startswith(x) for x in self.meta.get("inherit_files", [])):
            return self.parent.find(rel)
        return None

    def load(self, rel: str):
        p = self.find(rel)
        if p is None:
            raise ContentError(f"content file missing for {self.year}: {rel}")
        return self._read(p)

    def source_year(self, rel: str) -> int | None:
        p = self.find(rel)
        return int(p.relative_to(self.root).parts[0]) if p else None

    def get(self, rel: str, *keys, what: str = ""):
        """load(rel)[k1][k2]... with an error message a non-programmer can act on."""
        node = self.load(rel)
        trail = []
        for k in keys:
            trail.append(str(k))
            if not isinstance(node, dict) or str(k) not in node:
                raise ContentError(
                    f"{what or 'content'} missing for {self.year}: {rel} has no entry [{' > '.join(trail)}]")
            node = node[str(k)]
        if node in (None, "", [], {}) or _has_todo(node):
            raise ContentError(f"{what or 'content'} is empty or still TODO for {self.year}: "
                               f"{rel} [{' > '.join(trail)}]")
        return node

    # ------------------------------------------------------------------ validation
    def validate(self) -> tuple[list[str], list[str]]:
        """Check that every customer combination can be served.

        Returns (errors, warnings).  Errors mean some customers cannot get a report.
        """
        errors: list[str] = []
        warnings: list[str] = []

        def need(rel):
            try:
                return self.load(rel)
            except ContentError as exc:
                errors.append(str(exc))
                return None

        def nonempty(value) -> bool:
            if isinstance(value, str):
                return bool(value.strip()) and not _has_todo(value)
            if isinstance(value, list):
                return bool(value) and all(nonempty(v) for v in value)
            return value is not None

        year = str(self.year)
        stale = re.compile(r"\b(20\d\d)\b")

        def check_years(rel, text):
            """Warn when year-bound text mentions a different year than the pack's."""
            if self.source_year(rel) != self.year:
                return
            others = {y for y in stale.findall(json.dumps(text, ensure_ascii=False))
                      if y not in (year, str(self.year + 1), str(self.year - 1))}
            if others:
                warnings.append(f"{rel}: mentions year(s) {sorted(others)} in a {year} pack")

        meta = self.meta
        for key in ("title_hi", "title_en", "chapters", "transits"):
            if key not in meta:
                errors.append(f"year.json: '{key}' is missing")
        for planet in ("jupiter", "saturn", "rahu", "ketu"):
            periods = meta.get("transits", {}).get(planet)
            if not periods:
                errors.append(f"year.json: transits.{planet} is missing")
                continue
            for p in periods:
                if str(p.get("sign", "")).lower() not in SIGNS:
                    errors.append(f"year.json: transits.{planet} has an unknown sign '{p.get('sign')}'")
        if _has_todo(meta):
            errors.append("year.json still contains TODO placeholders")

        for group in ("overview", "significance"):
            for m in range(1, 10):
                d = need(f"{group}/mulank{m}.json")
                if d is None:
                    continue
                for s in SIGNS:
                    if not nonempty(d.get(s)):
                        errors.append(f"{group}/mulank{m}.json: no text for Moon sign '{s}'")
                if group == "significance":
                    check_years(f"{group}/mulank{m}.json", d)

        for s in SIGNS:
            d = need(f"monthly/{s}.json")
            if d is None:
                continue
            for mo in MONTHS:
                month = d.get("months", {}).get(mo, {})
                score = d.get("scores", {}).get(mo, {})
                for c in CATEGORY_KEYS:
                    if not nonempty(month.get(c)):
                        errors.append(f"monthly/{s}.json: no text for {mo} > {c}")
                    v = score.get(c)
                    if not isinstance(v, (int, float)) or not 0 <= v <= 100:
                        errors.append(f"monthly/{s}.json: score for {mo} > {c} must be a number 0-100 (found {v!r})")
            check_years(f"monthly/{s}.json", d.get("months"))

        for a in YEARLY_FILES:
            d = need(f"yearly/{a}.json")
            if d is None:
                continue
            for s in SIGNS:
                e = d.get(s)
                if not e or not (nonempty(e.get("intro")) or e.get("sections")):
                    errors.append(f"yearly/{a}.json: no text for Moon sign '{s}'")
                    continue
                for sec in e.get("sections", []):
                    if not sec.get("hidden") and not nonempty(sec.get("body")):
                        errors.append(f"yearly/{a}.json: [{s}] section '{sec.get('key')}' has no body")
            check_years(f"yearly/{a}.json", d)

        jup = need("transits/jupiter.json")
        for s in SIGNS:
            if jup is not None:
                e = jup.get(s) or {}
                if not e.get("periods"):
                    errors.append(f"transits/jupiter.json: no periods for ascendant '{s}'")
                for p in e.get("periods", []):
                    if not nonempty(p.get("body")):
                        errors.append(f"transits/jupiter.json: [{s}] period '{p.get('heading')}' has no text")
                    if "house" not in p:
                        warnings.append(f"transits/jupiter.json: [{s}] heading not in the form "
                                        f"'January 1 to June 2 — Jupiter in Gemini (4th House)': {p.get('heading')}")
        for planet in ("saturn", "rahu"):
            d = need(f"transits/{planet}.json")
            if d is not None:
                for s in SIGNS:
                    if not nonempty(d.get(s)):
                        errors.append(f"transits/{planet}.json: no text for ascendant '{s}'")
        for planet in MONTHLY_PLANETS:
            d = need(f"transits/{planet}.json")
            if d is None:
                continue
            for s in SIGNS:
                months = [x.get("month") for x in d.get(s, [])]
                if months != MONTHS:
                    errors.append(f"transits/{planet}.json: ascendant '{s}' must have the 12 months in order")
                elif not all(nonempty(x.get("body")) for x in d[s]):
                    errors.append(f"transits/{planet}.json: ascendant '{s}' has an empty month")
        for planet in ("jupiter", "saturn", "rahu", *MONTHLY_PLANETS):
            if self.find(f"transits/{planet}.json"):
                check_years(f"transits/{planet}.json", self.load(f"transits/{planet}.json"))

        mul = need("mulank.json")
        if mul is not None:
            for m in map(str, range(1, 10)):
                e = mul.get(m)
                if not e:
                    errors.append(f"mulank.json: Mulank {m} is missing")
                    continue
                for kind in ("lucky", "unlucky"):
                    k = e.get(kind, {})
                    for f in ("dates", "dates_text", "colours", "colours_text", "day", "day_text"):
                        if not nonempty(k.get(f)):
                            errors.append(f"mulank.json: Mulank {m} > {kind} > {f} is empty")
                    for c in k.get("colours", []):
                        if not self.swatch(c):
                            warnings.append(f"mulank.json: Mulank {m} {kind} colour '{c}' has no swatch in "
                                            f"year.json > colours (a neutral swatch will be drawn)")
                if not e.get("rudraksha", {}).get("beads"):
                    errors.append(f"mulank.json: Mulank {m} has no rudraksha beads")
                for f in ("dos", "donts"):
                    if not nonempty(e.get(f)):
                        errors.append(f"mulank.json: Mulank {m} > {f} is empty")
                for el in ELEMENTS:
                    r = e.get("remedies", {}).get(el, {})
                    if not nonempty(r.get("intro")) or not nonempty(r.get("items")):
                        errors.append(f"mulank.json: Mulank {m} > remedies > {el} is incomplete")
                aff = e.get("affirmation", {})
                for f in ("line", "why", "closing", "light"):
                    if not nonempty(aff.get(f)):
                        errors.append(f"mulank.json: Mulank {m} > affirmation > {f} is empty")
                if not aff.get("ritual", {}).get("rows"):
                    errors.append(f"mulank.json: Mulank {m} > affirmation > ritual has no steps")
            check_years("mulank.json", mul)

        gem = need("gemstones.json")
        if gem is not None:
            for s in SIGNS:
                e = gem.get("by_ascendant", {}).get(s)
                if not e or not e.get("lucky"):
                    errors.append(f"gemstones.json: no lucky stones for ascendant '{s}'")
                    continue
                for g in e["lucky"]:
                    name = gem.get("aliases", {}).get(g, g)
                    if not nonempty(gem.get("stones", {}).get(name)):
                        errors.append(f"gemstones.json: lucky stone '{g}' ({s}) has no description")
            if not nonempty(gem.get("process")):
                errors.append("gemstones.json: 'process' is empty")

        el = need("elements.json")
        if el is not None:
            for s in SIGNS:
                if el.get(s) not in ELEMENTS:
                    errors.append(f"elements.json: Moon sign '{s}' has no element")

        fixed = need("fixed.json")
        if fixed is not None:
            for f in ("disclaimer", "before_you_begin", "chapter1_intro", "letter", "letter_thanks",
                      "consultation", "consultation_url", "rudraksha_remove", "rudraksha_procedure"):
                if not nonempty(fixed.get(f)):
                    errors.append(f"fixed.json: '{f}' is empty")
            check_years("fixed.json", fixed)

        return errors, warnings

    # ------------------------------------------------------------------ small lookups
    def swatch(self, colour_name: str) -> str | None:
        """Hex value for a colour name used in the lucky / unlucky colours."""
        table = {}
        if self.parent:
            table.update({k.lower(): v for k, v in self.parent.meta.get("colours", {}).items()})
        table.update({k.lower(): v for k, v in self.meta.get("colours", {}).items()})
        return table.get(colour_name.strip().lower())


def _walk_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _walk_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_strings(v)


def _has_todo(node) -> bool:
    """True if any text inside `node` is a TODO placeholder (what the pack skeleton writes)."""
    return any(s.strip().upper().startswith("TODO") for s in _walk_strings(node))
