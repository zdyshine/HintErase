#!/usr/bin/env python3
"""Cut frame-exact clips for every case and write the cases.json that build_site.py reads.

    python tools/cut_clips.py clips.json              # -> raw/<case>/*.mkv, cases.json
    python tools/cut_clips.py clips.json --only ktv-wipe

Why: results are full-length videos, sources may be interlaced MPEG-2, and masks are separate
files. Cutting by frame number (not by seconds) on every row guarantees that Input, Hint and
results stay frame-aligned, and `vf` lets the Input row get the same deinterlacing the
pipeline applied (longvideo uses yadif mode=0, parity tff, interlaced frames only).

clips.json
{
  "out_json": "cases.json",               # written for build_site.py
  "top": {...},                           # copied into cases.json (placeholder, hero, defaults, overview_video)
  "cases": [
    {"id": "ktv-wipe", "category": "karaoke", "title": "...", "note": "...", "title_zh": "...", "note_zh": "...",
     "start_frame": 660, "frames": 240,      # same frame range on every row
     "left": "Input", "right": "HintErase",
     "rows": [
       {"label": "Input",     "path": "../../测试样例/KTV/补充资料/后来.mpg", "vf": "yadif=0:0:0"},
       {"label": "Hint",      "path": "<same as Input>", "vf": "yadif=0:0:0", "mask": "../../测试样例/KTV/补充资料/后来_mask.mp4"},
       {"label": "HintErase", "path": "../../测试样例/KTV/后来_A_mask_visible_step-15000.mp4"}]}
  ]
}
Clips are written losslessly enough for a second encode (x264 crf 14); masks as FFV1 gray.
"""
import argparse, json, os, re, subprocess, sys
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "row"


def fps_of(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=r_frame_rate", "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return Fraction(out.strip().split("\n")[0])


def cut(src, dst, s, n, vf="", mask=False):
    """Frames s .. s+n-1 of src (counted after vf), re-timed from zero."""
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return
    chain = ",".join(x for x in [vf, f"select='between(n\\,{s}\\,{s + n - 1})'", "setpts=N/(FRAME_RATE*TB)"] if x)
    enc = (["-pix_fmt", "gray", "-c:v", "ffv1"] if mask
           else ["-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "14"])
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", chain, "-frames:v", str(n), "-an", *enc, dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"[ffmpeg failed] {' '.join(cmd)}\n{r.stderr[-1500:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    os.chdir(ROOT)
    spec = json.load(open(a.spec, encoding="utf-8"))
    cases = []
    for c in spec["cases"]:
        s, n = int(c["start_frame"]), int(c["frames"])
        d = os.path.join("raw", c["id"])
        os.makedirs(d, exist_ok=True)
        rows, fps, done = [], None, {}
        for r in c["rows"]:
            if not os.path.exists(r["path"]):
                sys.exit(f"[{c['id']}] missing {r['path']}")
            f = fps_of(r["path"])
            fps = fps or f
            if abs(float(f) - float(fps)) > 0.01:
                sys.exit(f"[{c['id']}] {r['label']} runs at {float(f):.3f} fps, Input at {float(fps):.3f}")
            src_key = (r["path"], r.get("vf", ""))
            p = done.get(src_key) or os.path.join(d, slug(r["label"]) + ".mkv")   # Hint reuses the Input clip
            if src_key not in done and (not a.only or c["id"] in a.only):
                cut(r["path"], p, s, n, r.get("vf", ""))
            done[src_key] = p
            row = {"label": r["label"], "path": p.replace(os.sep, "/")}
            if "mask" in r:
                m = os.path.join(d, slug(r["label"]) + "_mask.mkv")
                if not a.only or c["id"] in a.only:
                    cut(r["mask"], m, s, n, mask=True)
                row["mask"] = m.replace(os.sep, "/")
            rows.append(row)
        out = {k: c[k] for k in ("id", "category", "title", "note", "title_zh", "note_zh", "left", "right", "max_side") if k in c}
        out.update(rows=rows, start=0, duration=round(n / float(fps), 3), src_frame=s)
        cases.append(out)
        print(f"[ok] {c['id']}: frames {s}-{s + n - 1} ({n / float(fps):.1f}s), {len(rows)} rows")
    cfg = dict(spec.get("top", {}))
    cfg["cases"] = cases
    open(spec.get("out_json", "cases.json"), "w", encoding="utf-8").write(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    print("wrote", spec.get("out_json", "cases.json"))


if __name__ == "__main__":
    main()
