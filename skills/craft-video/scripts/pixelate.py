#!/usr/bin/env python3
"""pixelate.py IN OUT [--scale 6] [--size LWxLH] [--palette pico8|NAME|FILE.hex|FILE.png|auto:16] [--dither bayer|none] [--bayer 3] [--fps 12]
              [--contrast 1.1] [--saturation 1.2] [--crf 14] [--yuv444] [--allow-odd]

Turn any picture (a made video, a recording, a screen capture) into pixel art that stays pixel art in the file: shrink it to a logical size with an area filter,
map it onto a fixed palette with ordered (Bayer) dithering, hold it on whole animation frames, and blow it back up by an integer factor with nearest neighbour.
  --scale S    the size of one pixel in the output (default 6). The logical size is the input size divided by S, so 1920x1080 at 6 is 320x180 and 1080x1920 is 180x320.
               Use an EVEN scale (2, 4, 6, 8, 10, 12): measured on x264 4:2:0, an odd scale lets chroma bleed across pixels (S=3 kept 50% of the pixel blocks, S=5 44%, even
               scales 100%) and S=1 destroys 1-pixel detail. An odd scale is refused unless --yuv444 (clean, but many players cannot play it) or --allow-odd.
  --size WxH   the logical size, instead of deriving it from the input; the output is (W*S) x (H*S). The input is scaled to cover it and cropped.
  --palette    a name from pixel/palettes.json, a .hex file (one #rrggbb per line), a PNG (its colours), or auto:N (the N best colours of the whole clip, fixed for every frame).
               A fixed palette is what keeps colours from shifting between frames.
  --dither     bayer (default, --bayer 0 to 5 sets the pattern size, 3 is 8 x 8): ordered, so it does not shimmer. none: flat colour, no pattern. ffmpeg's own default
               (sierra2_4a) and Floyd-Steinberg are not offered: measured on real footage they changed 47% and 46% of the pixels between frames, Bayer 14.5% like no
               dithering at all (the real motion), because error diffusion carries one pixel's rounding into its neighbours and the next frame rounds differently.
  --fps N      the logical frame rate (default: the input's). Pixel art is animated on twos or threes: 15 or 10 for a 30 fps output, 12 for 24, 12 or 15 or 20 for 60.
               It must divide the output rate; each frame is then held for the rest of its slot.
  --contrast, --saturation   a push before the palette (1.1 and 1.2 suit most footage): a palette flattens the picture.
Audio is copied. A .png OUT makes one still, lossless (the first frame of a video, or an image such as a photo or a logo): a pixel-art avatar or sprite base in one command.
Check the result with:  qa_pixels.py OUT --scale S --palette NAME (a video; for a still, look at it). Needs ffmpeg and Pillow (to write the palette image)."""
import argparse, json, os, subprocess, sys, tempfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))


def load_palette(spec):
    """Colours as [(r, g, b)] for a palette name, a .hex file or a PNG."""
    if spec.startswith("auto:"): return None
    if os.path.isfile(spec):
        if spec.lower().endswith(".png"):
            from PIL import Image
            return sorted({tuple(p) for p in Image.open(spec).convert("RGB").getdata()})
        hexes = [l.strip().lstrip("#") for l in open(spec) if l.strip() and not l.startswith(("//", ";"))]
    else:
        pf = os.path.join(HERE, "..", "pixel", "palettes.json"); data = json.load(open(pf)) if os.path.exists(pf) else {}
        if spec not in data: sys.exit(f"pixelate: no palette '{spec}' (known: {', '.join(sorted(data))}); or pass a .hex or .png file, or auto:16")
        hexes = [c.lstrip("#") for c in data[spec]["colors"]]
    return [tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in hexes]


def palette_png(cols, path):
    """ffmpeg's paletteuse wants exactly 256 pixels: repeat the colours to fill them (a repeat is the same colour, so the mapping is unchanged)."""
    from PIL import Image
    im = Image.new("RGB", (16, 16)); im.putdata((cols * (256 // len(cols) + 1))[:256]); im.save(path)


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate", "-of", "json", path], capture_output=True, text=True)
    s = json.loads(r.stdout)["streams"][0]; fps = Fraction(s["avg_frame_rate"] if s["avg_frame_rate"] not in ("0/0", "") else s["r_frame_rate"])
    audio = bool(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip())
    return int(s["width"]), int(s["height"]), fps, audio


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("out"); ap.add_argument("--scale", type=int, default=6); ap.add_argument("--size"); ap.add_argument("--palette", default="pico8")
    ap.add_argument("--dither", default="bayer", choices=["bayer", "none"]); ap.add_argument("--bayer", type=int, default=3); ap.add_argument("--fps", type=float)
    ap.add_argument("--contrast", type=float, default=1.1); ap.add_argument("--saturation", type=float, default=1.2); ap.add_argument("--crf", type=int, default=14)
    ap.add_argument("--yuv444", action="store_true"); ap.add_argument("--allow-odd", action="store_true")
    a = ap.parse_args(); S = a.scale
    if S < 2: sys.exit("pixelate: --scale must be 2 or more (at 1 the pixels are 1 x 1 and 4:2:0 chroma destroys them)")
    if S % 2 and not (a.yuv444 or a.allow_odd): sys.exit(f"pixelate: scale {S} is odd: 4:2:0 chroma would bleed across pixels. Use an even scale (2, 4, 6, 8), or --yuv444 (clean, but many players cannot play it), or --allow-odd")
    w, h, fps, audio = probe(a.src)
    lw, lh = (int(v) for v in a.size.lower().split("x")) if a.size else (w // S, h // S)
    ow, oh = lw * S, lh * S; out_fps = float(fps)
    lf = a.fps or out_fps
    if lf > out_fps + 1e-6 or abs(out_fps / lf - round(out_fps / lf)) > 1e-3: sys.exit(f"pixelate: --fps {lf:g} must divide the output rate {out_fps:g} (each frame is held for a whole number of output frames)")
    tmp = tempfile.mkdtemp(prefix="cvpix-"); pal = os.path.join(tmp, "palette.png")
    eq = f",eq=contrast={a.contrast}:saturation={a.saturation}" if (a.contrast != 1 or a.saturation != 1) else ""
    head = f"fps={lf:g},scale={lw}:{lh}:force_original_aspect_ratio=increase:flags=area,crop={lw}:{lh}:exact=1,setsar=1{eq}"      # exact=1: crop rounds an odd height (135) down to an even one on yuv420p, and the integer upscale is lost
    if a.palette.startswith("auto:"):                                 # the whole clip's best N colours, found once, so no frame picks its own
        n = int(a.palette[5:])
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-vf", f"{head},palettegen=max_colors={n}:stats_mode=full:reserve_transparent=0", pal], check=True)
        cols = None
    else:
        cols = load_palette(a.palette); palette_png(cols, pal)
    dith = "dither=none" if a.dither == "none" else f"dither=bayer:bayer_scale={a.bayer}"
    still = a.out.lower().endswith(".png"); pix = "rgb24" if still else ("yuv444p" if a.yuv444 else "yuv420p")
    fc = f"[0:v]{head}[s];[s][1:v]paletteuse={dith}[p];[p]scale={ow}:{oh}:flags=neighbor,fps={out_fps:g},format={pix}[v]"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", a.src, "-i", pal, "-filter_complex", fc, "-map", "[v]"] + \
          (["-frames:v", "1", "-update", "1", a.out] if still else
           (["-map", "0:a", "-c:a", "copy"] if audio else []) + ["-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf), "-pix_fmt", pix, "-movflags", "+faststart", a.out])
    subprocess.run(cmd, check=True)
    msg = f"pixelate: {a.out}: {ow}x{oh} from a {lw}x{lh} picture at scale {S}, palette {a.palette}" + ("" if cols is None else f" ({len(cols)} colours)") + f", {a.dither} dither, "
    msg += pix if still else f"{lf:g} fps held to {out_fps:g}, {pix}"
    if not still: msg += f"\n  check it: python3 {os.path.join(HERE, 'qa_pixels.py')} {a.out} --scale {S}" + ("" if a.palette.startswith("auto:") else f" --palette {a.palette}")
    print(msg)


if __name__ == "__main__":
    main()
