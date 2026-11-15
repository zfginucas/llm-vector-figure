#!/usr/bin/env python3
"""Trace raster regions of the Fig.5 target into vector contours."""
import json, math, os
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(ROOT, "assets", "target.png")
OUT = os.path.join(ROOT, "data", "shapes.json")

NAVY = np.array([28, 72, 112], float)
TEAL = np.array([12, 126, 136], float)
WHITE = np.array([253, 253, 253], float)

def color_mask(crop, ref, tmin=0.45, resid=45):
    """Pixels on the white->ref colour ramp above tmin."""
    d = ref - WHITE
    n = (d * d).sum()
    p = crop.reshape(-1, 3) - WHITE
    t = (p @ d) / n
    proj = np.outer(t, d)
    res = np.linalg.norm(p - proj, axis=1)
    m = (t > tmin) & (res < resid)
    return m.reshape(crop.shape[0], crop.shape[1])

def rdp(points, eps=0.9):
    if len(points) < 3:
        return points
    pts = np.asarray(points, float)
    start, end = pts[0], pts[-1]
    d = end - start
    L = np.linalg.norm(d)
    if L < 1e-9:
        dist = np.linalg.norm(pts - start, axis=1)
    else:
        dist = np.abs(np.cross(d, pts - start)) / L
    i = int(np.argmax(dist))
    if dist[i] > eps:
        left = rdp(pts[:i+1], eps)
        right = rdp(pts[i:], eps)
        return np.vstack([left[:-1], right])
    return np.array([start, end])

def trace_mask(mask, min_area=6.0, eps=0.9):
    """Return list of closed contours (Nx2, pixel coords) via marching squares."""
    fig = plt.figure()
    ax = fig.add_subplot(111)
    cs = ax.contour(mask.astype(float), levels=[0.5])
    segs = cs.allsegs[0] if cs.allsegs else []
    out = []
    for seg in segs:
        if len(seg) < 4:
            continue
        # closed loop area
        x, y = seg[:, 0], seg[:, 1]
        area = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
        if area < min_area:
            continue
        s = rdp(seg, eps)
        if len(s) >= 4:
            out.append(s)
    plt.close(fig)
    return out

def extract(name, box, colors, min_area=6.0, eps=0.9):
    x0, y0, x1, y1 = box
    im = np.asarray(Image.open(TARGET).convert("RGB")).astype(float)
    crop = im[y0:y1, x0:x1]
    result = {"bbox": [x0, y0, x1, y1], "colors": {}}
    for cname, ref in colors.items():
        m = color_mask(crop, ref)
        contours = trace_mask(m, min_area=min_area, eps=eps)
        contours = [[[float(px + x0), float(py + y0)] for px, py in c] for c in contours]
        result["colors"][cname] = contours
        print(f"{name}/{cname}: {len(contours)} contours, {sum(len(c) for c in contours)} pts")
    return result

ICONS = {
    "head1": ((62, 305, 232, 478), {"navy": NAVY}),
    "handL1": ((245, 300, 337, 420), {"navy": NAVY}),
    "handR1": ((348, 300, 440, 420), {"teal": TEAL}),
    "wave1": ((28, 450, 492, 565), {"navy": NAVY, "teal": TEAL}),

    "head2": ((562, 305, 732, 478), {"navy": NAVY}),
    "fist2": ((745, 300, 840, 422), {"navy": NAVY}),
    "foot2": ((870, 292, 968, 422), {"teal": TEAL}),
    "wave2": ((538, 450, 1000, 565), {"navy": NAVY, "teal": TEAL}),

    "head3": ((1052, 305, 1198, 478), {"navy": NAVY}),
    "handL3": ((1192, 300, 1256, 404), {"navy": NAVY}),
    "handR3": ((1272, 300, 1336, 404), {"teal": TEAL}),
    "feet3": ((1340, 300, 1414, 406), {"teal": TEAL}),
    "tongue3": ((1418, 300, 1500, 404), {"navy": NAVY}),
    "wave3": ((1048, 450, 1512, 565), {"navy": NAVY, "teal": TEAL}),
}

if __name__ == "__main__":
    shapes = {}
    for name, (box, colors) in ICONS.items():
        shapes[name] = extract(name, box, colors)
    with open(OUT, "w") as f:
        json.dump(shapes, f)
    print("wrote", OUT)
