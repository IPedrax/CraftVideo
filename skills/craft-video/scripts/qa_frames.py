#!/usr/bin/env python3
"""qa_frames.py VIDEO [--static 3.0] [--end-hold 5.0] [--json]: does the PICTURE of a finished video hold up? The other gates measure sound, size and sync,
so a render with a blank or frozen picture passes them all.

  blank     5% or more of the frames are one flat colour (std < 1.5 and range < 8 on a 128 px copy)                 FAIL
  static    the picture barely changes for --static seconds (under 0.5/255 per frame: a slow drift or moving text on a still ground counts)  WARN, with the times
  end hold  the last such stretch is longer than --end-hold seconds (a sources card needs 3 to 4 s to read)         WARN
  flash     one frame that differs from both neighbours while those two agree (a bad join between scenes)            WARN
It judges the picture only, never captions or sound, and prints the share of the video that barely changes as information. A WARN is a place to look at,
not a verdict: a held end card or a number that settles is meant to be still. `--selftest` builds clips with ffmpeg and checks every rule.
Needs numpy and ffmpeg."""
import argparse, json, subprocess, sys, tempfile
import numpy as np

STILL = 0.5      # mean absolute change per frame (0..255, on the 128 px copy) under which a 0.25 s window counts as still


def load(path):
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", path],
                                     capture_output=True, text=True).stdout)["streams"][0]
    W, H = info["width"], info["height"]; n, d = map(float, info["r_frame_rate"].split("/")); fps = n / d
    w, h = (128, round(128 * H / W / 2) * 2) if W >= H else (round(128 * W / H / 2) * 2, 128)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32), fps


def check(path, static=3.0, end_hold=5.0):
    g, fps = load(path); n = len(g); dur = n / fps; flat = g.reshape(n, -1)
    blank = float(((flat.std(axis=1) < 1.5) & (flat.max(axis=1) - flat.min(axis=1) < 8)).mean())
    d = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))                                   # d[i]: change from frame i to i+1
    step = max(1, round(fps * 0.25)); win = np.array([d[i:i + step].mean() for i in range(0, len(d) - step + 1, step)])
    runs, start = [], None
    for i, s in enumerate(list(win < STILL) + [False]):                                # runs of still windows, as (from, to) seconds
        if s and start is None: start = i
        if not s and start is not None: runs.append((start * step / fps, i * step / fps)); start = None
    last = runs[-1] if runs and runs[-1][1] >= dur - 0.6 else None                     # the still run that reaches the end is the end hold
    body = [r for r in runs if r != last]
    flashes = [round((i + 1) / fps, 2) for i in range(1, n - 1)
               if d[i - 1] > 12 and d[i] > 12 and np.abs(g[i + 1] - g[i - 1]).mean() < 0.35 * min(d[i - 1], d[i])]
    return {"seconds": round(dur, 2), "frames": n, "blank_share": round(blank, 3), "still_share": round(float((win < STILL).mean()), 2),
            "static_min": static, "static_runs": [(round(a, 2), round(b, 2)) for a, b in body if b - a >= static], "end_hold": round(last[1] - last[0], 2) if last else 0.0,
            "end_hold_max": end_hold, "flashes": flashes}


def report(r):
    bad = 0
    ok = r["blank_share"] < 0.05; bad += not ok
    print(f"  {'PASS' if ok else 'FAIL'} blank      {r['blank_share'] * 100:.0f}% of the frames are one flat colour")
    if r["static_runs"]: print("  WARN static     barely changes for " + ", ".join(f"{b - a:.1f} s at {a:.1f} to {b:.1f} s" for a, b in r["static_runs"]) + " (a deliberate hold, or dead time?)")
    else: print(f"  PASS static     no stretch of {r['static_min']:g} s or more where the picture barely changes (before the end)")
    print(f"  {'WARN' if r['end_hold'] > r['end_hold_max'] else 'PASS'} end hold   {r['end_hold']:.1f} s barely changing at the end (limit {r['end_hold_max']:g} s)")
    print(f"  {'WARN' if r['flashes'] else 'PASS'} flash      " + (f"one-frame flashes at {', '.join(map(str, r['flashes'][:6]))} s" if r["flashes"] else "none"))
    print(f"  info  {r['still_share'] * 100:.0f}% of the video barely changes (a slow drift or moving text on a still ground counts as barely changing)")
    return bad


def selftest():
    d = tempfile.mkdtemp()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=180x320:rate=30", "-frames:v", "1", f"{d}/still.png"], check=True)
    def clip(name, parts):                                  # parts: (kind, seconds): move = a moving test pattern, still = one frame held, black = flat black
        args, graph = [], ""
        for i, (k, s) in enumerate(parts):
            args += {"move": ["-f", "lavfi", "-t", str(s), "-i", "testsrc2=size=180x320:rate=30"], "still": ["-loop", "1", "-framerate", "30", "-t", str(s), "-i", f"{d}/still.png"],
                     "black": ["-f", "lavfi", "-t", str(s), "-i", "color=c=black:size=180x320:rate=30"]}[k]
            graph += f"[{i}:v]fps=30,format=yuv420p[v{i}];"
        graph += "".join(f"[v{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", graph, "-pix_fmt", "yuv420p", f"{d}/{name}.mp4"], check=True); return f"{d}/{name}.mp4"
    r = check(clip("mid", [("move", 3), ("still", 4), ("move", 2)]))
    assert r["blank_share"] < 0.05 and len(r["static_runs"]) == 1 and 3.5 <= r["static_runs"][0][1] - r["static_runs"][0][0] <= 4.3 and r["end_hold"] == 0, r
    r = check(clip("tail", [("move", 3), ("still", 6)]))
    assert r["end_hold"] >= 5.5 and not r["static_runs"], r
    r = check(clip("black", [("black", 3)])); assert r["blank_share"] > 0.9, r
    r = check(clip("flash", [("move", 2), ("black", 0.034), ("move", 2)])); assert len(r["flashes"]) == 1 and r["blank_share"] < 0.05, r   # one black frame inside moving footage
    print("qa_frames selftest: ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest": selftest(); sys.exit(0)
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--static", type=float, default=3.0)
    ap.add_argument("--end-hold", type=float, default=5.0); ap.add_argument("--json", action="store_true"); a = ap.parse_args()
    r = check(a.video, a.static, a.end_hold)
    if a.json: print(json.dumps(r)); sys.exit(0)
    print(f"== picture: {a.video} ({r['seconds']} s, {r['frames']} frames) =="); sys.exit(1 if report(r) else 0)
