#!/usr/bin/env python3
"""Turn the golden moons of the month-opener backgrounds into white-silver moons (nebula sky untouched).

    python tools/recolor_moons.py            # all 12 report/static/img/bg_month_NN.jpg, in place
Needs opencv-python-headless + numpy.  Safe to run twice (white pixels are not touched again).
"""
from pathlib import Path

import cv2
import numpy as np

IMG = Path(__file__).resolve().parent.parent / "report" / "static" / "img"


def whiten(path: Path) -> None:
    bgr = cv2.imread(str(path))
    H, W = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV_FULL).astype(np.float32)   # H 0-255
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    yy, xx = np.mgrid[0:H, 0:W]
    near = ((xx - 0.5 * W) ** 2 + (yy - 0.36 * H) ** 2) < (0.34 * W) ** 2
    warm = np.clip((s - 0.03) / 0.10, 0, 1) * np.clip((85 - np.abs(h - 42)) / 25, 0, 1) * near
    warm = cv2.GaussianBlur(warm.astype(np.float32), (0, 0), 1.2)
    # silver-white with a cool tint; keep the crater texture (value channel), lift it slightly
    lum = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    lift = np.clip(lum ** 0.95 * 1.06, 0, 1)
    white = np.stack([lift * 1.0, lift * 0.965, lift * 0.90], axis=-1) * 255      # BGR: slightly blue
    out = bgr.astype(np.float32) * (1 - warm[..., None]) + white * warm[..., None]
    cv2.imwrite(str(path), np.clip(out, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 90])


if __name__ == "__main__":
    for i in range(1, 13):
        whiten(IMG / f"bg_month_{i:02d}.jpg")
        print("bg_month", i)
