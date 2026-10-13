#!/usr/bin/env python3
"""face_track.py: make a 9:16 (or any narrower) crop follow the speaker's face instead of sitting in the middle of the frame.

  face_track.py analyze SOURCE TRACK.json [--ranges "10-70,300-360"] [--fps 3] [--width 480]    (needs OpenCV and the YuNet model: scripts/get_face.sh;
                                                                                                  run it with that venv's python, see FACE_PY below)
  face_track.py apply EDL.json TRACK.json [--out EDL.json] [--smooth 0.9] [--deadzone 0.05]       (numpy and OpenCV not needed: writes the crop path into the EDL)
  face_track.py --selftest

analyze decodes the source once, at a low rate and size, runs the YuNet face detector on each sample and keeps the dominant face (largest, with a bias for
the one it followed a moment ago, so two people of similar size do not make the crop flip), and finds scene cuts from ffmpeg's scene score (a face that jumps
across the frame between two samples counts as a cut too, and is pinned to its exact frame). TRACK.json holds one sample per step: [t, face centre x, face
centre y, face area as a share of the frame], with nulls where no face was found, and the cut times. --ranges limits it to the parts of the source that
matter (the clips you picked), which is much faster on a long file.

apply writes, for every segment of an edit.json whose output is narrower than the source, the path of the crop window: "crop": {"axis", "w", "h", "keys": [[t, pos]...]}
(t from the segment's start, pos the window's left or top edge in source pixels) and "layout": "face". The path is smoothed: missing samples are filled,
a median filter removes single-sample spikes, a deadzone keeps the frame still while the head only moves a little, and a critically damped spring eases
toward the target, run forward and then backward over the samples (the whole file is known, so the frame does not trail a moving face by the spring's time
constant), so a pan starts and stops softly and never overshoots. The smoothing restarts at every scene cut and the path jumps there instead of
panning across it. A segment where a face is found in under half the samples (a slide, a screen recording) gets "layout": "fit": the whole frame over a
blurred copy of itself, so nothing is cropped off. edit.sh then applies it with the ffmpeg provider (output.reframe "face").
The ideas (YuNet through OpenCV's FaceDetectorYN, low-rate sampling, a deadzone and a spring on the crop, face shots against full-frame shots) are the ones
SupoClip (FujiwaraChoki/supoclip, AGPL-3.0) uses; this is our own code, written from a description of them, and none of SupoClip's code is here.
FACE_PY: the python that has OpenCV: $FACE_DIR/venv/bin/python (default ~/.local/share/craftvideo/face)."""
import argparse, json, math, os, re, subprocess, sys

FACE_DIR = os.environ.get("FACE_DIR") or os.path.expanduser("~/.local/share/craftvideo/face")
MODEL = os.path.join(FACE_DIR, "face_detection_yunet_2023mar.onnx")
MIN_AREA = 0.0015        # a face under this share of the frame is not the speaker (a poster, a thumbnail)
FACE_RATE = 0.5          # a segment with a face in fewer than this share of its samples is a "fit" segment
MAX_KEYS = 60            # keys per segment: the crop expression grows with them


# ------------------------------------------------------------------ analyze (needs OpenCV)
def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", path], capture_output=True, text=True)
    d = json.loads(r.stdout); return int(d["streams"][0]["width"]), int(d["streams"][0]["height"]), float(d["format"]["duration"])


def frames(src, t0, dur, fps, w, h, gray=False):
    """(t, ndarray) for each sample of [t0, t0+dur): one sequential ffmpeg decode, piped as raw frames."""
    import numpy as np
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", src, "-an", "-sn", "-vf", f"fps={fps},scale={w}:{h}", "-pix_fmt", "gray" if gray else "bgr24", "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL); n = w * h * (1 if gray else 3); k = 0
    try:
        while True:
            raw = p.stdout.read(n)
            if len(raw) < n: break
            yield t0 + k / fps, np.frombuffer(raw, np.uint8).reshape((h, w) if gray else (h, w, 3)); k += 1
    finally:
        p.stdout.close(); p.wait()


def scene_cuts(src, s, e, thr=0.2):
    """Cut times in [s, e) from ffmpeg's scene score, read at the source's own frame rate on a small copy (frame-accurate, one decode)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", src, "-an", "-vf", f"scale=160:-2,select='gt(scene,{thr})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True)
    return [round(s + float(m), 3) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr) if float(m) > 0.05]


def exact_cut(src, a, b):
    """A shot change lies between the samples at a and b: look at every frame in between (small, grey) and take the biggest jump."""
    import numpy as np
    best, at = -1.0, (a + b) / 2; prev = None
    for t, f in frames(src, max(0.0, a - 0.05), (b - a) + 0.1, 60, 32, 18, gray=True):
        if prev is not None:
            d = float(np.mean(np.abs(f.astype(np.int16) - prev)))
            if d > best: best, at = d, t
        prev = f.astype(np.int16)
    return round(at, 3)


def analyze(src, ranges, fps, pw):
    try:
        import cv2, numpy as np
    except ImportError:
        sys.exit(f"face_track: OpenCV is not available to this python. Run scripts/get_face.sh once, then run this with {FACE_DIR}/venv/bin/python")
    if not os.path.exists(MODEL): sys.exit(f"face_track: the YuNet model is missing ({MODEL}): run scripts/get_face.sh")
    w, h, dur = probe(src); ph = max(2, int(round(pw * h / w / 2)) * 2)
    det = cv2.FaceDetectorYN.create(MODEL, "", (pw, ph), 0.6, 0.3, 50)
    samples, cuts = [], []
    for s, e in (ranges or [(0.0, dur)]):
        prev_c, mine = None, []
        for t, fr in frames(src, s, e - s, fps, pw, ph):
            _, fs = det.detect(fr)
            best, bs = None, -1.0
            for f in ([] if fs is None else fs):
                x, y, fw, fh = (float(v) for v in f[:4]); sc = float(f[-1])
                area = fw * fh / (pw * ph)
                if area < MIN_AREA: continue
                score = area * sc * (1.5 if prev_c is not None and abs(x + fw / 2 - prev_c) < 0.15 * pw else 1.0)
                if score > bs: best, bs = (x + fw / 2, y + fh / 2, area), score
            if best: prev_c = best[0]; mine.append([round(t, 3), round(best[0] / pw * w, 1), round(best[1] / ph * h, 1), round(best[2], 5)])
            else: mine.append([round(t, 3), None, None, 0.0])
        samples += mine
        found = scene_cuts(src, s, e)
        for p, q in zip(mine, mine[1:]):          # a face that jumps across the frame between two samples (0.3 s) is a shot change, whatever the scene score says
            if p[1] is not None and q[1] is not None and abs(q[1] - p[1]) > 0.2 * w and not any(p[0] - 0.05 <= c <= q[0] + 0.05 for c in found):
                found.append(exact_cut(src, p[0], q[0]))
        cuts += found
    return {"version": 1, "source": os.path.abspath(src), "width": w, "height": h, "duration": dur, "sample_fps": fps, "samples": samples, "cuts": sorted(set(cuts))}


# ------------------------------------------------------------------ the crop path (pure python)
def fill(vals):
    out = list(vals); last = None
    for i, v in enumerate(out):
        if v is None: out[i] = last
        else: last = v
    last = None
    for i in range(len(out) - 1, -1, -1):
        if out[i] is None: out[i] = last
        else: last = out[i]
    return out


def median3(v):
    return [sorted(v[max(0, i - 1):i + 2])[len(v[max(0, i - 1):i + 2]) // 2] for i in range(len(v))]


def spring(ts, tgt, w, lo, hi, vmax):
    """A critically damped spring toward tgt: eases in and out, never overshoots."""
    x, v, out = tgt[0], 0.0, [tgt[0]]
    for k in range(1, len(ts)):
        dt = ts[k] - ts[k - 1]; n = max(1, math.ceil(dt / 0.02)); h = dt / n
        for _ in range(n):
            v = max(-vmax, min(vmax, v + (w * w * (tgt[k] - x) - 2 * w * v) * h)); x += v * h
        x = max(lo, min(hi, x)); out.append(x)
    return out


def smooth_run(ts, desired, lo, hi, dz, smooth, vmax):
    """One shot: median filter, then a deadzone (the comfort target only moves once the face drifts past it), then a critically damped spring toward it,
    run forward and then backward over the samples: the whole file is known, so there is no reason for the frame to lag a moving face by the spring's time constant."""
    d = median3(desired); a = d[0]; tgt = []
    for v in d:
        if v - a > dz: a = v - dz
        elif a - v > dz: a = v + dz
        tgt.append(a)
    w = 2.0 / max(0.05, smooth / 1.4)                      # two passes soften about 1.4 times as much as one
    fwd = spring(ts, tgt, w, lo, hi, vmax)
    back = spring([-t for t in reversed(ts)], list(reversed(fwd)), w, lo, hi, vmax)
    return list(reversed(back))


def simplify(pts, tol):
    """Keep a key when the path has moved by at least tol since the last kept one; the ends and the jump pairs at cuts always stay."""
    keys = [pts[0]]
    for i in range(1, len(pts) - 1):
        if pts[i][2] or abs(pts[i][1] - keys[-1][1]) >= tol: keys.append(pts[i])
    keys.append(pts[-1]); return keys


def segment_keys(track, t0, t1, cw, iw, ih, axis, smooth=0.9, deadzone=0.05):
    """Keys [(t from t0, pos)] for the crop window over [t0, t1], and the share of samples with a face."""
    ts_all = [s[0] for s in track["samples"]]
    if not ts_all: return [], 0.0
    cuts = [c for c in track.get("cuts", [])]
    lo, hi = 0.0, float((iw - cw) if axis == "x" else (ih - cw))
    col = 1 if axis == "x" else 2; size = iw if axis == "x" else ih
    pad = 2.5                                              # settle in front of the segment: it must not start mid-pan
    sel = [s for s in track["samples"] if t0 - pad <= s[0] <= t1 + 0.5]
    if not sel: return [], 0.0
    inside = [s for s in track["samples"] if t0 <= s[0] <= t1]
    presence = (sum(1 for s in inside if s[col] is not None and s[3] >= MIN_AREA) / len(inside)) if inside else 0.0
    pts = []
    bounds = [t0 - pad] + [c for c in cuts if t0 - pad < c < t1 + 0.5] + [t1 + 1.0]
    for ri in range(len(bounds) - 1):
        a, b = bounds[ri], bounds[ri + 1]
        run = [s for s in sel if a <= s[0] < b]
        if not run: continue
        centre = fill([s[col] if (s[col] is not None and s[3] >= MIN_AREA) else None for s in run])
        if centre[0] is None: continue
        desired = [min(max(c - cw / 2.0, lo), hi) for c in centre]
        xs = smooth_run([s[0] for s in run], desired, lo, hi, max(2.0, cw * deadzone), smooth, size * 0.4)
        first = ri > 0                                     # a jump pair at a cut: hold the old shot's last position to the cut, then the new shot's first
        if first and pts: pts.append((a - 1 / 120.0, pts[-1][1], True))
        for i, (s, x) in enumerate(zip(run, xs)): pts.append((s[0], x, bool(first and i == 0)))
    if not pts: return [], presence
    def at(t):                                             # the path at time t, held outside its ends, linear between points; a cut's jump pair is vertical
        if t <= pts[0][0]: return pts[0][1]
        for (ta, xa, _), (tb, xb, _) in zip(pts, pts[1:]):
            if ta <= t <= tb: return xa if tb == ta else xa + (xb - xa) * (t - ta) / (tb - ta)
        return pts[-1][1]
    win = [(t0, at(t0), True)] + [(t, x, j) for t, x, j in pts if t0 < t < t1] + [(t1, at(t1), True)]
    tol = max(1.5, cw * 0.006); keys = simplify(win, tol)
    while len(keys) > MAX_KEYS: tol *= 1.5; keys = simplify(win, tol)
    return [(round(t - t0, 3), int(round(x))) for t, x, _ in keys], presence


def pan_expr(keys):
    """ffmpeg expression of t: the position along the keys, linear between them and held outside, written as a sum of clipped ramps (no deep nesting)."""
    if not keys: return "0"
    e = str(int(keys[0][1]))
    for (ta, xa), (tb, xb) in zip(keys, keys[1:]):
        if xb != xa: e += f"+({int(xb - xa)})*clip((t-{ta:.3f})/{max(tb - ta, 1e-3):.3f},0,1)"
    return e


def shot_kinds(track, t0, t1, min_run=1.0):
    """[(a, b, kind)] over [t0, t1]: the footage between scene cuts, each "face" when a face is found in at least half of its samples and "fit" when not
    (a slide, a screen recording), None where the track has no samples. A run under min_run seconds takes its neighbour's kind, so a flicker is not a layout change."""
    edges = [t0] + [c for c in track.get("cuts", []) if t0 + 0.2 < c < t1 - 0.2] + [t1]; runs = []
    for a, b in zip(edges, edges[1:]):
        ins = [s for s in track["samples"] if a <= s[0] < b]
        runs.append([a, b, None if not ins else ("face" if sum(1 for s in ins if s[1] is not None and s[3] >= MIN_AREA) / len(ins) >= FACE_RATE else "fit")])
    for i, r in enumerate(runs):
        if r[2] is not None and r[1] - r[0] < min_run and len(runs) > 1:
            nb = runs[i - 1] if i > 0 else runs[i + 1]
            if nb[2] is not None: r[2] = nb[2]
    merged = []
    for r in runs:
        if merged and merged[-1][2] == r[2]: merged[-1][1] = r[1]
        else: merged.append(list(r))
    return [tuple(r) for r in merged]


def apply(edl, track, smooth=0.9, deadzone=0.05):
    """Annotate the EDL's segments: a face shot gets the crop path, a content shot "fit". A segment that spans both is split at the change (the provider keeps
    the sound continuous across a split that is not a cut). Returns (edl, face segments, fit segments, segments the track does not cover)."""
    iw, ih = track["width"], track["height"]; o = edl.setdefault("output", {})
    ow, oh = o.get("width") or iw, o.get("height") or ih
    cw, ch = min(iw, int(ih * ow / oh) // 2 * 2), min(ih, int(iw * oh / ow) // 2 * 2)
    axis = "x" if cw < iw else ("y" if ch < ih else None)
    if axis is None: return edl, 0, 0, 0
    out, nface, nfit, nnone = [], 0, 0, 0
    for s in edl["segments"]:
        for a, b, kind in shot_kinds(track, s["in"], s["out"]):
            sub = {k: v for k, v in s.items() if k not in ("layout", "crop")}; sub["in"], sub["out"] = round(a, 4), round(b, 4)
            keys = segment_keys(track, a, b, cw if axis == "x" else ch, iw, ih, axis, smooth, deadzone)[0] if kind == "face" else []
            if kind == "face" and keys: sub["layout"] = "face"; sub["crop"] = {"axis": axis, "w": cw, "h": ch, "keys": [list(k) for k in keys]}; nface += 1
            elif kind is None: nnone += 1
            else: sub["layout"] = "fit"; nfit += 1
            out.append(sub)
    edl["segments"] = out; o["reframe"] = "face"; edl["face"] = {"track": track.get("source"), "smooth": smooth, "deadzone": deadzone}
    return edl, nface, nfit, nnone


# ------------------------------------------------------------------ self-test: the path, then the whole thing on footage with a moving marker (no OpenCV needed)
def selftest():
    import tempfile
    # 1. the path: a still face stays still, a drifting one is followed softly without overshoot, a cut is a jump, a gap is filled
    ts = [i / 3.0 for i in range(30)]
    still = smooth_run(ts, [500 + (3 if i % 2 else -3) for i in range(30)], 0, 1000, 30, 0.9, 400)
    assert max(still) - min(still) < 1.0, "jitter inside the deadzone must not move the frame"
    drift = smooth_run(ts, [300 + 40 * i for i in range(30)], 0, 2000, 30, 0.9, 800)
    assert all(b >= a - 1e-6 for a, b in zip(drift, drift[1:])) and drift[-1] < 300 + 40 * 29 + 1, "the frame must follow the drift and never overshoot"
    assert abs(median3([1, 1, 90, 1, 1])[2] - 1) < 1e-9 and fill([None, 4, None, 6, None]) == [4, 4, 4, 6, 6]
    track = {"width": 1920, "height": 1080, "samples": [[i / 3.0, (500 if i < 15 else 1400) + 0.0, 300.0, 0.02] for i in range(45)], "cuts": [5.0]}
    keys, pres = segment_keys(track, 0.0, 14.0, 606, 1920, 1080, "x")
    xs = dict(keys); jump = [(a, b) for a, b in zip(keys, keys[1:]) if abs(b[1] - a[1]) > 400]
    assert pres == 1.0 and len(jump) == 1 and 4.9 < jump[0][1][0] < 5.1 and abs(jump[0][1][1] - (1400 - 303)) < 5, (keys, jump)
    assert pan_expr([(0, 100), (1, 100), (2, 300)]).count("clip") == 1 and len(keys) <= MAX_KEYS
    nofaces = {"width": 1920, "height": 1080, "samples": [[i / 3.0, None, None, 0.0] for i in range(30)], "cuts": []}
    e, nf, nfit, nn = apply({"segments": [{"in": 0.0, "out": 5.0}], "output": {"width": 1080, "height": 1920}}, nofaces)
    assert (nf, nfit, nn) == (0, 1, 0) and e["segments"][0]["layout"] == "fit"
    # a face shot, a slide, a face shot: one segment over all three is split where the layout changes, back to back; a 0.5 s blip takes its neighbour's kind
    face = lambda t, x: [t, x, 300.0, 0.02]; none = lambda t: [t, None, None, 0.0]
    three = {"width": 1920, "height": 1080, "cuts": [5.0, 9.0, 12.5, 13.0], "samples": [face(i / 3.0, 700) for i in range(15)] + [none(5 + i / 3.0) for i in range(12)]
             + [face(9 + i / 3.0, 1200) for i in range(10)] + [none(12.5 + i / 3.0) for i in range(1)] + [face(13 + i / 3.0, 1200) for i in range(5)]}
    e, nf, nfit, nn = apply({"segments": [{"in": 0.0, "out": 14.5, "zoom": 1.08}], "output": {"width": 1080, "height": 1920}}, three)
    sg = e["segments"]
    assert [s["layout"] for s in sg] == ["face", "fit", "face"] and (nf, nfit) == (2, 1), [(s["in"], s["out"], s["layout"]) for s in sg]
    assert all(abs(a["out"] - b["in"]) < 1e-6 for a, b in zip(sg, sg[1:])) and sg[0]["in"] == 0.0 and sg[-1]["out"] == 14.5 and all(s["zoom"] == 1.08 for s in sg)
    e, nf, nfit, nn = apply({"segments": [{"in": 40.0, "out": 45.0}], "output": {"width": 1080, "height": 1920}}, three)
    assert nn == 1 and "layout" not in e["segments"][0], "a segment the track does not cover stays untracked"
    # 2. end to end: footage with a bright box that slides across a dark frame; the crop must keep it in the middle of the output
    here = os.path.dirname(os.path.abspath(__file__)); d = tempfile.mkdtemp(prefix="cvface-"); src = os.path.join(d, "box.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x101418:s=1280x720:r=30:d=8", "-f", "lavfi", "-i", "color=c=white:s=120x200:r=30:d=8",
                    "-filter_complex", "[0][1]overlay=x='200+100*t':y=260", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", src], check=True)
    tr = {"version": 1, "source": src, "width": 1280, "height": 720, "samples": [[i / 3.0, 260 + 800 * (i / 3.0) / 8, 360.0, 0.02] for i in range(24)], "cuts": []}
    edl = {"version": 1, "source": src, "segments": [{"in": 0.5, "out": 7.5, "zoom": 1.0}], "output": {"width": 360, "height": 640, "fps": 30, "reframe": "face"},
           "audio": {}, "video": {}, "overlays": [], "stats": {"source_duration": 8.0}}
    edl, nf, nfit, nn = apply(edl, tr); assert (nf, nfit, nn) == (1, 0, 0), (nf, nfit, nn)
    ep = os.path.join(d, "edl.json"); json.dump(edl, open(ep, "w")); out = os.path.join(d, "out.mp4")
    r = subprocess.run([sys.executable, os.path.join(here, "providers", "edit", "edit_ffmpeg.py"), ep, out], capture_output=True, text=True)
    assert r.returncode == 0 and os.path.exists(out), r.stderr[-400:]
    import numpy as np
    errs = []
    for t in (1.0, 3.0, 5.0, 6.8):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", out, "-frames:v", "1", "-vf", "format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
        img = np.frombuffer(raw, np.uint8).reshape(640, 360)
        cols = np.nonzero((img > 200).sum(axis=0) > 100)[0]
        assert len(cols), f"the box is not in the output frame at {t} s"
        errs.append(abs((cols.min() + cols.max()) / 2 - 180) / 360)
    assert max(errs) < 0.12, f"the marker strays from the middle of the crop by {max(errs):.0%} of the width: {errs}"
    print(f"face_track selftest: ok (the marker stays within {max(errs):.1%} of the middle over a 7 s slide; {len(edl['segments'][0]['crop']['keys'])} keys)")


def main():
    ap = argparse.ArgumentParser(add_help=False); ap.add_argument("cmd", nargs="?"); ap.add_argument("a", nargs="?"); ap.add_argument("b", nargs="?")
    ap.add_argument("--ranges"); ap.add_argument("--fps", type=float, default=3.0); ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--out"); ap.add_argument("--smooth", type=float, default=0.9); ap.add_argument("--deadzone", type=float, default=0.05); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest or a.cmd == "--selftest": return selftest()
    if a.cmd == "analyze" and a.a and a.b:
        rng = [tuple(float(x) for x in p.split("-")) for p in a.ranges.split(",")] if a.ranges else None
        tr = analyze(a.a, rng, a.fps, a.width); json.dump(tr, open(a.b, "w"))
        found = sum(1 for s in tr["samples"] if s[1] is not None)
        print(f"{a.b}: {len(tr['samples'])} samples, a face in {found} ({100 * found / max(1, len(tr['samples'])):.0f}%), {len(tr['cuts'])} scene cut(s)"); return
    if a.cmd == "apply" and a.a and a.b:
        edl, track = json.load(open(a.a)), json.load(open(a.b))
        edl, nface, nfit, nnone = apply(edl, track, a.smooth, a.deadzone)
        if not (nface + nfit + nnone): sys.exit("face_track: the output is not narrower than the source, so there is nothing to follow (leave output.reframe as it is)")
        json.dump(edl, open(a.out or a.a, "w"), indent=1)
        print(f"{a.out or a.a}: {nface} segment(s) follow the face, {nfit} fit the whole frame over a blurred copy" + (f", {nnone} not covered by the track (centred crop)" if nnone else "")); return
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
