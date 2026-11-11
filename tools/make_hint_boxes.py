#!/usr/bin/env python3
"""Recover detector-style boxes from an input clip and its erased result, and draw them on the
input as a "hint" video for the project page.

    python tools/make_hint_boxes.py --input 输入.mp4 --result 擦除结果.mp4 --out 提示.mp4 [--offset 1]

Where the result differs from the input is where something was removed. Per frame:
  |input - result| (max over RGB) > --thr          -> changed pixels
  OR over a +-1 frame window                        -> stable against wipes and flicker
  close with a wide, flat kernel                    -> characters of one line merge
  connected components larger than --min_area       -> one box per line / logo
  each box shrunk to its densely changed rows/cols  -> legs and shadows merged by the closing fall off
  drop boxes much taller than wide (a moving person, not a text line), and specks smaller than 6% of the height
  keep a box only if a box overlapping it (IoU > 0.3) appears in >= 4 of the 7 frames around it
  link boxes into tracks and replace each by its track medoid over +-4 frames (no jumping boxes)
Boxes are padded by --pad pixels and drawn as outlines on the input, in the page's hint color.
A JSON with the boxes of every frame is written next to the video.

--offset N: result frame k matches input frame k+N (the clip pairs from 后来 are one frame
apart). The hint video keeps the input's own timeline, so the page uses the same offset for the
Input and Hint rows.
Needs numpy and opencv-python.
"""
import argparse, json, subprocess
import numpy as np
import cv2

COLOR = (58, 163, 242)  # BGR of #F2A33A, the hint color used on the page


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout.strip().split("\n")[0].split(",")
    return int(out[0]), int(out[1]), out[2]


def read_all(path):
    w, h, _ = probe(path)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def boxes_of(mask, min_area, pad, W, H, min_size=0.06):
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if a < min_area or w < 6 or h < 6:
            continue
        if h > 2.2 * w and h > 40:          # tall and thin: motion around a person, not a text line
            continue
        if max(w, h) < min_size * H:        # small specks: hands, edges of moving objects
            continue
        out.append([max(0, int(x - pad)), max(0, int(y - pad)), min(W - 1, int(x + w + pad)), min(H - 1, int(y + h + pad))])
    return sorted(out, key=lambda b: (b[1], b[0]))


def tighten(b, m, pad, W, H, rel=0.35):
    """Shrink a box to the rows and columns that are densely changed: a text line is dense, a leg
    or a shadow that the closing merged into it is not."""
    x0, y0, x1, y1 = b
    sub = m[y0:y1 + 1, x0:x1 + 1].astype(np.float32)
    if sub.size == 0 or sub.max() == 0:
        return b
    rows, cols = sub.mean(1), sub.mean(0)
    r = np.where(rows > rel * rows.max())[0]; c = np.where(cols > rel * cols.max() * 0.5)[0]
    return [max(0, x0 + int(c[0]) - pad), max(0, y0 + int(r[0]) - pad),
            min(W - 1, x0 + int(c[-1]) + pad), min(H - 1, y0 + int(r[-1]) + pad)]


def track_and_smooth(per_frame, iou, win=4, min_track=5):
    """Link boxes over time and replace every box by the medoid of its track within +-win frames.

    A text line or logo stays put, so a box that jumps for a few frames (a shadow or a limb merged
    into it, a half-faded line) is an outlier: the medoid -- the box agreeing best with its
    neighbours -- ignores runs shorter than half the window, while a real change (a new lyric
    line, a dot of a countdown disappearing) wins as soon as it holds for most of the window.
    Tracks shorter than min_track frames are dropped."""
    N = len(per_frame)
    tracks = []                      # each: {frame: box}
    live = []                        # indices of tracks that had a box in the previous frame
    for j in range(N):
        nxt, used = [], set()
        for b in per_frame[j]:
            cand = [(iou(b, tracks[t][j - 1]), t) for t in live if t not in used]
            best = max(cand, default=(0, None))
            if best[0] > 0.3:
                t = best[1]
            else:
                t = len(tracks); tracks.append({})
            tracks[t][j] = b; used.add(t); nxt.append(t)
        live = nxt
    out = [[] for _ in range(N)]
    for tr in tracks:
        if len(tr) < min_track:
            continue
        for j in tr:
            near = [tr[t] for t in range(j - win, j + win + 1) if t in tr]
            med = max(near, key=lambda p: sum(iou(p, q) for q in near))
            out[j].append(list(med))
    return [sorted(bs, key=lambda b: (b[1], b[0])) for bs in out]


def drop_nested(boxes, frac=0.8):
    """Drop a box that lies (>= frac of its area) inside a larger box of the same frame:
    a line detected on its own inside a title-card block is already covered by the block."""
    area = lambda b: max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    keep = []
    for b in boxes:
        inside = False
        for q in boxes:
            if q is b or area(q) <= area(b):
                continue
            ix = max(0, min(b[2], q[2]) - max(b[0], q[0])); iy = max(0, min(b[3], q[3]) - max(b[1], q[1]))
            if ix * iy >= frac * area(b):
                inside = True; break
        if not inside:
            keep.append(b)
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--result", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--offset", type=int, default=0, help="result frame k matches input frame k+offset")
    ap.add_argument("--thr", type=int, default=32, help="per-pixel change threshold (0-255)")
    ap.add_argument("--min_area", type=int, default=150, help="ignore changed blobs smaller than this (pixels, after closing)")
    ap.add_argument("--min_size", type=float, default=0.06, help="drop boxes whose longer side is below this fraction of the height")
    ap.add_argument("--roi", default="", help="x0,y0,x1,y1 as fractions: only look for changes here (e.g. 0,0.55,1,1 for "
                    "lyrics at the bottom); keeps motion around people out of the boxes")
    ap.add_argument("--win", type=int, default=4, help="temporal smoothing: medoid over +-win frames of a track")
    ap.add_argument("--min_track", type=int, default=5, help="drop boxes that exist for fewer frames than this")
    ap.add_argument("--pad", type=int, default=4)
    ap.add_argument("--thick", type=int, default=2)
    ap.add_argument("--from_json", default=None,
                    help="reuse the boxes of an earlier run (its .json), drop nested boxes and redraw; skips detection")
    a = ap.parse_args()

    inp, res = read_all(a.input), read_all(a.result)
    N, H, W = inp.shape[:3]
    if a.from_json:
        prev = json.load(open(a.from_json, encoding="utf-8"))["boxes_xyxy"]
        frames_boxes = [drop_nested([list(map(int, q)) for q in f]) for f in prev]
        frames_boxes += [[] for _ in range(N - len(frames_boxes))]
    else:
        # changed-pixel mask in the input timeline
        change = np.zeros((N, H, W), np.uint8)
        for j in range(N):
            k = j - a.offset
            if 0 <= k < len(res):
                d = np.abs(inp[j].astype(np.int16) - res[k].astype(np.int16)).max(axis=2)
                change[j] = (d > a.thr).astype(np.uint8)
        if a.roi:
            x0, y0, x1, y1 = [float(v) for v in a.roi.split(",")]
            keep = np.zeros((H, W), np.uint8); keep[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)] = 1
            change *= keep
        # frames without a matching result frame borrow their nearest neighbour
        valid = [j for j in range(N) if 0 <= j - a.offset < len(res)]
        for j in range(N):
            if j not in valid:
                change[j] = change[min(valid, key=lambda v: abs(v - j))]

        k_open = np.ones((2, 2), np.uint8)
        k_line = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, W // 22), max(5, H // 90)))
        raw_boxes = []
        for j in range(N):
            m0 = cv2.morphologyEx(change[max(0, j - 1): j + 2].max(axis=0), cv2.MORPH_OPEN, k_open)  # drop codec noise
            m = cv2.morphologyEx(m0, cv2.MORPH_CLOSE, k_line)      # merge the characters of a line
            raw_boxes.append([tighten(b, m0, a.pad, W, H) for b in boxes_of(m, a.min_area, a.pad, W, H, a.min_size)])

        def iou(p, q):
            ix = max(0, min(p[2], q[2]) - max(p[0], q[0])); iy = max(0, min(p[3], q[3]) - max(p[1], q[1]))
            inter = ix * iy
            return inter / float((p[2] - p[0]) * (p[3] - p[1]) + (q[2] - q[0]) * (q[3] - q[1]) - inter + 1e-6)

        persistent = []
        for j in range(N):
            keep = []
            for b in raw_boxes[j]:
                seen = sum(any(iou(b, q) > 0.3 for q in raw_boxes[t]) for t in range(max(0, j - 3), min(N, j + 4)))
                if seen >= min(4, N):
                    keep.append(b)
            persistent.append(keep)
        frames_boxes = track_and_smooth(persistent, iou, a.win, a.min_track)
        frames_boxes = [drop_nested(b) for b in frames_boxes]

    w, h, fps = probe(a.input)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", fps, "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                            "-pix_fmt", "yuv420p", a.out], stdin=subprocess.PIPE)
    for j in range(N):
        img = inp[j].copy()
        for x0, y0, x1, y1 in frames_boxes[j]:
            cv2.rectangle(img, (x0, y0), (x1, y1), COLOR, a.thick, lineType=cv2.LINE_AA)
        enc.stdin.write(img.tobytes())
    enc.stdin.close(); enc.wait()
    js = a.out.rsplit(".", 1)[0] + ".json"
    json.dump({"input": a.input, "result": a.result, "offset": a.offset, "width": W, "height": H,
               "boxes_xyxy": frames_boxes}, open(js, "w", encoding="utf-8"))
    nb = [len(b) for b in frames_boxes]
    print(f"{a.out}: {N} frames, boxes per frame min/mean/max {min(nb)}/{np.mean(nb):.1f}/{max(nb)}; boxes in {js}")


if __name__ == "__main__":
    main()
