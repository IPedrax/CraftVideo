#!/usr/bin/env python3
"""qa_sync.py video.mp4 narration.wav: cross-correlates the 10 ms loudness envelope of the exported audio with the
narration to find the offset. Prints the best lag in ms (0 = in sync); exits 1 if it is more than 40 ms (a frame)."""
import subprocess, sys, tempfile, os
import numpy as np
import soundfile as sf

video, voice = sys.argv[1], sys.argv[2]
tmp = tempfile.mkdtemp()
wav = os.path.join(tmp, "a.wav")
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "48000", wav], check=True)
a, sr = sf.read(wav); v, _ = sf.read(voice)
if v.ndim > 1: v = v.mean(axis=1)
n = min(len(a), len(v)); a, v = a[:n], v[:n]
env = lambda x, w=480: np.sqrt(np.convolve(x * x, np.ones(w) / w, mode="same"))[::w]
ea, ev = env(a), env(v); ea = ea - ea.mean(); ev = ev - ev.mean()
lags = list(range(-30, 31))
cc = [np.dot(ea[max(0, l):len(ea) + min(0, l)], ev[max(0, -l):len(ev) - max(0, l)]) for l in lags]
best = lags[int(np.argmax(cc))] * 10
print(f"narration sync: best lag {best} ms (0 = in sync)")
os.remove(wav); os.rmdir(tmp)
sys.exit(0 if abs(best) <= 40 else 1)
