#!/usr/bin/env python3
"""Build report/data/constellations.json.

Aquarius is taken from the supplied artwork so it stays identical to the
approved design.  The other eleven figures are drawn from approximate star
positions (right ascension in hours, declination in degrees, visual
magnitude) with the usual stick-figure joins, in the same visual language.
The shipped JSON is already built; run this only to change the figures.

    python tools/build_constellations.py
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# name: (RA hours, Dec degrees, magnitude)
STARS = {
    "aries": {
        "alpha": (2.1196, 23.46, 2.0), "beta": (1.9107, 20.81, 2.6), "gamma": (1.8923, 19.29, 3.9),
        "41": (2.8331, 27.26, 3.6),
    },
    "taurus": {
        "alpha": (4.5987, 16.51, 0.85), "beta": (5.4382, 28.61, 1.65), "zeta": (5.6274, 21.14, 3.0),
        "epsilon": (4.4769, 19.18, 3.5), "gamma": (4.3299, 15.63, 3.65), "delta": (4.3823, 17.54, 3.75),
        "theta": (4.4777, 15.87, 3.4), "lambda": (4.0113, 12.49, 3.4), "xi": (3.4528, 9.73, 3.7),
        "omicron": (3.4136, 9.03, 3.6), "eta": (3.7914, 24.11, 2.85),
    },
    "gemini": {
        "alpha": (7.5767, 31.89, 1.6), "beta": (7.7553, 28.03, 1.15), "gamma": (6.6285, 16.40, 1.9),
        "epsilon": (6.7322, 25.13, 3.0), "mu": (6.3827, 22.51, 2.9), "eta": (6.2479, 22.51, 3.3),
        "delta": (7.3354, 21.98, 3.5), "zeta": (7.0685, 20.57, 3.8), "xi": (6.7548, 12.90, 3.35),
        "kappa": (7.7408, 24.40, 3.6), "lambda": (7.3015, 16.54, 3.6), "tau": (7.1857, 30.25, 4.4),
        "theta": (6.8798, 33.96, 3.6), "iota": (7.4288, 27.80, 3.8), "upsilon": (7.5987, 26.90, 4.1),
        "nu": (6.4827, 20.21, 4.1),
    },
    "cancer": {
        "alpha": (8.9748, 11.86, 4.25), "beta": (8.2753, 9.19, 3.5), "delta": (8.7448, 18.15, 3.9),
        "gamma": (8.7215, 21.47, 4.65), "iota": (8.7783, 28.76, 4.0),
    },
    "leo": {
        "alpha": (10.1395, 11.97, 1.35), "beta": (11.8177, 14.57, 2.1), "gamma": (10.3329, 19.84, 2.0),
        "delta": (11.2351, 20.52, 2.55), "theta": (11.2373, 15.43, 3.3), "eta": (10.1222, 16.76, 3.5),
        "zeta": (10.2782, 23.42, 3.4), "mu": (9.8794, 26.01, 3.9), "epsilon": (9.7642, 23.77, 3.0),
    },
    "virgo": {
        "alpha": (13.4199, -11.16, 1.0), "gamma": (12.6943, -1.45, 2.75), "epsilon": (13.0363, 10.96, 2.8),
        "beta": (11.8449, 1.76, 3.6), "delta": (12.9267, 3.40, 3.4), "zeta": (13.5783, -0.60, 3.4),
        "eta": (12.3318, -0.67, 3.9), "nu": (11.7643, 6.53, 4.0), "iota": (14.2669, -6.00, 4.1),
        "mu": (14.7177, -5.66, 3.9), "tau": (14.0273, 1.54, 4.25), "theta": (13.1658, -5.54, 4.4),
        "109": (14.7708, 1.89, 3.7),
    },
    "libra": {
        "alpha": (14.8480, -16.04, 2.75), "beta": (15.2835, -9.38, 2.6), "gamma": (15.5921, -14.79, 3.9),
        "sigma": (15.0678, -25.28, 3.3), "upsilon": (15.6171, -28.14, 3.6), "tau": (15.6441, -29.78, 3.65),
    },
    "scorpio": {
        "alpha": (16.4901, -26.43, 1.0), "beta": (16.0906, -19.81, 2.6), "delta": (16.0056, -22.62, 2.3),
        "pi": (15.9809, -26.11, 2.9), "sigma": (16.3531, -25.59, 2.9), "tau": (16.5981, -28.22, 2.8),
        "epsilon": (16.8361, -34.29, 2.3), "mu": (16.8645, -38.05, 3.0), "zeta": (16.9097, -42.36, 3.6),
        "eta": (17.2027, -43.24, 3.3), "theta": (17.6220, -43.00, 1.85), "iota": (17.7931, -40.13, 3.0),
        "kappa": (17.7081, -39.03, 2.4), "lambda": (17.5601, -37.10, 1.6), "upsilon": (17.5127, -37.30, 2.7),
    },
    "sagittarius": {
        "epsilon": (18.4029, -34.38, 1.8), "delta": (18.3499, -29.83, 2.7), "lambda": (18.4662, -25.42, 2.8),
        "sigma": (18.9211, -26.30, 2.05), "zeta": (19.0435, -29.88, 2.6), "phi": (18.7609, -26.99, 3.2),
        "tau": (19.1157, -27.67, 3.3), "gamma": (18.0968, -30.42, 3.0), "eta": (18.2938, -36.76, 3.1),
        "pi": (19.1627, -21.02, 2.9), "mu": (18.2294, -21.06, 3.85), "xi": (18.9620, -21.11, 3.5),
    },
    "capricorn": {
        "alpha": (20.3009, -12.54, 3.6), "beta": (20.3502, -14.78, 3.05), "psi": (20.7682, -25.27, 4.1),
        "omega": (20.8635, -26.92, 4.1), "zeta": (21.4444, -22.41, 3.75), "delta": (21.7840, -16.13, 2.85),
        "gamma": (21.6682, -16.66, 3.7), "iota": (21.3711, -16.83, 4.3), "theta": (21.0990, -17.23, 4.1),
    },
    "pisces": {
        "alpha": (2.0341, 2.76, 3.8), "omicron": (1.7566, 9.16, 4.25), "eta": (1.5247, 15.35, 3.6),
        "phi": (1.2292, 24.58, 4.65), "upsilon": (1.3244, 27.26, 4.75), "tau": (1.1946, 30.09, 4.5),
        "nu": (1.6905, 5.49, 4.45), "mu": (1.5031, 6.14, 4.85), "epsilon": (1.0491, 7.89, 4.3),
        "delta": (0.8114, 7.59, 4.4), "omega": (23.9885, 6.86, 4.0), "iota": (23.6656, 5.63, 4.1),
        "theta": (23.4661, 6.38, 4.3), "gamma": (23.2861, 3.28, 3.7), "kappa": (23.4489, 1.26, 4.9),
        "lambda": (23.7008, 1.78, 4.5),
    },
}

LINES = {
    "aries": "41-alpha alpha-beta beta-gamma",
    "taurus": "zeta-alpha alpha-theta theta-gamma gamma-delta delta-epsilon epsilon-beta gamma-lambda "
              "lambda-xi xi-omicron",
    "gemini": "alpha-tau tau-epsilon epsilon-mu mu-eta epsilon-nu tau-theta tau-iota iota-upsilon "
              "upsilon-beta upsilon-delta delta-zeta zeta-gamma delta-lambda lambda-xi beta-kappa",
    "cancer": "iota-gamma gamma-delta delta-alpha delta-beta",
    "leo": "alpha-eta eta-gamma gamma-zeta zeta-mu mu-epsilon gamma-delta delta-beta beta-theta "
           "theta-alpha delta-theta",
    "virgo": "beta-eta eta-gamma gamma-delta delta-epsilon gamma-theta theta-alpha delta-zeta zeta-tau "
             "tau-109 zeta-iota iota-mu beta-nu",
    "libra": "alpha-beta beta-gamma gamma-alpha alpha-sigma gamma-upsilon upsilon-tau",
    "scorpio": "beta-delta delta-pi delta-sigma sigma-alpha alpha-tau tau-epsilon epsilon-mu mu-zeta "
               "zeta-eta eta-theta theta-iota iota-kappa kappa-lambda lambda-upsilon",
    "sagittarius": "gamma-delta gamma-epsilon delta-epsilon epsilon-zeta zeta-tau tau-sigma sigma-phi "
                   "phi-zeta phi-delta delta-lambda lambda-phi lambda-mu sigma-xi xi-pi epsilon-eta",
    "capricorn": "alpha-beta beta-psi psi-omega omega-zeta zeta-delta delta-gamma gamma-iota "
                 "iota-theta theta-beta",
    "pisces": "tau-upsilon upsilon-phi phi-tau phi-eta eta-omicron omicron-alpha alpha-nu nu-mu "
              "mu-epsilon epsilon-delta delta-omega omega-iota iota-theta theta-gamma gamma-kappa "
              "kappa-lambda lambda-iota",
}


def project(sign: str) -> dict:
    stars = STARS[sign]
    ras = [ra - 24 if ra > 12 and sign == "pisces" else ra for ra, _, _ in stars.values()]
    decs = [d for _, d, _ in stars.values()]
    ra0, dec0 = (max(ras) + min(ras)) / 2, (max(decs) + min(decs)) / 2
    pts = {}
    for name, (ra, dec, mag) in stars.items():
        if sign == "pisces" and ra > 12:
            ra -= 24
        # sky view: east (larger RA) to the left, north up
        x = -(ra - ra0) * 15 * math.cos(math.radians(dec0))
        y = -(dec - dec0)
        pts[name] = (x, y, mag)
    xs, ys = [p[0] for p in pts.values()], [p[1] for p in pts.values()]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    scale = 1 / max(w, h)  # normalise so the longer side is 1
    names = list(pts)
    ranked = sorted(names, key=lambda n: pts[n][2])
    out_stars = []
    for n in names:
        x, y, mag = pts[n]
        rank = ranked.index(n)
        # the two brightest get the four-point sparkle, like the supplied Aquarius
        size = "bright" if rank < 2 else ("mid" if mag <= 3.7 or rank < 5 else "small")
        out_stars.append({"x": round((x - cx) * scale, 4), "y": round((y - cy) * scale, 4), "size": size})
    out_lines = [[names.index(a), names.index(b)] for a, b in (seg.split("-") for seg in LINES[sign].split())]
    return {"w": round(w * scale, 4), "h": round(h * scale, 4), "stars": out_stars, "lines": out_lines}


def from_supplied(svg_path: Path) -> dict:
    """Read the approved Aquarius artwork back into the same normalised form."""
    s = svg_path.read_text(encoding="utf-8")
    stars = []
    for m in re.finditer(r'<g opacity="[^"]*"><circle cx="([-\d.]+)" cy="([-\d.]+)" r="([-\d.]+)" fill="url\(#rStar\)"/>', s):
        x, y, r = map(float, m.groups())
        stars.append((x, y, "bright" if r > 4 else ("mid" if r > 1 else "small")))
    raw_lines = [tuple(map(float, m.groups())) for m in re.finditer(
        r'<line x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"', s)]

    def nearest(x, y):
        return min(range(len(stars)), key=lambda i: (stars[i][0] - x) ** 2 + (stars[i][1] - y) ** 2)

    lines = sorted({tuple(sorted((nearest(x1, y1), nearest(x2, y2)))) for x1, y1, x2, y2 in raw_lines})
    xs, ys = [p[0] for p in stars], [p[1] for p in stars]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    scale = 1 / max(w, h)
    return {"w": round(w * scale, 4), "h": round(h * scale, 4),
            "stars": [{"x": round((x - cx) * scale, 4), "y": round((y - cy) * scale, 4), "size": z} for x, y, z in stars],
            "lines": [list(l) for l in lines if l[0] != l[1]]}


def main():
    data = {sign: project(sign) for sign in STARS}
    data["aquarius"] = from_supplied(ROOT / "report/static/svg/constellations/aquarius_constellation.svg")
    out = ROOT / "report/data/constellations.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    for k, v in data.items():
        print(f"{k:12s} {len(v['stars']):2d} stars {len(v['lines']):2d} lines  box {v['w']:.2f} x {v['h']:.2f}")


if __name__ == "__main__":
    main()
