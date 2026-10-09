#!/usr/bin/env python3
"""edl.py: load an edit decision list and fill in what a hand-written one leaves out.

  edl.py IN.json OUT.json     write the completed copy (the dispatcher does this, then hands every step the copy)
  from edl import load        the same thing for the Python scripts

A valid EDL needs only {"source": "file", "segments": [{"in": s, "out": s}, ...]}. Missing parts come from the source recording:
output.width/height/fps (fps snapped to the nearest standard rate), output.lufs -16, reframe none, stats.source_duration and a zoom of 1.0
per segment. Nothing already in the file is changed. Exits with one clear line if the source or the segments are unusable."""
import json, os, subprocess, sys

STD_FPS = [23.976, 24, 25, 29.97, 30, 50, 59.94, 60]


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path], capture_output=True, text=True)
    if not os.path.exists(path): sys.exit(f"edl: the source recording is missing: {path}")
    try: d = json.loads(r.stdout); d["format"]["duration"]
    except (ValueError, KeyError): sys.exit(f"edl: ffprobe cannot read the source recording (not a media file?): {path}")
    v = next((s for s in d.get("streams", []) if s["codec_type"] == "video"), None)
    fps = None
    if v:
        n, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/"); fps = float(n) / float(den or 1) if float(den or 1) else None
        if not fps: n, den = v["r_frame_rate"].split("/"); fps = float(n) / float(den)
        fps = min(STD_FPS, key=lambda f: abs(f - fps))
    return {"duration": float(d["format"]["duration"]), "width": v and v["width"], "height": v and v["height"], "fps": fps}


def load(path):
    e = json.load(open(path))
    if not e.get("source"): sys.exit("edl: the EDL has no \"source\"")
    if not e.get("segments"): sys.exit("edl: the EDL has no \"segments\" (nothing would be kept)")
    for i, s in enumerate(e["segments"], 1):
        if not (0 <= s["in"] < s["out"]): sys.exit(f"edl: segment {i} has in={s['in']} out={s['out']}: out must be after in, and in must be 0 or more")
        s.setdefault("zoom", 1.0)
    p = probe(e["source"])
    if e["segments"][-1]["out"] > p["duration"] + 0.05: sys.exit(f"edl: the last segment ends at {e['segments'][-1]['out']}s but the source is {p['duration']:.2f}s long")
    o = e.setdefault("output", {})
    for k in ("width", "height"):
        if p[k]: o.setdefault(k, p[k])
    if p["fps"]: o.setdefault("fps", p["fps"])
    o.setdefault("fps", 30); o.setdefault("lufs", -16.0); o.setdefault("reframe", "none")
    e.setdefault("stats", {}).setdefault("source_duration", round(p["duration"], 3))
    return e


if __name__ == "__main__":
    json.dump(load(sys.argv[1]), open(sys.argv[2], "w"), indent=1)
