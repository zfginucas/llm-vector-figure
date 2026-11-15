#!/usr/bin/env python3
"""Self-feedback loop: build PPTX -> render -> score -> (optional VLM critique) -> log.

Usage:
  python3 iterate.py --mode outline --rounds 1 --vlm
  python3 iterate.py --mode editable --rounds 1

The loop does not mutate design parameters by itself. It produces a numeric score and a
structured critique; an LLM/human then patches build_pptx.py (or the extracted JSON) and
the next round starts from there. Keep every round in iteration_log.csv.
"""
import argparse, base64, csv, datetime, json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(ROOT, "assets", "target.png")
LOG = os.path.join(ROOT, "data", "iteration_log.csv")


def run_build(mode):
    cmd = [sys.executable, os.path.join(HERE, "build_pptx.py")]
    if mode == "editable":
        cmd.append("--editable")
    subprocess.run(cmd, check=True)
    return os.path.join(ROOT, "outputs", "fig5_native_%s_v1.pptx" % ("outline" if mode == "outline" else "editable"))


def render(pptx):
    outdir = os.path.join(ROOT, ".render")
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        if f.endswith(".png"):
            os.remove(os.path.join(outdir, f))
    subprocess.run(["qlmanage", "-t", "-s", "1600", "-o", outdir, pptx],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    pngs = [f for f in os.listdir(outdir) if f.endswith(".png")]
    return os.path.join(outdir, pngs[0])


def ssim(a, b, win=5):
    from numpy.lib.stride_tricks import sliding_window_view
    a = a.astype(float); b = b.astype(float); p = win // 2
    ap = np.pad(a, p, mode="reflect"); bp = np.pad(b, p, mode="reflect")
    wa = sliding_window_view(ap, (win, win)).mean((-1, -2))
    wb = sliding_window_view(bp, (win, win)).mean((-1, -2))
    va = sliding_window_view(ap * ap, (win, win)).mean((-1, -2)) - wa * wa
    vb = sliding_window_view(bp * bp, (win, win)).mean((-1, -2)) - wb * wb
    cov = sliding_window_view(ap * bp, (win, win)).mean((-1, -2)) - wa * wb
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    return float((((2 * wa * wb + C1) * (2 * cov + C2)) / ((wa ** 2 + wb ** 2 + C1) * (va + vb + C2))).mean())


def score(png):
    ref = Image.open(TARGET).convert("RGB")
    out = Image.open(png).convert("RGB").resize(ref.size, Image.LANCZOS)
    out.save(os.path.join(ROOT, ".render", "render_latest.png"))
    a = np.asarray(ref.convert("L")).astype(float)
    b = np.asarray(out.convert("L")).astype(float)
    mse = float(((a - b) ** 2).mean())
    psnr = 10 * np.log10(255 ** 2 / mse) if mse > 0 else 99
    ab = np.asarray(ref.convert("L").filter(ImageFilter.GaussianBlur(1.2))).astype(float)
    bb = np.asarray(out.convert("L").filter(ImageFilter.GaussianBlur(1.2))).astype(float)
    return dict(ssim=ssim(a, b), ssim_blur=ssim(ab, bb), psnr=psnr,
                mae=float(np.abs(a - b).mean()))


def vlm_critique(png, round_no):
    key = os.environ.get("WEEX_API_KEY") or os.environ.get("WEEX_STG_API_KEY")
    if not key:
        print("VLM critique skipped: no WEEX key in env")
        return None
    import requests
    def b64(path):
        return base64.b64encode(open(path, "rb").read()).decode()
    prompt = (
        "You are comparing a TARGET reference figure with a RENDER of a fully vector PPTX "
        "reconstruction. List only concrete, visible discrepancies. Return strict JSON: "
        '{"issues":[{"bbox":[x0,y0,x1,y1],"severity":1-5,"what":"...","fix":"..."}],'
        '"overall":"one sentence"} . Coordinates are in the 1536x1024 target space.'
    )
    payload = {
        "model": "gpt-5.4",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64(TARGET)}},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64(png)}},
        ]}],
        "max_tokens": 1800,
    }
    r = requests.post("https://ai-gateway-stg.weex.tech/v1/chat/completions",
                      headers={"Authorization": "Bearer " + key}, json=payload, timeout=300)
    r.raise_for_status()
    txt = r.json()["choices"][0]["message"]["content"]
    path = os.path.join(ROOT, ".render", "critique_round%d.json" % round_no)
    with open(path, "w") as f:
        f.write(txt)
    print("critique ->", path)
    return txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["outline", "editable"], default="outline")
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--vlm", action="store_true")
    args = ap.parse_args()

    for i in range(1, args.rounds + 1):
        pptx = run_build(args.mode)
        png = render(pptx)
        m = score(png)
        print("round %d (%s): SSIM=%.4f blurred=%.4f PSNR=%.2f MAE=%.2f"
              % (i, args.mode, m["ssim"], m["ssim_blur"], m["psnr"], m["mae"]))
        row = [datetime.datetime.now().isoformat(timespec="seconds"), args.mode,
               round(m["ssim"], 4), round(m["ssim_blur"], 4), round(m["psnr"], 2), round(m["mae"], 2)]
        new = not os.path.exists(LOG)
        with open(LOG, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["ts", "mode", "ssim", "ssim_blur", "psnr", "mae"])
            w.writerow(row)
        if args.vlm:
            vlm_critique(png, i)


if __name__ == "__main__":
    main()
