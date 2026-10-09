#!/usr/bin/env python3
"""plan_edit.py: turn measurements (and optionally a transcript) into an edit decision list (EDL) you can read and change.

  plan_edit.py --source rec.mp4 --analysis analysis.json --out edit.json [--transcript transcript.json]
               [--style talking-head|screen|podcast|raw] [--keep-pause S] [--fillers um,uh,...] [--no-fillers]
               [--punch-in 1.08] [--lufs -16] [--denoise auto|off|N] [--captions|--no-captions] [--music FILE --music-db -22]
               [--width W --height H --fps F] [--reframe none|crop|blur] [--stabilize]

What it decides (every number ends up in edit.json, so the edit is data you can review and adjust):
  1. keep the voiced runs found by analyze.py; shorten a pause down to keep-pause only when that saves at least 0.2 s (MIN_TRIM): a shorter trim buys a visible jump cut for nothing
  2. with a transcript: remove filler words (um, uh, er, ah, hmm ...) and immediate word repeats ("the the"), but only when the word really
     overlaps voiced audio, because ASR word times are rough
  3. snap every cut to the quietest point within +/- 40 ms so cuts land in a breath, not in a word (this is also why ASR timing errors are survivable)
  4. drop slivers shorter than 0.25 s
  5. talking-head style: alternate a slight punch-in zoom on consecutive segments to hide jump cuts
Presets (--style) set sensible defaults for pause length, zoom, captions and the audio chain; any flag overrides them.
Needs numpy + soundfile."""
import argparse, json, math, os, re, sys
import numpy as np
import soundfile as sf

STYLES = {   # keep_pause, punch_in, captions, audio chain strength, color auto-level
    "talking-head": dict(keep_pause=0.30, punch=1.08, captions=True,  audio="voice",  color="auto", fillers=True),
    "screen":       dict(keep_pause=0.55, punch=1.00, captions=True,  audio="voice",  color="none", fillers=True),
    "podcast":      dict(keep_pause=0.45, punch=1.00, captions=False, audio="voice",  color="none", fillers=True),
    "raw":          dict(keep_pause=None, punch=1.00, captions=False, audio="light",  color="none", fillers=False),
}
FILLERS = ["um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "mm", "mmm"]
from edl import STD_FPS


MIN_TRIM = 0.2   # a pause is only cut when that saves at least this long: a 70 ms trim buys a visible jump cut for nothing


def norm(w):
    return re.sub(r"[^a-z']", "", w.lower())


def energy_db(wav, hop=0.005, win=0.012):
    x, sr = sf.read(wav)
    n, h = int(win * sr), int(hop * sr)
    idx = np.arange(0, max(1, len(x) - n), h)
    c = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    return 20 * np.log10(np.sqrt((c[idx + n] - c[idx]) / n) + 1e-9), hop


def snap(t, db, hop, dur, radius=0.04):
    i0, i1 = max(0, int((t - radius) / hop)), min(len(db) - 1, int((t + radius) / hop))
    if i1 <= i0:
        return t
    j = i0 + int(np.argmin(db[i0:i1 + 1]))
    return float(np.clip(j * hop, 0, dur))


def subtract(intervals, cuts):
    out = []
    for s, e in intervals:
        pieces = [[s, e]]
        for cs, ce in cuts:
            nxt = []
            for ps, pe in pieces:
                if ce <= ps or cs >= pe:
                    nxt.append([ps, pe]); continue
                if cs > ps: nxt.append([ps, cs])
                if ce < pe: nxt.append([ce, pe])
            pieces = nxt
        out += pieces
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True); ap.add_argument("--analysis", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--transcript"); ap.add_argument("--style", default="talking-head", choices=list(STYLES))
    ap.add_argument("--keep-pause", type=float); ap.add_argument("--fillers"); ap.add_argument("--no-fillers", action="store_true")
    ap.add_argument("--punch-in", type=float); ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--denoise", default="auto"); ap.add_argument("--min-segment", type=float, default=0.25)
    ap.add_argument("--captions", dest="captions", action="store_true", default=None); ap.add_argument("--no-captions", dest="captions", action="store_false")
    ap.add_argument("--music"); ap.add_argument("--music-db", type=float, default=-22.0)
    ap.add_argument("--width", type=int); ap.add_argument("--height", type=int); ap.add_argument("--fps", type=float)
    ap.add_argument("--reframe", default="none", choices=["none", "crop", "blur"]); ap.add_argument("--stabilize", action="store_true")
    a = ap.parse_args()
    st = STYLES[a.style]
    an = json.load(open(a.analysis)); dur = an["duration"]
    keep = a.keep_pause if a.keep_pause is not None else st["keep_pause"]
    punch = a.punch_in if a.punch_in is not None else st["punch"]
    captions = st["captions"] if a.captions is None else a.captions
    use_fill = (st["fillers"] and not a.no_fillers) and bool(a.transcript)
    notes = []

    # ---- 1. voiced runs -> segments with shortened pauses ----
    if keep is None or not an.get("speech"):
        segs = [[0.0, dur]]
        if keep is not None: notes.append("no speech found: keeping the whole recording")
    else:
        runs = an["speech"]
        half = keep / 2
        segs = []
        for i, (s, e) in enumerate(runs):
            gap_prev = s - runs[i - 1][1] if i else None
            gap_next = runs[i + 1][0] - e if i + 1 < len(runs) else None
            lead = min(0.25, s) if i == 0 else (half if gap_prev > keep + MIN_TRIM else gap_prev / 2)
            tail = min(0.40, dur - e) if gap_next is None else (half if gap_next > keep + MIN_TRIM else gap_next / 2)
            segs.append([max(0.0, s - lead), min(dur, e + tail)])
        merged = [segs[0]]
        for s, e in segs[1:]:
            if s <= merged[-1][1] + 1e-6: merged[-1][1] = max(merged[-1][1], e)
            else: merged.append([s, e])
        segs = merged

    # ---- 2. fillers and repeats from the transcript ----
    cuts = []
    if use_fill:
        words = json.load(open(a.transcript))["words"]
        fset = set((a.fillers.split(",") if a.fillers else FILLERS))
        if not isinstance(words, list): sys.exit("plan_edit: transcript has no word list")
        voiced = an.get("speech", [])
        def overlap(s, e):
            return sum(max(0, min(e, ve) - max(s, vs)) for vs, ve in voiced) / max(1e-6, e - s)
        skipped = 0
        for i, w in enumerate(words):
            n = norm(w["text"]); kind = None
            if n in fset: kind = "filler"
            elif i + 1 < len(words) and n and n == norm(words[i + 1]["text"]) and words[i + 1]["start"] - w["end"] < 0.4: kind = "repeat"
            if not kind: continue
            if overlap(w["start"], w["end"]) < 0.5: skipped += 1; continue          # a mistimed word in silence: do not cut speech for it
            cuts.append([max(0.0, w["start"] - 0.03), min(dur, w["end"] + 0.05), kind, w["text"]])
        if skipped: notes.append(f"{skipped} filler/repeat word(s) skipped: their times did not overlap voiced audio")
        segs = subtract(segs, [[c[0], c[1]] for c in cuts])
    elif a.transcript is None and st["fillers"] and not a.no_fillers:
        notes.append("no transcript: pauses are trimmed but filler words and repeats are NOT removed (transcribe first for that)")

    # ---- 3. snap cuts to the quietest nearby point, 4. drop slivers ----
    if an.get("audio_wav") and os.path.exists(an["audio_wav"]):
        db, hop = energy_db(an["audio_wav"])
        segs = [[snap(s, db, hop, dur) if s > 0 else s, snap(e, db, hop, dur) if e < dur else e] for s, e in segs]
    else:
        notes.append("no audio copy found: cuts were not snapped to quiet points")
    segs = [[round(s, 3), round(e, 3)] for s, e in segs if e - s >= a.min_segment]
    if not segs: sys.exit("plan_edit: nothing left to keep (recording silent, or thresholds too strict)")

    # ---- 5. punch-in on alternating segments ----
    out_segs = [{"in": s, "out": e, "zoom": round(punch if (punch > 1 and i % 2) else 1.0, 3)} for i, (s, e) in enumerate(segs)]

    v, au = an.get("video"), an.get("audio")
    fps = a.fps or (min(STD_FPS, key=lambda f: abs(f - (v["avg_fps"] or v["fps"]))) if v else 30)
    ext = {"width": a.width or (v["width"] if v else 0), "height": a.height or (v["height"] if v else 0)}
    denoise = a.denoise
    if denoise == "auto":
        denoise = 12 if (au and au.get("noise_floor_db") is not None and au["noise_floor_db"] > -62) else 0
    elif denoise == "off": denoise = 0
    else: denoise = float(denoise)
    audio = {"highpass": 80, "denoise": denoise, "compress": st["audio"] == "voice", "presence": st["audio"] == "voice", "fade_ms": 8, "lufs": a.lufs}
    total = round(sum(s["out"] - s["in"] for s in out_segs), 3)
    edl = {"version": 1, "source": os.path.abspath(a.source), "style": a.style,
           "output": {**ext, "fps": fps, "lufs": a.lufs, "reframe": a.reframe},
           "segments": out_segs, "audio": audio,
           "video": {"color": st["color"], "stabilize": a.stabilize, "lut": None},
           "captions": {"enabled": captions and bool(a.transcript), "style": "box", "max_chars": 42, "burn": True, "sidecar": "srt"},
           "music": ({"file": os.path.abspath(a.music), "db": a.music_db, "duck": True} if a.music else None),
           "overlays": [], "chapters": [],
           "stats": {"source_duration": round(dur, 3), "edited_duration": total, "removed": round(dur - total, 3),
                     "segments": len(out_segs), "filler_cuts": [{"at": round(c[0], 2), "word": c[3], "kind": c[2]} for c in cuts]}}
    if captions and not a.transcript: notes.append("captions requested but there is no transcript: run transcribe.sh first")
    edl["notes"] = notes
    json.dump(edl, open(a.out, "w"), indent=1)
    print(f"{a.out}: {dur:.1f}s -> {total:.1f}s ({100 * (dur - total) / dur:.0f}% removed), {len(out_segs)} segments, {len(cuts)} filler/repeat cuts, style {a.style}")
    for n in notes: print("  note:", n)


if __name__ == "__main__":
    main()
