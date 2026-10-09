#!/usr/bin/env python3
"""qa_edit.py edit.json OUT.mp4 [--srt OUT.srt]: gates for an edited video, whatever provider made it.

  duration   equals the kept segments (within 2 frames)          FAIL
  size, fps  as the EDL asked                                    FAIL
  loudness   integrated LUFS within 1 of the target              FAIL (only when the EDL asks for audio processing, i.e. a target)
  peak       true peak <= -1 dBFS                                FAIL
  A/V length audio and video streams within 40 ms                FAIL
  clicks     no jump in the waveform at a cut bigger than the    WARN (a heuristic: it flags, a person listens)
             loudest slope anywhere else
  black      no black stretch of 0.5 s or more                   WARN (a black intro or a screen recording can be legitimate)
  captions   sidecar cues in order, not overlapping, inside      FAIL
             the video
Exit 1 if anything FAILs. Needs ffmpeg and a python with numpy."""
import argparse, json, os, re, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edl import load


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, **kw)


def probe(path, entries, sel=None):
    c = ["ffprobe", "-v", "error"] + (["-select_streams", sel] if sel else []) + ["-show_entries", entries, "-of", "csv=p=0", path]
    return run(c, text=True).stdout.strip()


def srt_secs(t):
    h, m, s = t.replace(",", ".").split(":"); return int(h) * 3600 + int(m) * 60 + float(s)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("edl"); ap.add_argument("out"); ap.add_argument("--srt")
    a = ap.parse_args()
    e = load(a.edl); o = e.get("output") or {}; au = e.get("audio") or {}
    segs = e["segments"]; want = sum(s["out"] - s["in"] for s in segs); fps = o.get("fps") or 30
    rows = []
    def add(name, ok, detail, hard=True): rows.append((name, "PASS" if ok else ("FAIL" if hard else "WARN"), detail))

    dur = float(probe(a.out, "format=duration") or 0)
    add("duration", abs(dur - want) <= max(0.1, 2 / fps), f"{dur:.2f}s, the kept segments are {want:.2f}s")
    v = probe(a.out, "stream=width,height,r_frame_rate", "v:0")
    has_audio = bool(probe(a.out, "stream=index", "a"))
    if v:
        w, h, r = v.split(",")[:3]; n, d = map(float, r.split("/"))
        ok = abs(n / d - fps) <= 0.05 and (not o.get("width") or (int(w), int(h)) == (o["width"] - o["width"] % 2, o["height"] - o["height"] % 2))
        add("size, fps", ok, f"{w}x{h} at {n / d:.2f} fps")
    if has_audio:
        target = au.get("lufs", o.get("lufs"))
        txt = run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.out, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], text=True).stderr
        m = re.search(r"Integrated loudness:\s+I:\s+(-?[\d.]+) LUFS.*?True peak:\s+Peak:\s+(-?[\d.]+) dBFS", txt, re.S)
        if m:
            lufs, peak = float(m.group(1)), float(m.group(2))
            if target is not None: add("loudness", abs(lufs - target) <= 1.0, f"{lufs:.1f} LUFS (target {target})")
            add("true peak", peak <= -1.0, f"{peak:.1f} dBFS")
        else: add("loudness", False, "could not measure it")
        if v:
            vd, ad = probe(a.out, "stream=duration", "v:0"), probe(a.out, "stream=duration", "a:0")
            if vd and ad: add("A/V length", abs(float(vd) - float(ad)) <= 0.04, f"video {float(vd):.3f}s, audio {float(ad):.3f}s")
        raw = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", a.out, "-vn", "-ac", "1", "-ar", "48000", "-f", "f32le", "-"]).stdout
        x = np.frombuffer(raw, dtype=np.float32)
        if len(x) > 4800 and len(segs) > 1:
            dx = np.abs(np.diff(x)); base = np.percentile(dx, 99.9); t = 0.0; bad = []
            for i, s in enumerate(segs[:-1], 1):
                t += s["out"] - s["in"]; c = int(t * 48000); win = dx[max(0, c - 240):c + 240]
                if len(win) and win.max() > max(0.02, 3 * base): bad.append(f"{t:.2f}s")
            add("clicks at cuts", not bad, f"{len(segs) - 1} cuts checked" if not bad else "possible click at " + ", ".join(bad), hard=False)
    if v:
        bl = run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.out, "-an", "-vf", "blackdetect=d=0.5:pix_th=0.10", "-f", "null", "-"], text=True).stderr
        b = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", bl)
        add("black frames", not b, "none" if not b else "black at " + ", ".join(f"{s}-{en}s" for s, en in b), hard=False)
    if a.srt:
        cues = re.findall(r"(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})", open(a.srt, encoding="utf-8").read())
        prev, bad = 0.0, []
        for k, (s, en) in enumerate(cues, 1):
            s, en = srt_secs(s), srt_secs(en)
            if en <= s or s < prev - 1e-3 or en > dur + 0.1: bad.append(str(k))
            prev = en
        add("captions", bool(cues) and not bad, f"{len(cues)} cues in order" if cues and not bad else ("no cues" if not cues else "bad cue " + ", ".join(bad)))
    wid = max(len(r[0]) for r in rows)
    for name, res, detail in rows: print(f"  {res:<4} {name:<{wid}}  {detail}")
    fails = [r for r in rows if r[1] == "FAIL"]
    print("edit QA passed" if not fails else f"edit QA FAILED ({len(fails)})")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
