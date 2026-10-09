#!/usr/bin/env python3
"""interchange.py: write an edit decision list as a timeline another editor can open.

  interchange.py edit.json OUT --format otio|edl

otio  OpenTimelineIO JSON (Timeline.1 > Stack.1 > Track.1 Video + Audio > Clip.2 with an ExternalReference), the same dialect FilmCraft
      writes. Opens in DaVinci Resolve, Kdenlive, Final Cut (via OTIO adapters) and anything else that reads OTIO.
edl   CMX 3600, non-drop frame at the nearest integer rate, with the media's absolute path in a `* SOURCE FILE:` comment. Opens almost everywhere.
Both reference the SOURCE recording by absolute path, with one clip per kept segment, back to back: the cuts, not the polish. The
punch-in zoom, audio chain, colour and captions are not part of either format (zoomed segments are listed in the clip metadata / comments
so you can re-apply them). Relink the media if you move it."""
import argparse, json, os, subprocess, sys
from urllib.parse import quote
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edl import load


def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def has_audio(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path], capture_output=True, text=True)
    return bool(r.stdout.strip())


def rt(frames, rate):
    return {"OTIO_SCHEMA": "RationalTime.1", "rate": rate, "value": float(frames)}


def trange(start_f, dur_f, rate):
    return {"OTIO_SCHEMA": "TimeRange.1", "start_time": rt(start_f, rate), "duration": rt(dur_f, rate)}


def otio(edl, name):
    src = edl["source"]; fps = float(edl["output"].get("fps") or 30); sdur = probe_dur(src)
    def clip(i, s):
        a = round(s["in"] * fps); n = max(1, round(s["out"] * fps) - a)       # round both ends the same way the EDL does, so the two files agree
        return {"OTIO_SCHEMA": "Clip.2", "name": os.path.basename(src), "enabled": True, "effects": [], "markers": [],
                "source_range": trange(a, n, fps), "active_media_reference_key": "DEFAULT_MEDIA",
                "media_references": {"DEFAULT_MEDIA": {"OTIO_SCHEMA": "ExternalReference.1", "name": os.path.basename(src), "available_image_bounds": None,
                                                       "target_url": "file://" + quote(os.path.abspath(src)), "available_range": trange(0, round(sdur * fps), fps), "metadata": {}}},
                "metadata": {"craft_video": {"segment": i + 1, "zoom": s.get("zoom", 1.0)}}}
    tracks = [{"OTIO_SCHEMA": "Track.1", "name": "Video 1", "kind": "Video", "enabled": True, "effects": [], "markers": [], "source_range": None,
               "children": [clip(i, s) for i, s in enumerate(edl["segments"])], "metadata": {}}]
    if has_audio(src):
        tracks.append({"OTIO_SCHEMA": "Track.1", "name": "Audio 1", "kind": "Audio", "enabled": True, "effects": [], "markers": [], "source_range": None,
                       "children": [clip(i, s) for i, s in enumerate(edl["segments"])], "metadata": {}})
    return {"OTIO_SCHEMA": "Timeline.1", "name": name, "global_start_time": None, "metadata": {},
            "tracks": {"OTIO_SCHEMA": "Stack.1", "name": name, "enabled": True, "effects": [], "markers": [], "source_range": None, "children": tracks, "metadata": {}}}


def timecode(sec, fps):
    n = round(fps); f = round(sec * fps); return f"{f // (n * 3600):02d}:{(f // (n * 60)) % 60:02d}:{(f // n) % 60:02d}:{f % n:02d}"


def edl_text(edl, name):
    src = edl["source"]; fps = float(edl["output"].get("fps") or 30); reel = os.path.splitext(os.path.basename(src))[0][:8].upper().replace(" ", "_") or "AX"
    ch = "B" if has_audio(src) else "V"
    out = [f"TITLE: {name}", "FCM: NON-DROP FRAME", ""]
    t = 0.0
    for i, s in enumerate(edl["segments"], 1):
        L = s["out"] - s["in"]
        out.append(f"{i:03d}  {reel:<8} {ch:<5} C        {timecode(s['in'], fps)} {timecode(s['out'], fps)} {timecode(t, fps)} {timecode(t + L, fps)}")
        out.append(f"* FROM CLIP NAME: {os.path.basename(src)}")
        out.append(f"* SOURCE FILE: {os.path.abspath(src)}")                  # FilmCraft links the media by this path; a bare EDL only has the name
        if s.get("zoom", 1.0) > 1.0: out.append(f"* COMMENT: punch-in zoom {s['zoom']}")
        out.append("")
        t += L
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("edl"); ap.add_argument("out"); ap.add_argument("--format", required=True, choices=["otio", "edl"])
    a = ap.parse_args()
    edl = load(a.edl); name = os.path.splitext(os.path.basename(a.out))[0]
    if a.format == "otio": json.dump(otio(edl, name), open(a.out, "w"), indent=2)
    else: open(a.out, "w").write(edl_text(edl, name))
    print(f"{a.out}: {len(edl['segments'])} clips as {a.format.upper()}")


if __name__ == "__main__":
    main()
