#!/usr/bin/env python3
"""Repair the soft parts of an opener using the original artwork as the reference for detail.

The 4K opener (art_originals/color_ref/chNN.jpg) is a zoomed, AI-enlarged version of the original picture: the colour and
mood are right but thin lines (arcs, rims, constellations) came out blurred.  The original (art_originals/chNN_original.png)
has them crisp.  The original is registered onto the opener (SIFT similarity + dense flow), and its fine detail is
transplanted in: low frequencies (colour, light) stay from the opener, fine structure comes from the original.

    python tools/repair_with_original.py            # writes report/static/img/chapters/ch01/04/07.jpg
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import art_clean                                                    # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art_originals"
OUT = ROOT / "report" / "static" / "img" / "chapters"
# how much of the original's fine detail replaces the opener's (1 = all), and the detail scale (px)
TOP_KEEP = {1: 585, 4: 645, 7: 640}                              # px from the top of the page that stay as the opener has them
CHAPTERS = {1: dict(mix=1.0, keep=0.30, sigma=2.2), 4: dict(mix=1.0, keep=0.30, sigma=2.2), 7: dict(mix=1.0, keep=0.30, sigma=2.2)}


def register(org: np.ndarray, old: np.ndarray) -> np.ndarray:
    """Return the original warped onto the opener's pixel grid."""
    H, W = old.shape[:2]
    s = H / org.shape[0]
    org_r = cv2.resize(org, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    sift = cv2.SIFT_create(8000)
    g1, g2 = cv2.cvtColor(org_r, cv2.COLOR_BGR2GRAY), cv2.cvtColor(old, cv2.COLOR_BGR2GRAY)
    k1, d1 = sift.detectAndCompute(g1, None)
    k2, d2 = sift.detectAndCompute(g2, None)
    good = [a for a, b in cv2.BFMatcher().knnMatch(d1, d2, k=2) if a.distance < 0.75 * b.distance]
    p1 = np.float32([k1[a.queryIdx].pt for a in good]); p2 = np.float32([k2[a.trainIdx].pt for a in good])
    M, inl = cv2.estimateAffinePartial2D(p1, p2, method=cv2.RANSAC, ransacReprojThreshold=3)
    if M is None or inl.sum() < 40:
        raise SystemExit("could not register the original onto the opener")
    # warp straight from the full-resolution original (one resampling)
    S = np.diag([s, s, 1.0]); M3 = np.vstack([M, [0, 0, 1]]) @ S
    warped = cv2.warpAffine(org, M3[:2], (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    # dense flow: fix the small local differences left after the global fit
    a = cv2.GaussianBlur(cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY), (0, 0), 2)
    b = cv2.GaussianBlur(g2, (0, 0), 2)
    flow = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(a, b, None)
    flow = cv2.GaussianBlur(flow, (0, 0), 6)                          # smooth: no local tearing
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    return cv2.remap(warped, gx + flow[..., 0], gy + flow[..., 1], cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE), int(inl.sum())


def transplant(old: np.ndarray, ref: np.ndarray, mix: float, keep: float, sigma: float) -> np.ndarray:
    o, r = old.astype(np.float32), ref.astype(np.float32)
    # colour / light of the opener, detail of the original (brightness only, so no colour fringes)
    lo = cv2.cvtColor(old, cv2.COLOR_BGR2LAB).astype(np.float32)
    lr = cv2.cvtColor(ref, cv2.COLOR_BGR2LAB).astype(np.float32)
    Lo, Lr = lo[..., 0], lr[..., 0]
    hf_ref = Lr - cv2.GaussianBlur(Lr, (0, 0), sigma)
    hf_old = Lo - cv2.GaussianBlur(Lo, (0, 0), sigma)
    lo[..., 0] = np.clip(Lo - (1 - keep) * mix * hf_old + mix * hf_ref * 1.0 + (1 - mix) * 0, 0, 255)
    # thin bright lines: take the original's colour there too, so a gold arc stays gold instead of turning grey
    return cv2.cvtColor(lo.astype(np.uint8), cv2.COLOR_LAB2BGR)


def main() -> int:
    for n, p in CHAPTERS.items():
        old = cv2.imread(str(ART / "color_ref" / f"ch{n:02d}.jpg"))
        org = cv2.imread(str(ART / f"ch{n:02d}_original.png"))
        ref, inl = register(org, old)
        out = transplant(old, ref, **p)
        # the original still carries its baked title: keep the opener (title already painted out) above this line
        m = np.zeros(old.shape[:2], np.float32)
        m[:TOP_KEEP[n], :] = 1
        m = cv2.GaussianBlur(m, (0, 0), 16)[..., None]
        out = (out * (1 - m) + old * m).astype(np.uint8)
        Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB)).save(OUT / f"ch{n:02d}.jpg", "JPEG", quality=88, optimize=True, progressive=True)
        print(f"ch{n:02d}: registered with {inl} matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
