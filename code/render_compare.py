#!/usr/bin/env python3
"""Render a PPTX with Quick Look and score it against the target figure."""
import os, subprocess, sys, glob, shutil
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(ROOT, "assets", "target.png")


def render(pptx, outdir):
    if os.path.isdir(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir)
    subprocess.run(["qlmanage", "-t", "-s", "1600", "-o", outdir, pptx],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cands = glob.glob(os.path.join(outdir, "*.png"))
    if not cands:
        raise RuntimeError("qlmanage produced no thumbnail")
    return cands[0]


def ssim(a, b, win=7):
    a = a.astype(np.float64); b = b.astype(np.float64)
    from numpy.lib.stride_tricks import sliding_window_view
    pad = win // 2
    ap = np.pad(a, pad, mode="reflect"); bp = np.pad(b, pad, mode="reflect")
    wa = sliding_window_view(ap, (win, win)).mean(axis=(-1, -2))
    wb = sliding_window_view(bp, (win, win)).mean(axis=(-1, -2))
    va = sliding_window_view(ap * ap, (win, win)).mean(axis=(-1, -2)) - wa * wa
    vb = sliding_window_view(bp * bp, (win, win)).mean(axis=(-1, -2)) - wb * wb
    cov = sliding_window_view(ap * bp, (win, win)).mean(axis=(-1, -2)) - wa * wb
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    s = ((2 * wa * wb + C1) * (2 * cov + C2)) / ((wa ** 2 + wb ** 2 + C1) * (va + vb + C2))
    return float(s.mean())


REGIONS = {
    "title": (0, 20, 1536, 120),
    "card1": (31, 133, 488, 586),
    "card2": (539, 133, 996, 586),
    "card3": (1048, 133, 1503, 586),
    "bottom_left": (33, 672, 887, 939),
    "bottom_right": (914, 672, 1500, 939),
}


def main(pptx):
    png = render(pptx, os.path.join(ROOT, ".render"))
    ref = Image.open(TARGET).convert("RGB")
    out = Image.open(png).convert("RGB").resize(ref.size, Image.LANCZOS)
    out.save(os.path.join(ROOT, ".render", "render_latest.png"))
    a = np.asarray(ref).astype(np.float32)
    b = np.asarray(out).astype(np.float32)
    mse = float(((a - b) ** 2).mean())
    psnr = 10 * np.log10(255 ** 2 / mse) if mse > 0 else 99
    gray_a = np.asarray(ref.convert("L")); gray_b = np.asarray(out.convert("L"))
    print(f"GLOBAL PSNR={psnr:.2f} dB  SSIM={ssim(gray_a, gray_b, 7):.4f}  MAE={np.abs(a-b).mean():.2f}")
    for name, (x0, y0, x1, y1) in REGIONS.items():
        ga = gray_a[y0:y1, x0:x1]; gb = gray_b[y0:y1, x0:x1]
        print(f"  {name:13s} SSIM={ssim(ga, gb, 5):.4f}")
    # diff heatmap
    diff = np.abs(a - b).mean(axis=2)
    heat = np.zeros((*diff.shape, 3), dtype=np.uint8)
    heat[..., 0] = np.clip(diff * 3, 0, 255)
    heat[..., 1] = np.clip(diff * 1.2, 0, 255)
    Image.fromarray(heat).save(os.path.join(ROOT, ".render", "diff_heat.png"))
    # side by side
    canvas = Image.new("RGB", (ref.width, ref.height * 2 + 10), "white")
    canvas.paste(ref, (0, 0)); canvas.paste(out, (0, ref.height + 10))
    canvas.save(os.path.join(ROOT, ".render", "side_by_side.png"))
    print("render:", png)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "fig5_native_v1.pptx"))
