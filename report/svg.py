"""Vector artwork that depends on the customer or the year.

Everything here follows the visual vocabulary of the approved design pack
(report/static/svg): the same golds, glows, tick rings, sparkles and moons.
Static artwork is used as-is from the pack; this module only draws what has to
change per person: sign symbols, constellations, charts, calendars, stones.

All drawings use millimetres as user units and rely on the shared gradient
definitions emitted once per document by `shared_defs()`.
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from html import escape
from pathlib import Path

from .astro import MONTHS, SIGNS

STATIC = Path(__file__).parent / "static" / "svg"
DATA = Path(__file__).parent / "data"

GOLD = "#cfae6e"
GOLD_LIGHT = "#f3dfae"
IVORY = "#ece6d6"
INK = "#191104"
ICE = "#a9bde0"
ASH = "#b7b0a1"
MUTED = "#8e8b88"
NIGHT = "#080b16"

SERIF = "'Poppins', sans-serif"
SANS = "'Poppins', sans-serif"


def n(v: float) -> str:
    """Compact number formatting for SVG attributes."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def wrap(viewbox: tuple[float, float, float, float], inner: str, cls: str = "", title: str = "") -> str:
    x, y, w, h = viewbox
    t = f"<title>{escape(title)}</title>" if title else ""
    c = f' class="{cls}"' if cls else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{n(x)} {n(y)} {n(w)} {n(h)}" '
            f'width="{n(w)}mm" height="{n(h)}mm"{c} aria-hidden="true">{t}{inner}</svg>')


# --------------------------------------------------------------------------- shared definitions
@lru_cache(maxsize=1)
def shared_defs() -> str:
    """One hidden <svg> holding every gradient the pack uses, harvested from the pack itself."""
    seen: dict[str, str] = {}
    pattern = re.compile(r"<(linearGradient|radialGradient)\b[^>]*\bid=\"([^\"]+)\"[^>]*>.*?</\1>", re.S)
    for path in sorted(STATIC.rglob("*.svg")):
        for m in pattern.finditer(path.read_text(encoding="utf-8")):
            seen.setdefault(m.group(2), m.group(0))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0" class="svg-defs" aria-hidden="true">'
            f'<defs>{"".join(seen[k] for k in sorted(seen))}</defs></svg>')


@lru_cache(maxsize=None)
def _static(rel: str) -> tuple[tuple[float, float, float, float], str]:
    """(viewBox, inner markup without <defs>) of a pack file."""
    s = (STATIC / rel).read_text(encoding="utf-8")
    vb = tuple(float(v) for v in re.search(r'viewBox="([^"]+)"', s).group(1).split())
    inner = re.search(r"<svg[^>]*>(.*)</svg>", s, re.S).group(1)
    inner = re.sub(r"<title>.*?</title>|<desc>.*?</desc>|<defs>.*?</defs>", "", inner, flags=re.S).strip()
    return vb, inner


# --------------------------------------------------------------------------- primitives
def ticks(cx, cy, r, count, minor, major=None, major_every=0, inward=False) -> str:
    """Path data for a dial of radial ticks starting at radius r."""
    d = []
    sgn = -1 if inward else 1
    for i in range(count):
        a = 2 * math.pi * i / count
        ln = major if (major_every and i % major_every == 0) else minor
        s, c = math.sin(a), -math.cos(a)
        d.append(f"M{n(cx + r * s)},{n(cy + r * c)}L{n(cx + (r + sgn * ln) * s)},{n(cy + (r + sgn * ln) * c)}")
    return " ".join(d)


def sparkle_path(cx, cy, r) -> str:
    k = r * 0.1125
    return (f"M{n(cx)},{n(cy - r)} Q{n(cx + k)},{n(cy - k)} {n(cx + r)},{n(cy)} "
            f"Q{n(cx + k)},{n(cy + k)} {n(cx)},{n(cy + r)} Q{n(cx - k)},{n(cy + k)} {n(cx - r)},{n(cy)} "
            f"Q{n(cx - k)},{n(cy - k)} {n(cx)},{n(cy - r)}Z")


def star(cx, cy, size: str = "mid", k: float = 1.0) -> str:
    """A glowing star: 'bright' is a four-point sparkle, 'mid'/'small' are dots."""
    if size == "bright":
        return (f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(6.2 * k)}" fill="url(#rStar)"/>'
                f'<path d="{sparkle_path(cx, cy, 1.95 * k)}" fill="{IVORY}"/>')
    glow, dot = (1.5, 0.34) if size == "mid" else (0.9, 0.2)
    return (f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(glow * k)}" fill="url(#rStar)"/>'
            f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(dot * k)}" fill="{IVORY}"/>')


def moon(cx, cy, r, step: int, of: int = 12, glow: float = 0.0) -> str:
    """Moon phase `step` of `of` (1 = thin crescent ... of = full), gold on a dark disc."""
    f = max(0.0, min(1.0, step / of))
    rx = r * abs(1 - 2 * f)
    sweep = 0 if f < 0.5 else 1
    out = ""
    if glow:
        out += f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r * 2.1)}" fill="url(#rGoldGlow)" opacity="{n(glow)}"/>'
    out += f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="#090c17"/>'
    if f >= 0.999:
        out += f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="url(#gGold)"/>'
    else:
        out += (f'<path d="M{n(cx)},{n(cy - r)} A{n(r)},{n(r)} 0 0 1 {n(cx)},{n(cy + r)} '
                f'A{n(rx)},{n(r)} 0 0 {sweep} {n(cx)},{n(cy - r)}Z" fill="url(#gGold)"/>')
    out += (f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="none" stroke="{GOLD}" '
            f'stroke-width="{n(r * 0.035)}" opacity="0.55"/>')
    return out


def text(x, y, s, size, family=SERIF, fill=IVORY, anchor="start", weight=None, style=None,
         spacing=None, opacity=None) -> str:
    a = [f'x="{n(x)}"', f'y="{n(y)}"', f'font-family="{family}"', f'font-size="{n(size)}"', f'fill="{fill}"']
    if anchor != "start":
        a.append(f'text-anchor="{anchor}"')
    if weight:
        a.append(f'font-weight="{weight}"')
    if style:
        a.append(f'font-style="{style}"')
    if spacing:
        a.append(f'letter-spacing="{n(spacing)}"')
    if opacity is not None:
        a.append(f'opacity="{n(opacity)}"')
    return f"<text {' '.join(a)}>{escape(str(s))}</text>"


PT = 25.4 / 72  # one point in millimetres


# --------------------------------------------------------------------------- zodiac symbols
_GLYPH_UNITS = 17.0          # drawn size (in 1/20 em) of the longest side of a glyph
@lru_cache(maxsize=None)
def _symbol(sign: str) -> tuple[str, float, float, float]:
    """(path data, bbox centre x, bbox centre y) of a sign glyph; glyph units are 1/20 em."""
    s = (STATIC / "zodiac" / f"{sign}_zodiac_symbol.svg").read_text(encoding="utf-8")
    x, y, w, h = (float(v) for v in re.search(r'viewBox="([^"]+)"', s).group(1).split())
    d = re.search(r'<path\b[^>]*?\sd="([^"]+)"', s).group(1)
    norm = _GLYPH_UNITS / max(w - 12, h - 12, 1.0) if "viewBox" in s and w > 60 else 1.0   # the 2027 artwork is ~330 units wide
    return d, x + w / 2, y + h / 2, norm


def symbol(sign: str, cx, cy, em: float, fill: str = GOLD_LIGHT, opacity: float | None = None) -> str:
    """Sign glyph centred on (cx, cy); `em` is the type size in mm."""
    d, bx, by, norm = _symbol(sign)
    k = em / 20 * norm
    op = f' opacity="{n(opacity)}"' if opacity is not None else ""
    return (f'<path transform="translate({n(cx - bx * k)},{n(cy - by * k)}) scale({n(k) if k >= 0.01 else k})" '
            f'd="{d}" fill="{fill}" fill-rule="evenodd"{op}/>')


def sign_icon(sign: str, em: float = 3.2, fill: str = GOLD) -> str:
    """Small standalone glyph (running head)."""
    d, bx, by, norm = _symbol(sign)
    half = 9.2 / norm
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{n(bx - half)} {n(by - half)} {n(2 * half)} {n(2 * half)}" '
            f'width="{n(em * 0.92)}mm" height="{n(em * 0.92)}mm" class="sign-icon" aria-hidden="true">'
            f'<path d="{d}" fill="{fill}" fill-rule="evenodd"/></svg>')


def medallion(cx, cy, r, sign: str, glow: bool = True) -> str:
    out = ""
    if glow:
        out += f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r * 1.9)}" fill="url(#rGoldGlow)" opacity="0.35"/>'
    out += (f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="{NIGHT}" stroke="url(#gGold)" stroke-width="{n(r * 0.03)}"/>'
            f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r * 0.86)}" fill="none" stroke="{GOLD}" stroke-width="{n(r * 0.012)}" '
            f'opacity="0.4" stroke-dasharray="{n(r * 0.02)} {n(r * 0.09)}"/>')
    out += symbol(sign, cx, cy, r * 1.04)
    return out


# --------------------------------------------------------------------------- constellations
@lru_cache(maxsize=1)
def _constellations() -> dict:
    return json.loads((DATA / "constellations.json").read_text(encoding="utf-8"))


def constellation_group(sign: str, cx, cy, box_w, box_h, line_w: float = 0.16) -> str:
    """Stick figure of the sign's constellation fitted inside box_w x box_h, centred on (cx, cy)."""
    c = _constellations()[sign]
    scale = min(box_w / c["w"], box_h / c["h"])
    k = max(0.42, min(1.05, scale / 78))          # star size follows the drawn size
    pts = [(cx + s["x"] * scale, cy + s["y"] * scale, s["size"]) for s in c["stars"]]
    gap = 1.25 * k
    out = []
    for a, b in c["lines"]:
        x1, y1, _ = pts[a]
        x2, y2, _ = pts[b]
        length = math.hypot(x2 - x1, y2 - y1)
        if length <= 2 * gap + 0.05:
            continue
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        out.append(f'<line x1="{n(x1 + ux * gap)}" y1="{n(y1 + uy * gap)}" x2="{n(x2 - ux * gap)}" y2="{n(y2 - uy * gap)}" '
                   f'stroke="{GOLD_LIGHT}" stroke-width="{n(line_w)}" opacity="0.75" stroke-linecap="round"/>')
    for x, y, size in pts:
        out.append(star(x, y, size, k))
    return "".join(out)


def constellation(sign: str, w: float = 82, h: float = 52) -> str:
    """Standalone constellation drawing (profile card)."""
    pad = 7
    return wrap((-w / 2 - pad, -h / 2 - pad, w + 2 * pad, h + 2 * pad),
                constellation_group(sign, 0, 0, w, h), cls="constellation", title=f"{sign.title()} constellation")


# --------------------------------------------------------------------------- frames that carry the Moon sign
def _strip(inner: str, *patterns: str) -> str:
    for p in patterns:
        inner = re.sub(p, "", inner, flags=re.S)
    return inner


_SYMBOL_PATH = r'<path d="[^"]+" fill="#f3dfae"/>'            # the Aquarius glyph in the supplied files
_RING_SYMBOL = r'<path d="[^"]+" fill="#cfae6e" opacity="0.62"/>'
_CONST_LINE = r'<line [^>]*stroke="#f3dfae"[^>]*/>'


def cover_wheel(moon_sign: str) -> str:
    """Cover ring: the Moon sign in the top medallion, the other eleven following clockwise."""
    vb, inner = _static("celestial_frames/cover_zodiac_wheel_frame.svg")
    inner = _strip(inner, _RING_SYMBOL, _SYMBOL_PATH)
    cx, cy, r = 105, 121, 66.9
    start = SIGNS.index(moon_sign)
    for i in range(1, 12):
        a = math.radians(30 * i)
        inner += symbol(SIGNS[(start + i) % 12], cx + r * math.sin(a), cy - r * math.cos(a), 9.4 * PT, GOLD, 0.62)
    inner += symbol(moon_sign, 105, 54.1, 16.7 * PT)
    inner += constellation_group(moon_sign, 91, 124, 56, 54)
    return wrap(vb, inner, cls="art cover-wheel")


def back_ring(moon_sign: str) -> str:
    vb, inner = _static("celestial_frames/back_cover_ring_frame.svg")
    inner = _strip(inner, _SYMBOL_PATH)
    inner += symbol(moon_sign, 105, 48, 15.9 * PT)
    inner += constellation_group(moon_sign, 105, 107, 84, 64, line_w=0.18)
    return wrap(vb, inner, cls="art back-ring")


def mirror_illustration(moon_sign: str) -> str:
    """Chapter 01 art: the oval mirror with the customer's constellation inside."""
    vb, inner = _static("decorative_elements/chapter_01_mirror_illustration.svg")
    inner = _strip(inner, _CONST_LINE)

    def keep(m):  # drop the stars that belong to the constellation (inside the glass), keep frame stars
        cx, cy = float(m.group(1)), float(m.group(2))
        inside = ((cx - 105) / 27.5) ** 2 + ((cy - 110) / 40.5) ** 2 < 1
        return "" if inside else m.group(0)

    inner = re.sub(r'<g opacity="[^"]*"><circle cx="([-\d.]+)" cy="([-\d.]+)" r="[-\d.]+" fill="url\(#rStar\)"/>.*?</g>',
                   keep, inner, flags=re.S)
    inner += constellation_group(moon_sign, 105, 113, 41, 54, line_w=0.14)
    return wrap(vb, inner, cls="art mirror")


def tailpiece(moon_sign: str) -> str:
    """Moon-phase divider with the Moon sign in the centre medallion."""
    vb, inner = _static("dividers/moon_phase_tailpiece_divider.svg")
    inner = _strip(inner, _SYMBOL_PATH)
    return wrap(vb, inner + symbol(moon_sign, 66, 17, 24.4 * PT), cls="tailpiece")


def kundali_emblem(moon_sign: str) -> str:
    """Profile page chart emblem with the Moon sign at the centre."""
    vb, inner = _static("charts/kundali_chart_emblem_aquarius.svg")
    inner = _strip(inner, _SYMBOL_PATH)
    return wrap(vb, inner + symbol(moon_sign, 28, 28, 15.2 * PT), cls="kundali-emblem")


def badge(sign: str, kind: str) -> str:
    """Sign badge for the profile cards. kind: moon | sun | ascendant (sets the small marker)."""
    src = {"moon": "zodiac/moon_sign_aquarius_badge.svg", "sun": "zodiac/sun_sign_capricorn_badge.svg",
           "ascendant": "zodiac/ascendant_pisces_badge.svg"}[kind]
    vb, inner = _static(src)
    inner = re.sub(_SYMBOL_PATH, "", inner, count=1, flags=re.S)   # first light-gold path is the glyph
    return wrap(vb, inner + symbol(sign, 12, 12, 26.6 * PT), cls="badge")


# --------------------------------------------------------------------------- status visuals
LEVELS = ("best", "good", "average")


def level_of(score: float) -> str:
    """Score (0-100) to the three printed levels; thresholds are the 2026 report's."""
    return "best" if score >= 80 else ("good" if score >= 75 else "average")


def indicator(level: str, unit: float = 0.56) -> str:
    """Best = glowing gold disc, Good = half-lit ice disc, Average = hollow ring."""
    if level == "best":
        inner = ('<circle cx="5" cy="5" r="7.92" fill="url(#rGoldGlow)" opacity="0.8"/>'
                 '<circle cx="5" cy="5" r="3.6" fill="url(#gGold)"/>')
    elif level == "good":
        inner = (f'<circle cx="5" cy="5" r="3.02" fill="#0b1020" stroke="{ICE}" stroke-width="0.468"/>'
                 '<path d="M5,1.98 A3.02,3.02 0 0 1 5,8.02Z" fill="url(#gIce)"/>')
    else:
        inner = '<circle cx="5" cy="5" r="2.23" fill="none" stroke="#8a8478" stroke-width="0.468"/>'
    size = 16 * unit
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-3 -3 16 16" width="{n(size)}mm" height="{n(size)}mm" '
            f'class="indicator indicator-{level}" aria-hidden="true">{inner}</svg>')


def radar(center_label: str, areas: list[dict]) -> str:
    """Monthly status map: eight axes, three rings.  areas = [{label, level}] in report order."""
    cx, cy, R = 83.0, 64.0, 43.0
    radius = {"best": R, "good": R * 2 / 3, "average": R / 3}
    node_fill = {"best": GOLD_LIGHT, "good": ICE, "average": ASH}
    word = {"best": "Best", "good": "Good", "average": "Average"}
    o = [f'<circle cx="{n(cx)}" cy="{n(cy)}" r="64.5" fill="url(#rGoldGlow)" opacity="0.32"/>',
         f'<circle cx="{n(cx)}" cy="{n(cy)}" r="48" fill="none" stroke="{GOLD}" stroke-width="0.09" opacity="0.45" stroke-dasharray="0.25 1.2"/>',
         f'<path d="{ticks(cx, cy, 48, 96, 0.7, 1.6, 12)}" fill="none" stroke="{GOLD}" stroke-width="0.08" opacity="0.45" stroke-linecap="round"/>',
         f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(R / 3)}" fill="none" stroke="{GOLD}" stroke-width="0.09" opacity="0.4"/>',
         f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(R * 2 / 3)}" fill="none" stroke="{GOLD}" stroke-width="0.09" opacity="0.4"/>',
         f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(R)}" fill="#070a14" stroke="{GOLD}" stroke-width="0.14" opacity="0.75" fill-opacity="0.55"/>']
    pts = []
    for i, a in enumerate(areas):
        ang = math.radians(45 * i)
        s, c = math.sin(ang), -math.cos(ang)
        o.append(f'<line x1="{n(cx)}" y1="{n(cy)}" x2="{n(cx + R * s)}" y2="{n(cy + R * c)}" stroke="{GOLD}" stroke-width="0.08" opacity="0.35"/>')
        r = radius[a["level"]]
        pts.append((cx + r * s, cy + r * c))
    poly = " L".join(f"{n(x)},{n(y)}" for x, y in pts)
    o.append(f'<path d="M{poly}Z" fill="url(#gGoldFill)" opacity="0.24"/>')
    o.append(f'<path d="M{poly}Z" fill="none" stroke="url(#gGold)" stroke-width="0.36" stroke-linejoin="round"/>')
    # ring captions, set along a line 22 degrees right of vertical
    ang = math.radians(22)
    for lvl in ("average", "good", "best"):
        rr = radius[lvl] - 2.15
        o.append(text(cx + rr * math.sin(ang), cy - rr * math.cos(ang) + 0.05, lvl.upper(), 3.8 * PT, SANS, MUTED,
                      "middle", 500, spacing=3.8 * PT * 0.3))
    for (x, y), a in zip(pts, areas):
        lvl = a["level"]
        glow = "rGoldGlow" if lvl == "best" else "rIceGlow"
        o.append(f'<circle cx="{n(x)}" cy="{n(y)}" r="3.4" fill="url(#{glow})" opacity="{0.3 if lvl == "average" else 0.9}"/>')
        o.append(f'<circle cx="{n(x)}" cy="{n(y)}" r="1.25" fill="{node_fill[lvl]}" stroke="#070a14" stroke-width="0.3"/>')
    o.append(f'<circle cx="{n(cx)}" cy="{n(cy)}" r="7.4" fill="#070a14" stroke="url(#gGold)" stroke-width="0.2"/>')
    o.append(text(cx, cy + 1.7, center_label, 15.9 * PT, SERIF, IVORY, "middle", 500))
    # outer labels: (anchor, x, y of area caption); status word sits 4 mm below
    spots = [("middle", cx, 8.1), ("start", cx + 37.8, 25.95), ("start", cx + 53.5, 63.8), ("start", cx + 37.8, 101.6),
             ("middle", cx, 118.9), ("end", cx - 37.8, 101.6), ("end", cx - 53.5, 63.8), ("end", cx - 37.8, 25.95)]
    cap, sp = 5.5 * PT, 5.5 * PT * 0.285
    pitch = 3.1                                   # mm between the lines of a two-line caption
    for (anchor, x, y), a in zip(spots, areas):
        lines = _wrap_caption(a["label"].upper(), 20)
        # letter-spacing adds a trailing gap; nudge end/middle anchors so text stays optically aligned
        nudge = sp if anchor == "end" else (sp / 2 if anchor == "middle" else 0)
        half = (len(lines) - 1) / 2
        for j, ln in enumerate(lines):
            o.append(text(x + nudge, y + (j - half) * pitch, ln, cap, SANS, IVORY, anchor, 500, spacing=sp, opacity=0.9))
        o.append(text(x, y + 4.0 + half * pitch, word[a["level"]], 9.9 * PT, SERIF, node_fill[a["level"]], anchor, style="italic"))
    return wrap((-1.654, -1, 169.3, 130), "".join(o), cls="radar")


def _wrap_caption(s: str, width: int) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + [cur] if cur else lines


# --------------------------------------------------------------------------- Jupiter timeline
_MONTH_INDEX = {m: i for i, m in enumerate(MONTHS)}
_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _year_fraction_x(when: str) -> float:
    """'June 2' or '06-02' -> x on the 12-month track (5 .. 161, 13 mm per month)."""
    m = re.fullmatch(r"\s*([A-Za-z]+)\s+(\d{1,2})\s*", when) or None
    if m:
        mi, day = _MONTH_INDEX[m.group(1).lower()], int(m.group(2))
    else:
        mm = re.fullmatch(r"\s*(\d{1,2})-(\d{1,2})\s*", when)
        mi, day = int(mm.group(1)) - 1, int(mm.group(2))
    return 5 + 13 * (mi + (day - 1) / _DAYS[mi])


def timeline(periods: list[dict]) -> str:
    """Year track split into dated periods.  periods = [{from, to, label}], in order."""
    xs = [_year_fraction_x(p["from"]) for p in periods]
    ends = xs[1:] + [161.0]
    xs[0] = 5.0
    o = [f'<rect x="5" y="20.1" width="156" height="1.8" rx="0.9" fill="#0b0f1d" stroke="{GOLD}" stroke-width="0.1" stroke-opacity="0.5"/>']
    for i, (x0, x1) in enumerate(zip(xs, ends)):
        op = max(0.3, 0.95 - 0.31 * i)
        o.append(f'<rect x="{n(x0)}" y="20.1" width="{n(x1 - x0)}" height="1.8" rx="0.9" fill="url(#gGoldFill)" opacity="{n(op)}"/>')
    for i in range(13):
        x = 5 + 13 * i
        o.append(f'<line x1="{n(x)}" y1="23.2" x2="{n(x)}" y2="24.6" stroke="{GOLD}" stroke-width="0.1" opacity="0.5"/>')
        if i < 12:
            o.append(text(x + 6.5, 28.2, MONTHS[i][:3].upper(), 5.0 * PT, SANS, MUTED, "middle", 500, spacing=5.0 * PT * 0.3))
    # labels: left-aligned just after their start, pulled back inside the track, staggered if they collide
    size = 10.6 * PT
    placed, top = [], 11.4
    for x0, p in zip(xs, periods):
        width = len(p["label"]) * 1.52
        lx = min(x0 + 2.4, 161 - width)
        row = 0
        if placed and lx < placed[-1][0] + placed[-1][1] + 2 and placed[-1][2] == 0:
            row = 1
        placed.append((lx, width, row))
        y = 15.0 - row * 5.2
        top = min(top, y - 4.0)
        o.append(text(lx, y, p["label"], size, SERIF, IVORY, weight=500))
        o.append(f'<line x1="{n(x0)}" y1="{n(16.4 - row * 5.2)}" x2="{n(x0)}" y2="19.4" stroke="{GOLD}" stroke-width="0.12" opacity="0.7"/>')
    for x in xs + [161.0]:
        o.append(f'<circle cx="{n(x)}" cy="21" r="3.4" fill="url(#rGoldGlow)" opacity="0.8"/>'
                 f'<circle cx="{n(x)}" cy="21" r="1.45" fill="#070a14" stroke="{GOLD_LIGHT}" stroke-width="0.3"/>')
    return wrap((1.1, top, 163.8, 28.72 - top), "".join(o), cls="timeline")


# --------------------------------------------------------------------------- kundali house chart
_HOUSES = {
    1: [(25, 3), (36, 14), (25, 25), (14, 14)], 2: [(3, 3), (25, 3), (14, 14)], 3: [(3, 3), (14, 14), (3, 25)],
    4: [(3, 25), (14, 14), (25, 25), (14, 36)], 5: [(3, 25), (14, 36), (3, 47)], 6: [(3, 47), (14, 36), (25, 47)],
    7: [(25, 47), (36, 36), (25, 25), (14, 36)], 8: [(25, 47), (36, 36), (47, 47)], 9: [(47, 47), (36, 36), (47, 25)],
    10: [(47, 25), (36, 36), (25, 25), (36, 14)], 11: [(47, 25), (36, 14), (47, 3)], 12: [(47, 3), (36, 14), (25, 3)],
}


def kundali_houses(active: list[int]) -> str:
    """North-Indian chart with the given houses lit (houses counted from the ascendant)."""
    act = set(active)
    path = lambda pts: "M" + " L".join(f"{x},{y}" for x, y in pts) + "Z"
    o = ['<circle cx="25" cy="25" r="37.84" fill="url(#rGoldGlow)" opacity="0.22"/>',
         '<rect x="3" y="3" width="44" height="44" fill="#070a14" fill-opacity="0.85"/>']
    for h in sorted(act):
        o.append(f'<path d="{path(_HOUSES[h])}" fill="url(#gGoldFill)" opacity="0.9"/>')
    for h in range(1, 13):
        o.append(f'<path d="{path(_HOUSES[h])}" fill="none" stroke="{GOLD}" stroke-width="0.176" opacity="0.75" stroke-linejoin="round"/>')
    o.append('<rect x="3" y="3" width="44" height="44" fill="none" stroke="url(#gGold)" stroke-width="0.53"/>')
    o.append(f'<rect x="1.46" y="1.46" width="47.08" height="47.08" fill="none" stroke="{GOLD}" stroke-width="0.13" opacity="0.5"/>')
    for h in range(1, 13):
        pts = _HOUSES[h]
        cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        if h in act:
            o.append(text(cx, cy + 1.45, h, 4.3, SERIF, INK, "middle", 600))
        else:
            o.append(text(cx, cy + 1.0, h, 3.0, SERIF, GOLD, "middle", 500, opacity=0.6))
    return wrap((-1.5, -1.5, 53, 53), "".join(o), cls="kundali")


# --------------------------------------------------------------------------- lucky / unlucky visuals
def calendar(dates: list[int], lucky: bool = True) -> str:
    """31-day grid with the given dates marked: glowing gold (lucky) or struck through (unlucky)."""
    mark = set(dates)
    o = []
    for d in range(1, 32):
        cx, cy = 6 + 8 * ((d - 1) % 7), 5 + 8 * ((d - 1) // 7)
        if d in mark and lucky:
            o.append(f'<circle cx="{cx}" cy="{cy}" r="5.4" fill="url(#rGoldGlow)" opacity="0.9"/>'
                     f'<circle cx="{cx}" cy="{cy}" r="3.3" fill="url(#gGold)"/>')
            o.append(text(cx, cy + 1.0, d, 2.9, SERIF, INK, "middle", 600))
        elif d in mark:
            o.append(f'<circle cx="{cx}" cy="{cy}" r="3.3" fill="#05060c" stroke="{ASH}" stroke-width="0.24"/>')
            o.append(text(cx, cy + 1.0, d, 2.9, SERIF, "#d6d1c4", "middle", 500))
            o.append(f'<line x1="{n(cx - 2.6)}" y1="{n(cy + 2.6)}" x2="{n(cx + 2.6)}" y2="{n(cy - 2.6)}" stroke="{ASH}" stroke-width="0.22" opacity="0.85"/>')
        else:
            o.append(f'<circle cx="{cx}" cy="{cy}" r="3.1" fill="none" stroke="{GOLD}" stroke-width="0.08" opacity="0.3"/>')
            o.append(text(cx, cy + 0.85, d, 2.45, SERIF, GOLD, "middle", 500, opacity=0.7))
    return wrap((0.2, -0.8, 59.6, 41.3), "".join(o), cls="calendar")


def swatches(colours: list[str | None], lucky: bool = True) -> str:
    """Overlapping colour spheres.  None draws a neutral sphere (colour name without a swatch)."""
    count = max(1, len(colours))
    step = 12.5
    x0 = 30 - step * (count - 1) / 2
    o = []
    for i, hexv in enumerate(colours):
        cx = x0 + i * step
        if lucky:
            o.append(f'<circle cx="{n(cx)}" cy="20" r="11.5" fill="url(#rGoldGlow)" opacity="0.4"/>')
        o.append(f'<circle cx="{n(cx)}" cy="20" r="9.2" fill="{hexv or "#2a2f45"}"/>'
                 f'<circle cx="{n(cx)}" cy="20" r="9.2" fill="url(#rShade)" opacity="0.8"/>'
                 f'<circle cx="{n(cx)}" cy="20" r="9.2" fill="none" stroke="{"url(#gGold)" if lucky else "#8a8478"}" stroke-width="0.24"/>')
    if not lucky:
        o.append(f'<line x1="{n(x0 - 8.3)}" y1="33" x2="{n(x0 + (count - 1) * step + 8.3)}" y2="7" stroke="{ASH}" stroke-width="0.2" opacity="0.7"/>')
    half = step * (count - 1) / 2 + 12.3
    return wrap((30 - half, 7.5, 2 * half, 25), "".join(o), cls="swatches")


_DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_PLANET_GRAD = {"sun": "rSun", "mars": "rMars", "mercury": "rMerc", "jupiter": "rJup", "venus": "rVen", "saturn": "rSat"}


def _planet_dot(planet: str, cx, cy, r) -> str:
    if planet == "moon":
        return moon(cx, cy, r, 4, 10)
    o = ""
    if planet == "saturn":
        o += (f'<g transform="rotate(-18 {n(cx)} {n(cy)})"><path d="M{n(cx - r * 2.05)},{n(cy)} A{n(r * 2.05)},{n(r * 0.55)} 0 0 1 {n(cx + r * 2.05)},{n(cy)}" '
              f'fill="none" stroke="url(#gGold)" stroke-width="{n(r * 0.16)}" opacity="0.55"/></g>')
    o += f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="url(#{_PLANET_GRAD[planet]})"/>'
    if planet == "sun":
        o += f'<path d="{ticks(cx, cy, r * 1.25, 16, r * 0.45)}" fill="none" stroke="{GOLD_LIGHT}" stroke-width="{n(r * 0.07)}" opacity="0.8" stroke-linecap="round"/>'
    else:
        o += f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="url(#rShade)"/>'
    if planet == "saturn":
        o += (f'<g transform="rotate(-18 {n(cx)} {n(cy)})"><path d="M{n(cx - r * 2.05)},{n(cy)} A{n(r * 2.05)},{n(r * 0.55)} 0 0 0 {n(cx + r * 2.05)},{n(cy)}" '
              f'fill="none" stroke="url(#gGold)" stroke-width="{n(r * 0.16)}"/></g>')
    return o


def week_ring(day: str, planet: str, lucky: bool = True) -> str:
    """Seven-day ring (Monday at the top) with one day marked and its ruling planet at the centre."""
    day = day.strip().lower()
    line = GOLD if lucky else "#8a8478"
    o = [f'<circle cx="30" cy="21" r="15.5" fill="none" stroke="{line}" stroke-width="0.12" opacity="0.6"/>',
         f'<circle cx="30" cy="21" r="8.4" fill="none" stroke="{line}" stroke-width="0.09" opacity="0.4" stroke-dasharray="0.25 1"/>']
    for i, d in enumerate(_DAY_ORDER):
        a = 2 * math.pi * i / 7
        cx, cy = 30 + 15.5 * math.sin(a), 21 - 15.5 * math.cos(a)
        label = d[:2].title()
        if d == day and lucky:
            o.append(f'<circle cx="{n(cx)}" cy="{n(cy)}" r="5.6" fill="url(#rGoldGlow)" opacity="0.9"/>'
                     f'<circle cx="{n(cx)}" cy="{n(cy)}" r="3.5" fill="url(#gGold)"/>')
            o.append(text(cx, cy + 0.95, label, 2.7, SERIF, INK, "middle", 600))
        elif d == day:
            o.append(f'<circle cx="{n(cx)}" cy="{n(cy)}" r="3.5" fill="#05060c" stroke="{ASH}" stroke-width="0.24"/>')
            o.append(text(cx, cy + 0.95, label, 2.7, SERIF, "#d6d1c4", "middle", 500))
        else:
            o.append(f'<circle cx="{n(cx)}" cy="{n(cy)}" r="2.6" fill="{NIGHT}" stroke="{GOLD}" stroke-width="0.1" opacity="0.8"/>')
            o.append(text(cx, cy + 0.7, label, 2.0, SERIF, GOLD, "middle", 500, opacity=0.6))
    o.append(f'<circle cx="30" cy="21" r="9.2" fill="url(#rGoldGlow)" opacity="{0.42 if lucky else 0.3}"/>')
    o.append(_planet_dot(planet, 30, 21, 4.4 if planet in ("moon", "sun") else 3.4))
    return wrap((8.5, -0.8, 43, 43.6), "".join(o), cls="week-ring")


# --------------------------------------------------------------------------- rudraksha
def _bead(cx, cy, mukhi: int, r: float = 10.5) -> str:
    """Rudraksha bead with `mukhi` face lines (as the pack draws 9 and 10 mukhi)."""
    o = [f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r * 1.7)}" fill="url(#rGoldGlow)" opacity="0.3"/>',
         f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="url(#rRud)"/>']
    pairs = mukhi // 2
    odd = mukhi % 2 == 1
    sw = r * 0.055 * (1.0 if mukhi <= 10 else 0.8)
    for i in range(1, pairs + 1):
        rx = r * i / (pairs + 0.6)
        o.append(f'<ellipse cx="{n(cx)}" cy="{n(cy)}" rx="{n(rx)}" ry="{n(r)}" fill="none" stroke="#2a1608" stroke-width="{n(sw)}" opacity="0.75"/>')
        o.append(f'<ellipse cx="{n(cx + r * 0.03)}" cy="{n(cy)}" rx="{n(rx)}" ry="{n(r)}" fill="none" stroke="#e0a56a" stroke-width="{n(sw * 0.33)}" opacity="0.35"/>')
    if odd:
        o.append(f'<line x1="{n(cx)}" y1="{n(cy - r)}" x2="{n(cx)}" y2="{n(cy + r)}" stroke="#2a1608" stroke-width="{n(sw)}" opacity="0.75"/>')
    o.append(f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="url(#rShade)"/>')
    o.append(f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="none" stroke="url(#gGold)" stroke-width="{n(r * 0.035)}" opacity="0.7"/>')
    o.append(f'<ellipse cx="{n(cx)}" cy="{n(cy - r * 0.98)}" rx="{n(r * 0.12)}" ry="{n(r * 0.06)}" fill="#1a0d05"/>')
    return "".join(o)


def rudraksha_emblem(mukhi: int) -> str:
    vb, ring = _static("celestial_frames/section_emblem_ring_empty.svg")
    return wrap(vb, ring + _bead(17, 17, mukhi, 8.2).replace('opacity="0.3"/>', 'opacity="0.0"/>', 1), cls="emblem-svg")


def rudraksha_group(beads: list[int]) -> str:
    """The recommended beads on a gold thread, each captioned with its mukhi count."""
    count = len(beads)
    r = 10.5 if count <= 2 else (8.4 if count == 3 else 7.0)
    step = r * 2.2
    x0 = 30 - step * (count - 1) / 2
    o = ['<circle cx="30" cy="22" r="26" fill="url(#rGoldGlow)" opacity="0.35"/>',
         f'<path d="M2,10 Q30,-2 58,10" fill="none" stroke="{GOLD}" stroke-width="0.3" opacity="0.7"/>']
    for i, m in enumerate(beads):
        cx = x0 + i * step
        o.append(_bead(cx, 23, m, r))
        o.append(text(cx + 0.55, 23 + r + 6.6, f"{m} MUKHI", 4.4 * PT, SANS, MUTED, "middle", 500, spacing=4.4 * PT * 0.3))
    return wrap((0.15, -4.5, 59.7, 46), "".join(o), cls="rudraksha")


# --------------------------------------------------------------------------- gemstones
_FACETED = {  # base, edge highlight, mid shade, deep shade
    "yellow sapphire": ("#f6cf45", "#fff3b0", "#d79a12", "#8f5d06"),
    "blue sapphire": ("#4d7fe0", "#cfe0ff", "#1f3fa0", "#0f1f5c"),
    "hessonite": ("#c8752a", "#ffd9a8", "#8f4a14", "#4f2607"),
    "emerald": ("#2fae6e", "#c9f5dc", "#14804a", "#0a4a2a"),
    "ruby": ("#e0304a", "#ffc9d2", "#a3122a", "#5c0716"),
    "diamond": ("#eef4fb", "#ffffff", "#bcd0e6", "#8497b0"),
}
_GEM_ALIASES = {"green emerald": "emerald", "pukhraj": "yellow sapphire", "neelam": "blue sapphire",
                "gomed": "hessonite", "panna": "emerald", "manik": "ruby", "heera": "diamond",
                "moti": "pearl", "moonga": "red coral", "coral": "red coral", "cat’s eye": "cats eye",
                "cat's eye": "cats eye", "lehsunia": "cats eye"}


def gem_slug(name: str) -> str:
    """File name (without .png) of the stone picture in static/img/gems."""
    return gem_key(name).replace(" ", "_")


def gem_key(name: str) -> str:
    k = name.strip().lower()
    return _GEM_ALIASES.get(k, k)


def _gem(name: str, k: float = 1.0) -> str:
    """Stone drawing centred on the origin, about 29*k mm across."""
    key = gem_key(name)
    if key == "pearl":
        return (f'<circle r="{n(13 * k)}" fill="url(#rPearl)"/>'
                f'<ellipse cx="{n(-4.16 * k)}" cy="{n(-4.94 * k)}" rx="{n(2.86 * k)}" ry="{n(1.69 * k)}" fill="#fff" opacity="0.85" '
                f'transform="rotate(-35 {n(-4.16 * k)} {n(-4.94 * k)})"/>'
                f'<circle r="{n(13 * k)}" fill="none" stroke="url(#gGold)" stroke-width="{n(0.52 * k)}" opacity="0.8"/>')
    if key in ("red coral", "cats eye"):
        body = "url(#rCoral)" if key == "red coral" else "#a89a3a"
        o = f'<ellipse rx="{n(11.31 * k)}" ry="{n(14.5 * k)}" fill="{body}"/>'
        if key == "cats eye":
            o += (f'<ellipse rx="{n(11.31 * k)}" ry="{n(14.5 * k)}" fill="url(#rShade)"/>'
                  f'<ellipse rx="{n(1.1 * k)}" ry="{n(12.4 * k)}" fill="#fff8d0" opacity="0.8"/>')
        else:
            o += (f'<ellipse cx="{n(-3.48 * k)}" cy="{n(-6.09 * k)}" rx="{n(2.03 * k)}" ry="{n(4.35 * k)}" fill="#ffd9c8" opacity="0.7" '
                  f'transform="rotate(20 {n(-3.48 * k)} {n(-6.09 * k)})"/>')
        return o + f'<ellipse rx="{n(11.31 * k)}" ry="{n(14.5 * k)}" fill="none" stroke="url(#gGold)" stroke-width="{n(0.65 * k)}"/>'
    base, edge, mid, deep = _FACETED.get(key, ("#c9c9d6", "#ffffff", "#9a9aae", "#5e5e72"))
    A, B, C, D = 13.4 * k, 5.55 * k, 7.5 * k, 3.11 * k
    outer = [(B, -A), (A, -B), (A, B), (B, A), (-B, A), (-A, B), (-A, -B), (-B, -A)]
    inner = [(D, -C), (C, -D), (C, D), (D, C), (-D, C), (-C, D), (-C, -D), (-D, -C)]
    shade = [base, base, mid, base, deep, base, mid, base]   # crown facets, clockwise from top-right
    o = ""
    for i in range(8):
        j = (i + 1) % 8
        quad = [outer[i], outer[j], inner[j], inner[i]]
        o += (f'<path d="M{" L".join(f"{n(x)},{n(y)}" for x, y in quad)}Z" fill="{shade[i]}" stroke="{edge}" '
              f'stroke-width="{n(0.29 * k)}" stroke-linejoin="round"/>')
    o += f'<path d="M{" L".join(f"{n(x)},{n(y)}" for x, y in inner)}Z" fill="{base}" stroke="{edge}" stroke-width="{n(0.36 * k)}"/>'
    o += f'<path d="M{n(-D)},{n(-C)} L{n(D)},{n(-C)} L0,0Z" fill="{edge}" opacity="0.55"/>'
    o += f'<path d="M{n(D)},{n(C)} L{n(-D)},{n(C)} L0,0Z" fill="{deep}" opacity="0.45"/>'
    o += f'<path d="M{" L".join(f"{n(x)},{n(y)}" for x, y in outer)}Z" fill="none" stroke="url(#gGold)" stroke-width="{n(0.725 * k)}" stroke-linejoin="round"/>'
    return o


def gem(name: str) -> str:
    glow = "rStar" if gem_key(name) == "pearl" else "rGoldGlow"
    return wrap((-25, -25, 50, 50), f'<circle r="24.6" fill="url(#{glow})" opacity="0.3"/>' + _gem(name), cls="gem")


def gem_avoid(name: str) -> str:
    """Dimmed stone in an ash ring with a strike line (stones to avoid)."""
    inner = (f'<g opacity="0.6"><circle r="9.52" fill="url(#rGoldGlow)" opacity="0.3"/>{_gem(name, 0.385)}</g>'
             f'<circle r="8.2" fill="none" stroke="{ASH}" stroke-width="0.2" opacity="0.8"/>'
             f'<line x1="-5.8" y1="5.8" x2="5.8" y2="-5.8" stroke="{ASH}" stroke-width="0.24" opacity="0.9"/>')
    return wrap((-9.82, -9.82, 19.64, 19.64), inner, cls="gem-avoid")


def gem_emblem(name: str) -> str:
    vb, ring = _static("celestial_frames/section_emblem_ring_empty.svg")
    return wrap(vb, ring + f'<g transform="translate(17,17)">{_gem(name, 0.55)}</g>', cls="emblem-svg")


# --------------------------------------------------------------------------- remedy and ritual icons
def remedy_kind(text_: str) -> str:
    """Pick the icon family for a remedy / ritual from its wording."""
    t = text_.lower()
    rules = [
        ("diya", r"\bdiya\b|\blamp\b|\bflame\b|\bdeepak\b|\bcandle\b"),
        ("smoke", r"\bloban\b|\bincense\b|\bdhoop\b|\bagarbatti\b|\bsmoke\b|\bfragrance\b|\bcamphor\b"),
        ("water", r"\bwater\b|\bmilk\b|\bjal\b|\babhishek"),
        ("flower", r"\bflowers?\b|\blotus\b|\bpetals?\b|\bgarland\b"),
        ("offering", r"\bfeed\b|\bdonate\b|\bgrains?\b|\brice\b|\bbirds?\b|\bcows?\b|\bsesame\b|\bcharity\b|\bfood\b"),
        ("sun", r"\bsun\b|\bsurya\b|\bsunrise\b"),
        ("moon", r"\bmoon\b|\bmoonlight\b|\bchandra\b"),
        ("om", r"\bchant\b|\brecite\b|\bmantra\b|\bstotra\w*\b|\bchalisa\b|\bjapa?\b|\bom\b|\bsahasranam\w*\b|\bashtakam\b"),
    ]
    for kind, pattern in rules:
        if re.search(pattern, t):
            return kind
    return "lotus"


def _icon(kind: str, cx: float, cy: float, k: float) -> str:
    """Line icon centred on (cx, cy); k scales a 15-unit design."""
    def T(inner):
        return f'<g transform="translate({n(cx)},{n(cy)}) scale({n(k)})">{inner}</g>'
    if kind == "om":
        _, inner = _static("spiritual_icons/om_symbol.svg")
        return f'<g transform="translate({n(cx + 0.3 * k)},{n(cy + 6.2 * k)}) scale({n(0.72 * k)})">{inner}</g>'
    if kind == "water":
        return T('<path d="M0,-8.4 C3.6,-3.6 5.6,-0.8 5.6,2.2 A5.6,5.6 0 0 1 -5.6,2.2 C-5.6,-0.8 -3.6,-3.6 0,-8.4Z" fill="#0b1226" stroke="url(#gGold)" stroke-width="0.5" stroke-linejoin="round"/>'
                 f'<path d="M-2.8,2.4 A2.9,2.9 0 0 0 -0.4,5.2" fill="none" stroke="{ICE}" stroke-width="0.4" stroke-linecap="round"/>')
    if kind == "smoke":
        return T(f'<path d="M0,7.5 V0.5" fill="none" stroke="url(#gGold)" stroke-width="0.7" stroke-linecap="round"/>'
                 f'<path d="M-4.4,7.8 H4.4" fill="none" stroke="{GOLD}" stroke-width="0.5" stroke-linecap="round"/>'
                 f'<path d="M0,-0.4 C-2.6,-2.4 2.6,-3.6 0,-5.8 C-2,-7.4 1.6,-8.2 0.4,-9.8" fill="none" stroke="{GOLD_LIGHT}" stroke-width="0.45" opacity="0.9" stroke-linecap="round"/>'
                 '<circle cx="0" cy="0.4" r="0.9" fill="#ffb070"/>')
    if kind == "diya":
        _, inner = _static("spiritual_icons/diya_lamp.svg")
        return f'<g transform="translate({n(cx)},{n(cy + 1.2 * k)}) scale({n(0.42 * k)})">{inner}</g>'
    if kind == "sun":
        return T(f'<circle r="4.2" fill="url(#rSun)"/><path d="{ticks(0, 0, 5.6, 16, 1.5, 2.6, 2)}" fill="none" stroke="{GOLD_LIGHT}" stroke-width="0.32" stroke-linecap="round" opacity="0.85"/>')
    if kind == "moon":
        return T(moon(0, 0, 6.2, 3, 10))
    if kind == "offering":
        return T(f'<path d="M-7,0.6 H7 A7,6.2 0 0 1 -7,0.6Z" fill="#0b1226" stroke="url(#gGold)" stroke-width="0.5" stroke-linejoin="round"/>'
                 f'<path d="M-3.2,7.6 H3.2" fill="none" stroke="{GOLD}" stroke-width="0.5" stroke-linecap="round"/>'
                 + "".join(f'<circle cx="{x}" cy="{y}" r="0.75" fill="{GOLD_LIGHT}"/>' for x, y in
                           [(-3.6, -1.6), (-1.2, -2.3), (1.3, -2.2), (3.7, -1.5), (-2.3, -4.3), (0.1, -4.9), (2.5, -4.2), (0.1, -7.2)]))
    if kind == "flower":
        petal = "M0,-8.2 C2.6,-5.6 2.6,-2.2 0,0 C-2.6,-2.2 -2.6,-5.6 0,-8.2Z"
        return T("".join(f'<path d="{petal}" transform="rotate({a})" fill="#0b1226" stroke="url(#gGold)" stroke-width="0.42" stroke-linejoin="round"/>'
                         for a in range(0, 360, 45)) + f'<circle r="1.3" fill="{GOLD_LIGHT}"/>')
    # lotus with star: the generic sacred-practice mark
    petal = "M0,-8.6 C3.2,-5.8 3.2,-2.6 0,-1.2 C-3.2,-2.6 -3.2,-5.8 0,-8.6Z"
    return T("".join(f'<path d="{petal}" transform="rotate({a})" fill="none" stroke="{GOLD}" stroke-width="0.4" stroke-linejoin="round" opacity="0.9"/>'
                     for a in range(0, 360, 45)) + f'<path d="{sparkle_path(0, 0, 2.6)}" fill="{GOLD_LIGHT}"/>')


def remedy_medallion(kind: str) -> str:
    """Icon in a gold ring medallion, as on the remedies page."""
    inner = ('<circle cx="15" cy="15" r="23.56" fill="url(#rGoldGlow)" opacity="0.35"/>'
             '<circle cx="15" cy="15" r="12.4" fill="#080b16" stroke="url(#gGold)" stroke-width="0.372"/>'
             f'<circle cx="15" cy="15" r="10.66" fill="none" stroke="{GOLD}" stroke-width="0.149" opacity="0.4" stroke-dasharray="0.25 1.12"/>')
    return wrap((-8.86, -8.86, 47.72, 47.72), inner + _icon(kind, 15, 15, 1.0), cls="medallion")


def icon_emblem(kind: str) -> str:
    """The same icons inside the ornamental section ring (ritual page header)."""
    vb, ring = _static("celestial_frames/section_emblem_ring_empty.svg")
    return wrap(vb, ring + _icon(kind, 17, 17, 1.0), cls="emblem-svg")


def moon_emblem(step: int) -> str:
    vb, ring = _static("celestial_frames/section_emblem_ring_empty.svg")
    return wrap(vb, ring + moon(17, 17, 9.2, step, 12), cls="emblem-svg")
