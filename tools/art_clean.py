"""Picture clean-up used by tools/import_assets.py (needs opencv-python-headless, numpy, Pillow)."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


# ------------------------------------------------------------------ painted chapter openers
def find_title_block(rgb: np.ndarray, band: int = 640):
    """Bounding box (x0, y0, x1, y1) of the baked title (two text lines, rule, diamond) in the top band, or None."""
    gray = cv2.cvtColor(rgb[:band], cv2.COLOR_RGB2GRAY)
    bright = (gray > 150).astype(np.uint8)
    closed = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (41, 7)))
    n, _, stats, _ = cv2.connectedComponentsWithStats(closed)
    W = rgb.shape[1]
    boxes = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if w >= 60 and h <= 110 and abs((x + w / 2) - W / 2) < W * 0.2 and area > 400 and y > 20:
            boxes.append((x, y, x + w, y + h))
    if not boxes:
        return None
    # the title is the cluster of boxes nearest the top: keep boxes within 260 px of the first one
    boxes.sort(key=lambda b: b[1])
    top = boxes[0][1]
    keep = [b for b in boxes if b[1] < top + 260]
    return (min(b[0] for b in keep), min(b[1] for b in keep), max(b[2] for b in keep), max(b[3] for b in keep))


def _fill_rect(rgb: np.ndarray, x0: int, y0: int, x1: int, y1: int, feather: int = 28) -> np.ndarray:
    """Replace a rectangle by a smooth fill continued from its surroundings (+ matching grain), blended at the edges."""
    H, W = rgb.shape[:2]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    mask = np.zeros((H, W), np.uint8)
    mask[y0:y1, x0:x1] = 255
    sc = 4
    small = cv2.resize(rgb, (W // sc, H // sc), interpolation=cv2.INTER_AREA)
    sm = cv2.resize(mask, (W // sc, H // sc), interpolation=cv2.INTER_NEAREST)
    # sample the ring just outside the rectangle (robust against stray stars), then inpaint the hole smoothly
    ring = cv2.dilate(sm, np.ones((9, 9), np.uint8)) - sm
    med = cv2.medianBlur(small, 7)
    src = small.copy()
    src[ring == 0] = src[ring == 0]
    filled = cv2.inpaint(np.where(sm[..., None] > 0, med, med), cv2.dilate(sm, np.ones((3, 3), np.uint8)), 10, cv2.INPAINT_NS)
    filled = cv2.GaussianBlur(filled, (0, 0), 3)
    big = cv2.resize(filled, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32)
    grain = np.random.default_rng(7).normal(0, 1.6, rgb.shape).astype(np.float32)
    big = np.clip(big + grain, 0, 255)
    soft = cv2.GaussianBlur(mask, (0, 0), feather / 2.5).astype(np.float32)[..., None] / 255
    return (rgb * (1 - soft) + big * soft).astype(np.uint8)


def erase_title(img: Image.Image, pad: int = 34, extra=(0, 0)):
    """Paint the baked title out.  Returns (clean image, (x0, y0, x1, y1) of the removed block or None)."""
    rgb = np.array(img.convert("RGB"))
    box = find_title_block(rgb)
    if box is None:
        return img, None
    x0, y0, x1, y1 = box
    out = _fill_rect(rgb, x0 - pad - 30 - extra[0], y0 - pad, x1 + pad + 30 + extra[1], y1 + pad)
    return Image.fromarray(out), box


# ------------------------------------------------------------------ cover: remove the "FOR / NAME / date" placeholder
def fit_to_page(img: Image.Image, size=(1654, 2339)) -> Image.Image:
    """Fit a picture of another shape to the page without cropping or stretching: scale to the full height and continue
    the dark sky sideways (mirrored, blurred) - or top/bottom - to fill the page."""
    W, H = size
    im = img.convert("RGB")
    if abs(im.width / im.height - W / H) < 0.004:
        return im.resize(size, Image.LANCZOS)
    arr = np.array(im)
    if im.width / im.height < W / H:                     # too narrow: extend left and right
        nh = H
        nw = round(im.width * H / im.height)
        arr = np.array(im.resize((nw, nh), Image.LANCZOS))
        pad = (W - nw)
        l, r = pad // 2, pad - pad // 2
        ext = cv2.copyMakeBorder(arr, 0, 0, l, r, cv2.BORDER_REFLECT)
        soft = cv2.GaussianBlur(ext, (0, 0), 22)
        w = np.zeros((H, W), np.float32)
        w[:, :l] = 1
        w[:, W - r:] = 1
        w = cv2.GaussianBlur(w, (0, 0), 18)[..., None]
        w[:, l + 24:W - r - 24] = 0
        ext = (ext * (1 - w) + soft * w).astype(np.uint8)
        return Image.fromarray(ext)
    nw = W
    nh = round(im.height * W / im.width)                 # too wide: extend top and bottom
    arr = np.array(im.resize((nw, nh), Image.LANCZOS))
    pad = H - nh
    t, bt = pad // 2, pad - pad // 2
    return Image.fromarray(cv2.copyMakeBorder(arr, t, bt, 0, 0, cv2.BORDER_REFLECT))


def erase_cover_placeholder(img: Image.Image, region=(0.20, 0.822, 0.80, 0.935)) -> Image.Image:
    """Remove the baked placeholder (FOR, NAME with its stars and rules, date) leaving the painted night sky."""
    rgb = np.array(img.convert("RGB"))
    H, W = rgb.shape[:2]
    x0, y0, x1, y1 = int(region[0] * W), int(region[1] * H), int(region[2] * W), int(region[3] * H)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    # thin bright strokes only (letters, rules, sparkles): a white top-hat ignores the large soft shapes of the photo
    th = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61)))
    m = np.zeros(gray.shape, np.uint8)
    m[y0:y1, x0:x1] = (th[y0:y1, x0:x1] > 26).astype(np.uint8) * 255
    mask = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    out = cv2.inpaint(rgb, mask, 8, cv2.INPAINT_TELEA)
    soft = cv2.GaussianBlur(mask, (0, 0), 3).astype(np.float32)[..., None] / 255
    out = out * (1 - soft * 0.4) + cv2.GaussianBlur(out, (0, 0), 1.8) * soft * 0.4
    return Image.fromarray(out.astype(np.uint8))


def sharpen(img: Image.Image, amount: float = 1.0, radius: float = 1.6) -> Image.Image:
    """Clean up soft, blotchy artwork: edge-preserving smoothing (removes the JPEG / upscaling blotches), then
    two-scale sharpening of the brightness only, so edges get crisp without colour noise."""
    a = cv2.bilateralFilter(np.array(img.convert("RGB")), 7, 14, 4)
    lab = cv2.cvtColor(a, cv2.COLOR_RGB2LAB).astype(np.float32)
    L = lab[..., 0]
    for r, k in ((0.9, 1.1 * amount), (2.4, 0.7 * amount)):
        L = L + (L - cv2.GaussianBlur(L, (0, 0), r)) * k
    lab[..., 0] = np.clip(L, 0, 255)
    return Image.fromarray(cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB))


# ------------------------------------------------------------------ gemstone pictures
def clean_gem(img: Image.Image) -> Image.Image:
    """Keep only the main stone (drop slivers of neighbouring stones) and trim it to a clean oval where the picture cuts it."""
    im = img.convert("RGBA")
    a = np.array(im)
    alpha = a[..., 3]
    n, lab, stats, _ = cv2.connectedComponentsWithStats((alpha > 20).astype(np.uint8))
    if n <= 1:
        return im
    main = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    keep = lab == main
    ys, xs = np.where(keep)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    h, w = alpha.shape
    cut = y0 <= 0 or y1 >= h - 1 or x0 <= 0 or x1 >= w - 1
    mask = keep.astype(np.uint8) * 255
    if cut:     # the supplied picture cuts the stone: clip to the largest oval that fits inside what is visible
        oval = np.zeros_like(mask)
        cv2.ellipse(oval, (int((x0 + x1) / 2), int((y0 + y1) / 2)), (int((x1 - x0) / 2) - 1, int((y1 - y0) / 2) - 1), 0, 0, 360, 255, -1, cv2.LINE_AA)
        mask = cv2.bitwise_and(mask, oval)
    mask = cv2.GaussianBlur(mask, (0, 0), 0.8)
    a[..., 3] = np.minimum(alpha, mask)
    out = Image.fromarray(a)
    return out.crop(out.getbbox())


# ------------------------------------------------------------------ per-picture retouching
def remove_bright_object(img: Image.Image, rect, feather: int = 70) -> Image.Image:
    """Paint out an object (planet, ring ...) lying inside rect = (x0, y0, x1, y1) on a dark, smooth sky."""
    rgb = np.array(img.convert("RGB"))
    x0, y0, x1, y1 = rect
    out = _fill_rect(rgb, x0, y0, x1, y1, feather=feather)
    return Image.fromarray(out)


def fix_blur_patch(img: Image.Image, rect, feather: int = 90, glow=None, sparkle: int = 420) -> Image.Image:
    """Replace a smeared (out-of-focus) patch by smooth haze continued from its surroundings plus fresh fine sparkles.
    glow = (x, y, radius) adds a crisp soft light orb (the smear was meant to be a light)."""
    rgb = np.array(img.convert("RGB"))
    x0, y0, x1, y1 = rect
    H, W = rgb.shape[:2]
    out = _fill_rect(rgb, x0, y0, x1, y1, feather=feather).astype(np.float32)
    mask = np.zeros((H, W), np.uint8)
    mask[y0:y1, x0:x1] = 255
    soft = (cv2.GaussianBlur(mask, (0, 0), feather / 2.5).astype(np.float32) / 255)[..., None]
    rng = np.random.default_rng(11)
    layer = np.zeros((H, W), np.float32)
    for x, y in zip(rng.integers(x0, x1, sparkle), rng.integers(y0, y1, sparkle)):
        cv2.circle(layer, (int(x), int(y)), int(rng.integers(1, 3)), float(rng.uniform(70, 190)), -1)
    layer = cv2.GaussianBlur(layer, (0, 0), 0.9)
    out = out + layer[..., None] * np.array([1.0, 0.83, 0.48]) * soft * 0.9
    if glow:
        gx, gy, gr = glow
        yy, xx = np.mgrid[0:H, 0:W]
        g = np.clip(1 - np.sqrt((xx - gx) ** 2 + (yy - gy) ** 2) / gr, 0, 1) ** 2.2
        out = out + g[..., None] * np.array([255, 232, 175]) * 0.8
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
