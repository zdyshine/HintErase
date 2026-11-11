#!/usr/bin/env python3
"""Cut the report's figure images out of the web page's case videos, so the
report and the page always show the same results.

    python tools/make_figures.py ../hinterase_report/figures/figures.json

Reads docs/manifest.js and docs/media/<case>.mp4 (built by build_site.py) and
writes, next to figures.json, img/<case>__<label>.jpg cells that the LaTeX
figures include by name.  figures.json:

{
  "frames": [  # one still per label; "t" in seconds or "mid"
    {"case": "ktv-wipe", "t": "mid", "labels": ["Input", "HintErase"]}
  ],
  "zooms": [   # still + a magnified crop (box = x0,y0,x1,y1 as fractions of the frame)
    {"case": "sub-bilingual", "t": 2.0, "box": [0.25, 0.72, 0.75, 0.98],
     "labels": ["Input", "HintErase", "ProPainter"]}
  ],
  "slices": [  # time slice: one pixel column at x (fraction), rows y0..y1, frames left to right
    {"case": "long-multishot", "x": 0.5, "y0": 0.6, "y1": 1.0, "px_per_frame": 3,
     "labels": ["HintErase", "Independent windows"]}
  ]
}
"""
import json, os, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "docs")


def manifest():
    txt = open(os.path.join(SITE, "manifest.js"), encoding="utf-8").read()
    return json.loads(txt[txt.index("{"): txt.rindex("}") + 1])


def slug(label):
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def decode(case, t=None):
    """All frames (t=None) or one frame at t seconds, full stacked height, as uint8 [N,H,W,3]."""
    w, h = case["w"], case["h"] * len(case["rows"])
    cmd = ["ffmpeg", "-loglevel", "error"]
    if t is not None:
        cmd += ["-ss", f"{t:.3f}"]
    cmd += ["-i", os.path.join(SITE, case["video"].split("?")[0])]
    if t is not None:
        cmd += ["-frames:v", "1"]
    cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def row(frame, case, label):
    if label not in case["rows"]:
        print(f"  [warn] {case['id']}: no row '{label}' (has {case['rows']}); skipped")
        return None
    i, h = case["rows"].index(label), case["h"]
    return frame[i * h:(i + 1) * h]


def when(case, t):
    return case["frames"] / case["fps"] / 2 if t in (None, "mid") else float(t)


def main():
    cfg_path = sys.argv[1]
    out = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), "img")
    os.makedirs(out, exist_ok=True)
    cfg = json.load(open(cfg_path))
    cases = {c["id"]: c for c in manifest()["cases"]}

    def get(cid):
        if cid not in cases:
            sys.exit(f"case '{cid}' is not in docs/manifest.js; build it with build_site.py first")
        return cases[cid]

    for f in cfg.get("frames", []):
        c = get(f["case"]); fr = decode(c, when(c, f.get("t")))[0]
        for lab in f["labels"]:
            r = row(fr, c, lab)
            if r is not None:
                p = os.path.join(out, f"{c['id']}__{slug(lab)}.jpg")
                Image.fromarray(r).save(p, quality=92); print("  wrote", os.path.relpath(p))

    for z in cfg.get("zooms", []):
        c = get(z["case"]); fr = decode(c, when(c, z.get("t")))[0]
        x0, y0, x1, y1 = z["box"]
        for lab in z["labels"]:
            r = row(fr, c, lab)
            if r is None:
                continue
            H, W = r.shape[:2]
            box = (int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))
            full = Image.fromarray(r).copy()
            ImageDraw.Draw(full).rectangle(box, outline=(242, 163, 58), width=3)
            full.save(os.path.join(out, f"{c['id']}__{slug(lab)}.jpg"), quality=92)
            crop = Image.fromarray(r).crop(box)
            crop = crop.resize((crop.width * 3, crop.height * 3), Image.NEAREST)
            p = os.path.join(out, f"{c['id']}__{slug(lab)}__zoom.jpg")
            crop.save(p, quality=92); print("  wrote", os.path.relpath(p))

    for s in cfg.get("slices", []):
        c = get(s["case"]); frames = decode(c)
        k = s.get("px_per_frame", 3)
        for lab in s["labels"]:
            if lab not in c["rows"]:
                row(frames[0], c, lab); continue
            i, h = c["rows"].index(lab), c["h"]
            x = int(s["x"] * c["w"])
            ya, yb = i * h + int(s["y0"] * h), i * h + int(s["y1"] * h)
            col = frames[:, ya:yb, x, :]                     # [N, band, 3]
            img = np.repeat(col.transpose(1, 0, 2), k, axis=1)  # band x (N*k)
            p = os.path.join(out, f"{c['id']}__{slug(lab)}__slice.jpg")
            Image.fromarray(img).save(p, quality=92); print("  wrote", os.path.relpath(p))


if __name__ == "__main__":
    main()
