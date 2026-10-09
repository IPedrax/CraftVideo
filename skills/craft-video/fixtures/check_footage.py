#!/usr/bin/env python3
"""check_footage.py edit.json OUT.mp4 rec.truth.json: ground-truth checks for an edit of make_footage.py's recording.

  keeps speech   >= 95% of every real speech run survives the cuts
  drops fillers  the "um" and "uh" spans are (almost) gone
  trims dead air the edit is shorter than the speech plus a modest allowance for the pauses it keeps
  stays in sync  the fixture's white box is ON exactly while speech plays, so in the OUTPUT the picture's box and the
                 audio's loudness must line up (best lag within one frame)
  quiets hiss    the gap between speech level and noise floor grows (only when the EDL asks for denoise)
Pass --no-hiss for a provider that does no audio processing. Exit 1 on any failure. Needs numpy and ffmpeg."""
import json, subprocess, sys
import numpy as np

edl, out, truth = json.load(open(sys.argv[1])), sys.argv[2], json.load(open(sys.argv[3]))
segs = edl["segments"]; fails = []
def cover(a, b): return sum(max(0.0, min(b, s["out"]) - max(a, s["in"])) for s in segs)
def step(name, ok, detail):
    print(f"  {'PASS' if ok else 'FAIL'} {name:<14} {detail}"); (None if ok else fails.append(name))

kept = [cover(a, b) / (b - a) for a, b in truth["speech_runs"]]
step("keeps speech", min(kept) >= 0.95, f"worst run keeps {min(kept) * 100:.0f}%")
fl = [cover(a, b) for a, b in truth["filler_spans"]]
step("drops fillers", max(fl, default=0) <= 0.1, f"{', '.join(f'{x:.2f}s' for x in fl)} of filler left")
total = sum(s["out"] - s["in"] for s in segs); allow = 0.5 * len(truth["speech_runs"]) + 2
step("trims dead air", total <= truth["speech_total"] + allow, f"{total:.1f}s kept, {truth['speech_total']:.1f}s is speech")

FPS = 30
raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", out, "-an", "-vf", f"fps={FPS},crop=70:80:20:20,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, 80, 70).reshape(-1, 5600).mean(axis=1)
box = frames > (frames.min() + frames.max()) / 2
wav = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", out, "-vn", "-ac", "1", "-ar", "48000", "-f", "f32le", "-"], capture_output=True).stdout
x = np.frombuffer(wav, np.float32)
hop = 480; n = len(x) // hop; rms = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(axis=1)); db = 20 * np.log10(rms + 1e-9)
thr = (np.percentile(db, 10) + np.percentile(db, 90)) / 2
speech = db > thr
# resample the 100 Hz speech track to frame rate, then find the lag that matches the box best
fa = np.array([speech[min(int(i / FPS * 100), n - 1)] for i in range(len(box))], float); fb = box.astype(float)
lags = range(-6, 7)
def agree(l): a = fa[max(0, l):len(fa) + min(0, l)]; b = fb[max(0, -l):len(fb) - max(0, l)]; return (a == b).mean()
best = max(lags, key=agree)
step("stays in sync", abs(best) <= 1 and agree(best) > 0.9, f"best lag {best} frames, {agree(best) * 100:.0f}% of frames agree")

if (edl.get("audio") or {}).get("denoise") and "--no-hiss" not in sys.argv:
    def dr(path):
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path, "-vn", "-ac", "1", "-ar", "48000", "-f", "f32le", "-"], capture_output=True).stdout
        y = np.frombuffer(r, np.float32); m = len(y) // hop; d = 20 * np.log10(np.sqrt((y[:m * hop].reshape(m, hop) ** 2).mean(axis=1)) + 1e-9)
        return np.percentile(d, 90) - np.percentile(d, 3)    # the 3rd percentile: an edit keeps few pauses, so the 10th would be speech
    a, b = dr(edl["source"]), dr(out)
    step("quiets hiss", b > a + 3, f"speech-to-floor gap {a:.0f} dB -> {b:.0f} dB")
sys.exit(1 if fails else 0)
