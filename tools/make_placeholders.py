#!/usr/bin/env python3
"""Generate synthetic placeholder clips so the site can be built and previewed
before real results are ready.  Every frame carries a "PLACEHOLDER" tag.

    python tools/make_placeholders.py --out raw_placeholder

Writes, per case, <case>/{input,ours,mask,...}.mp4 and prints a cases.json
that build_site.py can consume directly.
"""
import argparse, json, math, os, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, SEC = 854, 480, 24, 6
N = FPS * SEC
FONT_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def font(size):
    try:
        return ImageFont.truetype(FONT_CJK, size)
    except OSError:
        return ImageFont.load_default()


class Writer:
    def __init__(self, path, w=W, h=H):
        self.p = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "16",
             "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)

    def write(self, img):
        self.p.stdin.write(np.asarray(img.convert("RGB"), dtype=np.uint8).tobytes())

    def close(self):
        self.p.stdin.close(); self.p.wait()


yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)


def scene(t, kind="dusk", shot=0):
    """Procedural background: gradient sky + drifting blobs + ground."""
    pal = {
        "dusk":  ((38, 52, 96), (236, 150, 98), (40, 34, 48)),
        "sea":   ((40, 110, 160), (180, 220, 235), (30, 70, 90)),
        "anime": ((120, 190, 240), (250, 240, 220), (110, 170, 90)),
        "flat":  ((70, 74, 82), (88, 92, 100), (60, 62, 70)),
        "room":  ((60, 48, 40), (200, 170, 130), (90, 70, 55)),
    }[kind]
    if shot:  # alternate shot = shifted palette
        pal = tuple(tuple(int(c * 0.75 + 40) for c in col) for col in pal)
    top, mid, gnd = (np.array(c, np.float32) for c in pal)
    g = (yy / H)[..., None]
    img = top * (1 - g) + mid * g
    hor = H * 0.68
    img = np.where((yy > hor)[..., None], gnd + (yy[..., None] - hor) * 0.08, img)
    for i in range(5):
        cx = (W * (0.15 + 0.2 * i) + t * (18 + 9 * i) * (1 if i % 2 else -1)) % (W + 200) - 100
        cy = H * (0.25 + 0.08 * math.sin(i * 1.7 + t * 0.6))
        r = 50 + 18 * i
        d = ((xx - cx) ** 2 + (yy - cy) ** 2) / (r * r)
        a = np.exp(-d * 1.5)[..., None] * (0.35 if kind != "flat" else 0.08)
        img = img * (1 - a) + 255 * a
    for i in range(7):  # silhouettes / props in the lower half
        x0 = int((i * 140 + t * 30 * (1 + shot)) % (W + 140)) - 70
        h0 = int(60 + 40 * math.sin(i * 2.3))
        img[int(hor) - h0:int(hor), max(0, x0):max(0, x0 + 60)] *= 0.55
    if kind == "anime":  # posterize for a cel look
        img = (img // 32) * 32 + 16
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def tag(img):
    d = ImageDraw.Draw(img)
    d.rectangle((10, 10, 128, 30), fill=(0, 0, 0))
    d.text((16, 12), "PLACEHOLDER", font=font(13), fill=(255, 200, 80))
    return img


def text_layer(draw_fn):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer), layer)
    return layer


def subtitle(d, lines, y0, size=30, fill=(255, 255, 255), stroke=(0, 0, 0)):
    f = font(size)
    y = y0
    for ln in lines:
        w = d.textlength(ln, font=f)
        d.text(((W - w) / 2, y), ln, font=f, fill=fill, stroke_width=3, stroke_fill=stroke)
        y += size + 8


def mask_of(layer, dilate=7):
    a = layer.split()[-1].point(lambda v: 255 if v > 20 else 0)
    return a.filter(ImageFilter.MaxFilter(dilate)).convert("RGB")


def box_mask(layer, pad=10):
    bb = layer.split()[-1].getbbox()
    m = Image.new("RGB", (W, H))
    if bb:
        ImageDraw.Draw(m).rectangle((bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad), fill=(255, 255, 255))
    return m


def smear(clean, mask, k, strength=1.0):
    """Fake baseline artifact: blurry, slightly flickering fill inside the mask."""
    blur = clean.filter(ImageFilter.GaussianBlur(9 + 3 * math.sin(k * 0.9)))
    tint = Image.new("RGB", (W, H), (128, 120, 110))
    fill = Image.blend(blur, tint, 0.25 * strength)
    return Image.composite(fill, clean, mask.convert("L"))


CASES = []


def case(cid, cat, title, note, kind, overlay_fn, extra=None, shots=False, hint="mask"):
    CASES.append(dict(id=cid, cat=cat, title=title, note=note, kind=kind, fn=overlay_fn,
                      extra=extra or [], shots=shots, hint=hint))


# ---------------------------------------------------------------- overlays
def ov_subtitle(k, d, layer):
    i = (k // 48) % 3
    zh = ["我们明天一早就出发", "海上的风比想象中大", "别回头，一直往前走"][i]
    en = ["We leave first thing tomorrow", "The wind at sea is stronger", "Don't look back, keep going"][i]
    subtitle(d, [zh, en], H - 100, size=28)


def ov_karaoke(k, d, layer):
    f = font(36)
    line = "月光洒在 我们走过的路上"
    w = d.textlength(line, font=f)
    x0, y0 = (W - w) / 2, H - 90
    d.text((x0, y0), line, font=f, fill=(255, 255, 255), stroke_width=3, stroke_fill=(30, 30, 120))
    prog = (k % N) / N
    hi = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(hi).text((x0, y0), line, font=f, fill=(255, 90, 160), stroke_width=3, stroke_fill=(255, 255, 255))
    cut = int(x0 + w * prog)
    layer.alpha_composite(hi.crop((0, 0, cut, H)), (0, 0))


def ov_title(k, d, layer):
    a = min(1, k / 24) * min(1, (N - k) / 24)
    f = font(64)
    t = "第 十 八 章"
    w = d.textlength(t, font=f)
    d.text(((W - w) / 2, H * 0.36), t, font=f, fill=(255, 236, 190, int(255 * a)),
           stroke_width=4, stroke_fill=(90, 40, 10, int(255 * a)))
    f2 = font(22)
    s = "CHAPTER EIGHTEEN · THE CROSSING"
    w2 = d.textlength(s, font=f2)
    d.text(((W - w2) / 2, H * 0.36 + 82), s, font=f2, fill=(255, 255, 255, int(220 * a)))


def ov_credits(k, d, layer):
    f = font(24)
    names = ["导演  林远", "编剧  陈岚", "摄影  周启明", "剪辑  何晴", "作曲  宋一川",
             "美术  吴卓", "录音  黄立", "制片  许安", "出品  远山影业"]
    y = H - k * 2.2
    for i, n in enumerate(names):
        w = d.textlength(n, font=f)
        d.text((W * 0.62 - w / 2, y + i * 54), n, font=f, fill=(255, 220, 140), stroke_width=2, stroke_fill=(20, 20, 20))


def ov_logo(k, d, layer):
    d.rounded_rectangle((W - 150, 22, W - 24, 62), 8, outline=(255, 255, 255, 200), width=3)
    d.text((W - 138, 28), "STUDIO", font=font(22), fill=(255, 255, 255, 200))
    d.text((26, H - 44), "© demo-watermark", font=font(18), fill=(255, 255, 255, 110))


def ov_anime(k, d, layer):
    i = (k // 60) % 2
    subtitle(d, [["喂——等等我！", "这次一定要赢"][i]], H - 72, size=26, fill=(255, 255, 255), stroke=(40, 40, 40))


def ov_multi(k, d, layer):
    ov_subtitle(k, d, layer)
    d.text((24, 22), "LIVE  第3场", font=font(22), fill=(255, 255, 255), stroke_width=2, stroke_fill=(200, 30, 30))


def ov_blur(k, d, layer):
    f = font(30)
    x = 40 + k * 4
    for j in range(6):
        d.text((x - j * 6, H - 100), "快速移动的字幕 Motion", font=f, fill=(255, 255, 255, 60), stroke_width=2,
               stroke_fill=(0, 0, 0, 40))


case("sub-bilingual", "subtitles", "Bilingual subtitles", "Two-line burned-in subtitles over a moving dusk scene.", "dusk", ov_subtitle)
case("sub-multi", "subtitles", "Subtitles plus a live badge", "Two overlays in different regions; one hint covers both.", "sea", ov_multi)
case("ktv-wipe", "karaoke", "Karaoke lyrics with color wipe", "Per-character color sweep; the outline changes color mid-line.", "room", ov_karaoke)
case("title-card", "titles", "Fading title card", "Large display type that fades in and out over the shot.", "dusk", ov_title)
case("credits-roll", "titles", "Rolling end credits", "Credits scrolling over live footage, tracked by a scroll-aware mask.", "sea", ov_credits)
case("logo-corner", "logos", "Corner logo and watermark", "A persistent station logo plus a translucent watermark.", "room", ov_logo)
case("anime-480", "anime", "480p anime dialogue", "Low-resolution cel-shaded source with outlined dialogue.", "anime", ov_anime)
case("long-multishot", "long", "Multi-shot sequence", "Hard cuts every two seconds. Compare against independently processed windows.", "dusk", ov_subtitle,
     extra=["Independent windows"], shots=True)
case("hint-box", "hints", "Loose box hint", "The hint is a rough box. Background inside the box must survive.", "flat", ov_subtitle, hint="box")
case("hint-missed", "hints", "Hint misses strokes", "The hint drops the second line. HintErase still removes it.", "dusk", ov_subtitle, hint="partial")
case("fail-blur", "failures", "Heavy motion blur", "Fast, blurred text leaves faint residue. A known limitation.", "dusk", ov_blur)


def render(c, out):
    os.makedirs(out, exist_ok=True)
    names = ["input", "ours", "mask"] + [e.lower().replace(" ", "_").replace("-", "_") for e in c["extra"]]
    ws = {n: Writer(os.path.join(out, n + ".mp4")) for n in names}
    for k in range(N):
        t = k / FPS
        shot = ((k // 48) % 2) if c["shots"] else 0
        clean = scene(t, c["kind"], shot)
        layer = text_layer(lambda d, l: c["fn"](k, d, l))
        inp = clean.copy().convert("RGBA"); inp.alpha_composite(layer); inp = inp.convert("RGB")
        if c["hint"] == "box":
            m = box_mask(layer, pad=26)
        elif c["hint"] == "partial":
            m = mask_of(layer); ImageDraw.Draw(m).rectangle((0, H - 62, W, H), fill=(0, 0, 0))
        else:
            m = mask_of(layer)
        ws["input"].write(tag(inp)); ws["mask"].write(m); ws["ours"].write(tag(clean.copy()))
        full = mask_of(layer, 11)
        for e, n in zip(c["extra"], names[3:]):
            if e == "Independent windows":
                jit = clean.point(lambda v: min(255, int(v * (1.0 + 0.06 * ((k // 16) % 2)))))
                ws[n].write(tag(Image.composite(jit, clean, full.convert("L"))))
            else:
                ws[n].write(tag(smear(clean, full, k, 1.0 + 0.4 * names.index(n))))
    for w in ws.values():
        w.close()
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="raw_placeholder")
    ap.add_argument("--json", default="cases.placeholder.json")
    a = ap.parse_args()
    cases = []
    for c in CASES:
        d = os.path.join(a.out, c["id"])
        names = render(c, d)
        rows = [{"label": "Input", "path": f"{d}/input.mp4"},
                {"label": "Hint", "path": f"{d}/input.mp4", "mask": f"{d}/mask.mp4"},
                {"label": "HintErase", "path": f"{d}/ours.mp4"}]
        rows += [{"label": e, "path": f"{d}/{n}.mp4"} for e, n in zip(c["extra"], names[3:])]
        cases.append(dict(id=c["id"], category=c["cat"], title=c["title"], note=c["note"], rows=rows,
                          start=0, duration=SEC, src_frame=1200 + 37 * len(cases)))
        print("rendered", c["id"])
    json.dump({"placeholder": True, "cases": cases}, open(a.json, "w"), ensure_ascii=False, indent=2)
    print("wrote", a.json)


if __name__ == "__main__":
    main()
