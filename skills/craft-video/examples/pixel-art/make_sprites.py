#!/usr/bin/env python3
"""make_sprites.py [OUT_DIR]: draw the example's little robot and write sheet.png + sheet.json in the shape Aseprite's sprite-sheet export uses
(`aseprite -b robot.aseprite --sheet sheet.png --data sheet.json --format json-array --list-tags`), so the scene reads it exactly as it would read a real export.
Tags: idle (2 frames), walk (4), hurt (2, ping-pong). Everything here is original and MIT; swap in your own export and the scene does not change.
Needs Pillow."""
import json, os, sys
from PIL import Image

COL = {"o": "1D2B53", "b": "29ADFF", "l": "FFF1E8", "s": "83769C", "e": "FFEC27", "r": "FF004D", ".": None}
UPPER = ["................", ".......r........", ".......o........", "....ooooooooo...", "...obbbbbbbbbo..", "...oblllbbbbbo..", "...obbbbbeebbo..",
         "...obbbbbeebbo..", "...obbbbbbbbbo..", "....ooooooooo...", "....obbbbbbbo...", "....obssbbbbbo.."]
HIP = ".....ooooooo...."
LEGS = {"idle": [".....ob...bo....", ".....ob...bo....", "....ooo...ooo..."],
        "spread": ["....ob.....bo...", "...ob.......bo..", "..ooo.......ooo."],
        "together": [".....obbbbbo....", ".....ob...bo....", ".....ob...bo....", "....ooo...ooo..."]}      # the last one is four rows: the body is one pixel higher


def build(upper, hip, legs):
    return [r.ljust(16, ".")[:16] for r in upper + [hip] + legs]


def flash(rows):                                                  # a hit: every body colour goes white, the eyes red
    return ["".join({"b": "l", "s": "l", "e": "r"}.get(c, c) for c in r) for r in rows]


def frames():
    idle = build(UPPER, HIP, LEGS["idle"])
    bob = lambda legs: build(UPPER[1:], HIP, legs)                # drop the empty top row, the legs are one row longer
    blink = [r.replace("ee", "bb") if i == 6 else r.replace("ee", "oo") if i == 7 else r for i, r in enumerate(idle)]       # the eyes close for one frame
    f = [(idle, 400), (blink, 400),
         (build(UPPER, HIP, LEGS["spread"]), 125), (bob(LEGS["together"]), 125), (build(UPPER, HIP, LEGS["spread"]), 125), (bob(LEGS["together"]), 125),
         (flash(idle), 80), (idle, 80)]
    return f


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    fr = frames(); n = len(fr)
    sheet = Image.new("RGBA", (16 * n, 16), (0, 0, 0, 0))
    for i, (rows, _) in enumerate(fr):
        assert len(rows) == 16 and all(len(r) == 16 for r in rows), (i, [len(r) for r in rows])
        for y, r in enumerate(rows):
            for x, ch in enumerate(r):
                if COL[ch]: sheet.putpixel((16 * i + x, y), tuple(int(COL[ch][k:k + 2], 16) for k in (0, 2, 4)) + (255,))
    sheet.save(os.path.join(out, "sheet.png"))
    data = {"frames": [{"filename": f"robot {i}.aseprite", "frame": {"x": 16 * i, "y": 0, "w": 16, "h": 16}, "rotated": False, "trimmed": False,
                        "spriteSourceSize": {"x": 0, "y": 0, "w": 16, "h": 16}, "sourceSize": {"w": 16, "h": 16}, "duration": d} for i, (_, d) in enumerate(fr)],
            "meta": {"app": "make_sprites.py, standing in for Aseprite's export", "version": "1.0", "image": "sheet.png", "format": "RGBA8888", "size": {"w": 16 * n, "h": 16}, "scale": "1",
                     "frameTags": [{"name": "idle", "from": 0, "to": 1, "direction": "forward"}, {"name": "walk", "from": 2, "to": 5, "direction": "forward"},
                                   {"name": "hurt", "from": 6, "to": 7, "direction": "pingpong"}]}}
    json.dump(data, open(os.path.join(out, "sheet.json"), "w"), indent=1)
    print(f"{out}: sheet.png ({16 * n}x16, {n} frames) and sheet.json (tags idle, walk, hurt)")


if __name__ == "__main__":
    main()
