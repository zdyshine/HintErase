#!/usr/bin/env python3
"""Build the media and manifest for the HintErase project page.

    python tools/build_site.py cases.json            # -> docs/media/*, docs/manifest.js
    python tools/build_site.py cases.json --only ktv-wipe --force

For every case, all rows (Input, Hint, HintErase, ablations ...) are trimmed to
the same span, resampled to one frame rate and size, and stacked vertically
into ONE H.264 file.  The page draws two rows of that file side by side on a
canvas, so the compared videos can never drift out of sync and only one
decoder runs per player.

cases.json
{
  "placeholder": false,                # true shows a "placeholder clips" banner
  "hero": "ktv-wipe",                  # case shown in the opening player
  "defaults": {"max_side": 854, "crf": 26, "fps": null},
  "cases": [
    {"id": "ktv-wipe", "category": "karaoke", "title": "...", "note": "...",
     "title_zh": "...", "note_zh": "...",                       # optional Chinese for the zh page
     "start": 12.0, "duration": 8, "src_frame": 13200,          # src_frame: frame number in the full source (shown as timecode)
     "left": "Input", "right": "HintErase",                    # default pair (optional)
     "rows": [
        {"label": "Input",     "path": "raw/ktv/input.mp4"},
        {"label": "Hint",      "path": "raw/ktv/input.mp4", "mask": "raw/ktv/hint_raw.mkv"},
        {"label": "HintErase", "path": "raw/ktv/ours.mp4"},
        {"label": "Hole",      "path": "raw/ktv/hole.mp4"}]}
  ]
}
Rows with "mask" are rendered as the input with the mask tinted on top.
A row may carry "offset": N to start N frames later than the other rows (to fix clips
exported one frame apart).  A case with "gallery": false is built for the opening player
only and does not appear in the gallery.  All
row videos must be frame-aligned with the input (same start frame).
"""
import argparse, hashlib, json, os, re, subprocess, sys
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "docs")
MEDIA = os.path.join(SITE, "media")

# Order and wording of the gallery tabs: (id, English label, English blurb, Chinese label, Chinese blurb).
CATEGORIES = [
    ("subtitles", "Subtitles", "Burned-in dialogue, single or bilingual, in any position.",
     "字幕", "硬字幕对白，单语或双语，位置不限。"),
    ("karaoke", "Karaoke lyrics", "Per-character color wipes with outlines that change mid-line.",
     "卡拉OK歌词", "逐字变色，描边在一行中途改变颜色。"),
    ("titles", "Title cards", "Opening title cards: song titles, credits and logos, often fading in and out.",
     "片头标题", "片头标题卡：歌名、演职信息和标志，常带淡入淡出。"),
    ("logos", "Logos & watermarks", "Persistent station marks and translucent watermarks.",
     "台标与水印", "常驻的台标和半透明水印。"),
    ("anime", "Anime & low-res", "Low-resolution animation with thin outlined subtitles and lyrics.",
     "动画与低分辨率", "低分辨率动画上带描边的细字幕和歌词。"),
    ("credits", "End credits", "Credit lines over the closing scenes of an episode.",
     "片尾演职员表", "剧集片尾画面上的演职员信息。"),
    ("uhd", "Ultra-HD delivery", "Old low-resolution footage, erased and then upscaled 4x by our in-house super-resolution model.",
     "超高清交付", "低分辨率老片擦除后，经自研超分模型放大 4 倍交付。"),
    ("long", "Long videos", "Minutes-long, multi-shot runs processed as one release.",
     "长视频", "长达数分钟的多镜头片段，按完整成片一次处理。"),
    ("hints", "Imperfect hints", "Boxes that over-cover, masks that miss strokes.",
     "不准确的提示", "多盖住背景的框、漏掉笔画的 mask。"),
    ("failures", "Limitations", "Cases that still leave residue.",
     "局限", "仍会留下残留的情况。"),
]
MAX_STACK = 4096          # keep the stacked frame inside what browsers decode in hardware
HINT_COLOR = "0xF2A33A"   # tint used to draw masks on the Hint row


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"[ffmpeg failed] {' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r.stdout


def probe(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height,r_frame_rate,nb_frames:format=duration", "-of", "json", path])
    j = json.loads(out)
    s = j["streams"][0]
    return int(s["width"]), int(s["height"]), Fraction(s["r_frame_rate"]), float(j["format"].get("duration", 0))


def even(x):
    return max(2, int(round(x / 2)) * 2)


def build_case(c, d, force):
    rows = c["rows"]
    for r in rows:
        for k in ("path", "mask"):
            if k in r and not os.path.exists(r[k]):
                sys.exit(f"[{c['id']}] missing {k}: {r[k]}")
    w, h, fps, dur0 = probe(rows[0]["path"])
    fps = Fraction(d["fps"]).limit_denominator(1001) if d.get("fps") else fps
    start = float(c.get("start", 0))
    dur = float(c.get("duration", dur0 - start))
    for r in rows:
        dur = min(dur, probe(r["path"])[3] - start - r.get("offset", 0) / float(fps))
        if "mask" in r:
            dur = min(dur, probe(r["mask"])[3] - start)
    if dur <= 0:
        sys.exit(f"[{c['id']}] start {start}s is past the end of a row")
    frames = int(round(dur * fps))   # round: dur*fps can land just below an integer

    side = c.get("max_side", d.get("max_side", 854))
    s = min(1.0, side / max(w, h))
    rw, rh = even(w * s), even(h * s)
    if rh * len(rows) > MAX_STACK:
        k = MAX_STACK / (rh * len(rows))
        rw, rh = even(rw * k), even(rh * k)

    out = os.path.join(MEDIA, f"{c['id']}.mp4")
    poster = os.path.join(MEDIA, f"{c['id']}.jpg")
    thumb = os.path.join(MEDIA, f"{c['id']}_thumb.jpg")
    # Chinese text does not change the video, so editing it must not trigger a re-encode.
    kc = {k: v for k, v in c.items() if k not in ("title_zh", "note_zh")}
    # a source file replaced under the same name (e.g. a regenerated hint video) must also change the key,
    # both to trigger a rebuild and to change the ?v= that keeps browsers from showing the cached clip
    kc["_files"] = [[os.path.getsize(f), int(os.path.getmtime(f))] for r in rows for f in (r["path"], r.get("mask")) if f]
    key = hashlib.sha1(json.dumps([kc, d, rw, rh, str(fps)], sort_keys=True).encode()).hexdigest()[:12]
    stamp = out + ".key"
    if not force and os.path.exists(out) and os.path.exists(stamp) and open(stamp).read() == key:
        print(f"[skip] {c['id']} (unchanged)")
    else:
        cmd, filt, labels, n = ["ffmpeg", "-y", "-loglevel", "error"], [], [], 0
        base = f"fps={fps},scale={rw}:{rh}:flags=lanczos,setsar=1"
        for j, r in enumerate(rows):
            # "offset": N frames to skip in this row only, for clips that start a few frames apart
            rs = start + r.get("offset", 0) / float(fps)
            cmd += ["-ss", f"{rs:.3f}", "-t", f"{dur + 1:.3f}", "-i", r["path"]]
            vi = n; n += 1
            if "mask" in r:
                cmd += ["-ss", f"{rs:.3f}", "-t", f"{dur + 1:.3f}", "-i", r["mask"]]
                mi = n; n += 1
                filt += [f"[{vi}:v]{base},format=rgba[b{j}]",
                         f"[{mi}:v]{base},format=gray,lut=y=val*0.62[a{j}]",
                         f"color=c={HINT_COLOR}:s={rw}x{rh}:r={fps},format=rgba[c{j}]",
                         f"[c{j}][a{j}]alphamerge[o{j}]",
                         f"[b{j}][o{j}]overlay=shortest=1,format=yuv420p[r{j}]"]
            else:
                filt.append(f"[{vi}:v]{base},format=yuv420p[r{j}]")
            labels.append(f"[r{j}]")
        filt.append(f"{''.join(labels)}vstack=inputs={len(rows)}[v]" if len(rows) > 1 else f"{labels[0]}null[v]")
        cmd += ["-filter_complex", ";".join(filt), "-map", "[v]", "-frames:v", str(frames),
                "-c:v", "libx264", "-preset", "slow", "-crf", str(d.get("crf", 26)), "-g", str(round(fps)),
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", out]
        run(cmd)
        mid = f"{dur / 2:.3f}"
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", mid, "-i", out, "-frames:v", "1", "-q:v", "4", poster])
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", mid, "-i", out, "-frames:v", "1",
             "-vf", f"crop={rw}:{rh}:0:0,scale=360:-2", "-q:v", "5", thumb])
        open(stamp, "w").write(key)
        mb = os.path.getsize(out) / 1e6
        print(f"[ok]   {c['id']}: {len(rows)} rows {rw}x{rh}, {frames} frames @ {float(fps):.3f} fps, {mb:.1f} MB"
              + ("   <-- over 50 MB, raise crf or shorten" if mb > 50 else ""))

    labs = [r["label"] for r in rows]
    entry = {
        "id": c["id"], "category": c["category"], "title": c["title"], "note": c.get("note", ""),
        # ?v=<key> changes whenever the clip is rebuilt, so browsers never show a cached old video
        "video": f"media/{c['id']}.mp4?v={key}", "poster": f"media/{c['id']}.jpg?v={key}",
        "thumb": f"media/{c['id']}_thumb.jpg?v={key}",
        "w": rw, "h": rh, "fps": float(fps), "frames": frames, "rows": labs,
        "left": c.get("left", labs[0]),
        "right": c.get("right", "HintErase" if "HintErase" in labs else labs[-1]),
        "src_frame": int(c.get("src_frame", round(start * float(fps)))),
    }
    if c.get("gallery") is False:  # e.g. a clip shown only in the opening player
        entry["gallery"] = False
    for k in ("title_zh", "note_zh"):  # optional Chinese text; the page falls back to English
        if c.get(k):
            entry[k] = c[k]
    return entry


def bump_versions():
    """Append ?v=<content hash> to the css/js links in index.html, so a rebuilt page is never
    mixed with cached old files (python http.server and GitHub Pages both let browsers cache)."""
    p = os.path.join(SITE, "index.html")
    html = open(p, encoding="utf-8").read()
    for name in ("style.css", "i18n.js", "manifest.js", "app.js"):
        v = hashlib.sha1(open(os.path.join(SITE, name), "rb").read()).hexdigest()[:8]
        html = re.sub(r'(["\'])' + re.escape(name) + r'(\?v=[0-9a-f]+)?\1', rf'\g<1>{name}?v={v}\1', html)
    open(p, "w", encoding="utf-8").write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases")
    ap.add_argument("--only", nargs="*", help="build only these case ids (manifest still lists all built cases)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    cfg = json.load(open(a.cases))
    d = cfg.get("defaults", {})
    os.makedirs(MEDIA, exist_ok=True)
    known = {cat[0] for cat in CATEGORIES}
    entries = []
    for c in cfg["cases"]:
        if c["category"] not in known:
            sys.exit(f"[{c['id']}] unknown category {c['category']}; add it to CATEGORIES")
        if a.only and c["id"] not in a.only:
            if os.path.exists(os.path.join(MEDIA, c["id"] + ".mp4")):
                entries.append(build_case(c, d, False))
            continue
        entries.append(build_case(c, d, a.force))
    used = {e["category"] for e in entries if e.get("gallery", True)}
    manifest = {
        "placeholder": bool(cfg.get("placeholder")),
        "hero": cfg.get("hero") or (entries[0]["id"] if entries else None),
        "overview_video": cfg.get("overview_video", {}),
        "uhd": cfg.get("uhd"),                 # case shown in the standalone Ultra-HD section
        "categories": [{"id": k, "label": l, "blurb": b, "label_zh": lz, "blurb_zh": bz}
                       for k, l, b, lz, bz in CATEGORIES if k in used],
        "cases": entries,
    }
    with open(os.path.join(SITE, "manifest.js"), "w") as f:
        f.write("// Generated by tools/build_site.py. Do not edit by hand.\n")
        f.write("window.HINTERASE_MANIFEST = " + json.dumps(manifest, ensure_ascii=False, indent=1) + ";\n")
    hero = next((e for e in entries if e["id"] == manifest["hero"]), None)
    if hero:  # social preview image: left half input, right half result
        w, h = hero["w"], hero["h"]
        li, ri = hero["rows"].index(hero["left"]), hero["rows"].index(hero["right"])
        half = w // 2
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(SITE, hero["poster"].split("?")[0]), "-filter_complex",
             f"[0]crop={half}:{h}:0:{li*h}[a];[0]crop={w-half}:{h}:{half}:{ri*h}[b];[a][b]hstack,drawbox=x={half-1}:y=0:w=2:h={h}:color=white:t=fill",
             "-q:v", "4", os.path.join(MEDIA, "og.jpg")])
    open(os.path.join(SITE, ".nojekyll"), "w").close()
    bump_versions()
    total = sum(os.path.getsize(os.path.join(MEDIA, x)) for x in os.listdir(MEDIA) if not x.endswith(".key")) / 1e6
    print(f"\nmanifest: {len(entries)} cases, docs/media = {total:.0f} MB"
          + ("   <-- GitHub Pages sites should stay under 1 GB" if total > 800 else ""))


if __name__ == "__main__":
    main()
