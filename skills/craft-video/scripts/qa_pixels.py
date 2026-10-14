#!/usr/bin/env python3
"""qa_pixels.py VIDEO --scale S [--palette NAME|FILE] [--frames 24] [--tol 24] [--colors N]: is this really pixel art at S times its logical size?

  grid      the share of S x S blocks whose pixels are all one colour (every channel within --tol levels), over --frames frames spread across the video.
            PASS from 99%. A smaller share means something blurred or shifted the pixels: a sprite at a half-pixel position, CSS scaling by a non-integer factor, a
            smooth easing on a pixel layer, an odd S with 4:2:0 chroma (measured: S=3 keeps 50% of the blocks, S=5 44%, even S keeps all), or the grid not starting at
            the frame's corner. On a FAIL it looks for the grid's real phase and for another scale that fits, and says so.
  colours   without a palette: how many distinct colours the blocks use (the colour at each block's centre, 5 bits a channel, those covering 99.5% of the blocks).
            PASS up to --colors (default 64).
  palette   with --palette: the share of blocks within --tol of a palette colour, which is the stricter test. PASS from 99%.
Needs ffmpeg and numpy. Exit 1 on any FAIL. --palette is a name from pixel/palettes.json, a .hex file (one colour a line) or a PNG."""
import argparse, json, os, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def palette(spec):
    if not spec: return None
    if os.path.isfile(spec):
        if spec.lower().endswith(".png"):
            from PIL import Image
            return np.unique(np.asarray(Image.open(spec).convert("RGB")).reshape(-1, 3), axis=0).astype(np.int16)
        cols = [l.strip().lstrip("#") for l in open(spec) if l.strip() and not l.startswith(("//", ";"))]
    else:
        pf = os.path.join(HERE, "..", "pixel", "palettes.json")
        data = json.load(open(pf)) if os.path.exists(pf) else {}
        if spec not in data: sys.exit(f"qa_pixels: no palette '{spec}' (known: {', '.join(sorted(data)) or 'none'}); pass a .hex or .png file")
        cols = [c.lstrip("#") for c in data[spec]["colors"]]
    return np.array([[int(c[i:i + 2], 16) for i in (0, 2, 4)] for c in cols], np.int16)


def frames(path, n, w, h):
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip() or 0)
    rate = max(n / max(dur, 0.1), 0.01)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-an", "-vf", f"fps={rate:.5f}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    out = []
    while len(out) < n:
        raw = p.stdout.read(w * h * 3)
        if len(raw) < w * h * 3: break
        out.append(np.frombuffer(raw, np.uint8).reshape(h, w, 3))
    p.stdout.close(); p.kill(); p.wait()
    return out


def uniform(img, s, dx=0, dy=0, tol=24):
    h, w = (img.shape[0] - dy) // s * s, (img.shape[1] - dx) // s * s
    b = img[dy:dy + h, dx:dx + w].reshape(h // s, s, w // s, s, 3).astype(np.int16)
    return ((b.max(axis=(1, 3)) - b.min(axis=(1, 3))).max(axis=2) <= tol).mean()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--scale", type=int, required=True)
    ap.add_argument("--palette"); ap.add_argument("--frames", type=int, default=24); ap.add_argument("--tol", type=int, default=24); ap.add_argument("--colors", type=int)
    a = ap.parse_args(); S = a.scale
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", a.video], capture_output=True, text=True).stdout.strip().split(",")
    if len(pr) < 2: sys.exit("qa_pixels: cannot read the video")
    w, h = int(pr[0]), int(pr[1])
    if S < 2 or w % S or h % S: sys.exit(f"qa_pixels: --scale must be 2 or more and divide {w}x{h} exactly (a 1 x 1 block is always one colour)")
    fr = frames(a.video, a.frames, w, h)
    if not fr: sys.exit("qa_pixels: no frames could be read")
    rows, fails = [], 0
    def row(name, ok, detail):
        nonlocal fails; fails += not ok; rows.append(f"  {'PASS' if ok else 'FAIL'} {name:<8} {detail}")

    share = [uniform(f, S, tol=a.tol) for f in fr]; g = float(np.mean(share)); worst = float(np.min(share))
    detail = f"{100 * g:.2f}% of the {S} x {S} blocks are one colour over {len(fr)} frames (worst frame {100 * worst:.1f}%), at {w // S}x{h // S}"
    if g < 0.99:
        mid = fr[len(fr) // 2]
        phase = max(((uniform(mid, S, dx, dy, a.tol), dx, dy) for dx in range(S) for dy in range(S)), key=lambda t: t[0])
        fits = [s2 for s2 in range(2, 25) if s2 != S and w % s2 == 0 and h % s2 == 0 and uniform(mid, s2, tol=a.tol) >= 0.99]      # a scale the picture really sits on; the largest is the true one
        if phase[0] >= 0.99: detail += f"; the grid fits from about ({phase[1]}, {phase[2]}) pixels in ({100 * phase[0]:.1f}%): the picture is offset from the frame's corner"
        elif fits: detail += f"; the pixels sit on a {max(fits)} x {max(fits)} grid: is the scale right?"
        elif S % 2: detail += "; an odd scale smears 4:2:0 chroma across pixels: use an even scale (2, 4, 6, 8) or yuv444p"
        else: detail += "; something blurs or moves the pixels by less than a pixel"
    row("grid", g >= 0.99, detail)

    pal = palette(a.palette)
    centres = np.concatenate([f[S // 2::S, S // 2::S].reshape(-1, 3) for f in fr])
    key = ((centres[:, 0].astype(np.int32) >> 3) << 10) | ((centres[:, 1].astype(np.int32) >> 3) << 5) | (centres[:, 2].astype(np.int32) >> 3)
    _, cnt = np.unique(key, return_counts=True); cnt = np.sort(cnt)[::-1]
    used = int(np.searchsorted(np.cumsum(cnt) / cnt.sum(), 0.995) + 1)
    if pal is None or a.colors:                      # with a palette, the palette row is the stricter test: noise splits one colour across several 5-bit bins
        limit = a.colors or 64
        row("colours", used <= limit, f"{used} distinct colours cover 99.5% of the blocks (limit {limit})")
    if pal is not None:
        d = np.abs(centres.astype(np.int16)[:, None, :] - pal[None, :, :]).max(axis=2).min(axis=1)
        row("palette", (d <= a.tol).mean() >= 0.99, f"{100 * (d <= a.tol).mean():.2f}% of the blocks are within {a.tol} levels of one of the {len(pal)} palette colours")
    print(f"qa_pixels {os.path.basename(a.video)}"); print("\n".join(rows)); print("pixel QA passed" if not fails else f"pixel QA FAILED ({fails})"); sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
