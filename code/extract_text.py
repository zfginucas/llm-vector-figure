#!/usr/bin/env python3
"""Trace every glyph of the target figure into vector contours (outline mode)."""
import json, os
import numpy as np
from PIL import Image
from extract_shapes import TARGET, rdp, trace_mask

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "text_shapes.json")

WHITE_BG = "#FDFDFE"
# name: (x0,y0,x1,y1, ink, hole_fill, background)
TEXT_REGIONS = {
    "title":       ((120, 30, 1420, 100), "dark",  WHITE_BG, WHITE_BG),
    "c1_hdr":      ((145, 152, 482, 198), "white", "#204C73", "#204C73"),
    "c2_hdr":      ((635, 152, 990, 198), "white", "#0E828D", "#0E828D"),
    "c3_hdr":      ((1150, 152, 1500, 198), "white", "#E86B29", "#E86B29"),
    "c1_body":     ((40, 225, 482, 305), "dark",  WHITE_BG, WHITE_BG),
    "c2_body":     ((548, 225, 988, 305), "dark",  WHITE_BG, WHITE_BG),
    "c3_body":     ((1055, 225, 1498, 305), "dark",  WHITE_BG, WHITE_BG),
    "b1_hdr":      ((150, 695, 884, 745), "white", "#0C7F89", "#0C7F89"),
    "b2_hdr":      ((1025, 695, 1497, 745), "white", "#E36725", "#E36725"),
    "b1_body":     ((40, 775, 880, 925), "dark",  WHITE_BG, WHITE_BG),
    "b2_body":     ((930, 775, 1490, 925), "dark",  WHITE_BG, WHITE_BG),
    "c1_labels":   ((260, 420, 425, 452), "dark",  WHITE_BG, WHITE_BG),
    "c2_labels":   ((750, 420, 965, 452), "dark",  WHITE_BG, WHITE_BG),
    "c3_labels":   ((1190, 405, 1500, 455), "dark",  WHITE_BG, WHITE_BG),
}

INK = {"dark": "#0A1A3A", "white": "#FFFFFF"}


def hexrgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i+2], 16) for i in (0, 2, 4)], float)


def mask_for(crop, ink, bg_hex, tmin=0.55, resid=80):
    bg = hexrgb(bg_hex); fg = hexrgb(INK[ink])
    d = fg - bg
    n = (d * d).sum()
    p = crop.reshape(-1, 3) - bg
    t = (p @ d) / n
    res = np.linalg.norm(p - np.outer(t, d), axis=1)
    return ((t > tmin) & (res < resid)).reshape(crop.shape[0], crop.shape[1])


def main():
    im = np.asarray(Image.open(TARGET).convert("RGB")).astype(float)
    out = {}
    for name, (box, ink, hole_fill, bg) in TEXT_REGIONS.items():
        x0, y0, x1, y1 = box
        crop = im[y0:y1, x0:x1]
        scale = 4
        big = np.asarray(Image.fromarray(crop.astype(np.uint8)).resize(
            (crop.shape[1] * scale, crop.shape[0] * scale), Image.LANCZOS)).astype(float)
        m = mask_for(big, ink, bg)
        contours = trace_mask(m, min_area=1.5 * scale * scale, eps=0.9)
        contours = [[[float(px / scale + x0), float(py / scale + y0)] for px, py in c] for c in contours]
        out[name] = {"ink": ink, "fill": INK[ink], "hole": hole_fill, "contours": contours}
        print(f"{name:10s} {ink:5s} {len(contours):3d} contours, {sum(len(c) for c in contours):5d} pts")
    with open(OUT, "w") as f:
        json.dump(out, f)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
