#!/usr/bin/env python3
"""make_footage.py OUTDIR: a deterministic fake "recording" for testing the edit pipeline. Not speech: speech-shaped bursts.

Writes OUTDIR/rec.mp4 (1280x720 @ 30, 36 s), rec.transcript.json (word timings that are exact by construction) and
rec.truth.json (the speech runs and filler spans the analysers should find).

Audio: bursts with long pauses, two filler sounds ("um", "uh"), low hiss and 50 Hz hum (so highpass/denoise have work).
Video: testsrc2, plus a bright box top-left that is ON exactly while a burst plays. That makes sync checkable after
editing: the audio's loudness envelope and the box's brightness must line up.
Needs numpy, soundfile and ffmpeg."""
import json, os, subprocess, sys
import numpy as np
import soundfile as sf

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
SR, DUR = 48000, 36.0
rng = np.random.default_rng(11)
# (start, end, words) per burst; fillers are their own tiny bursts. Pauses between bursts are the dead air to cut.
S = [
    (1.00, 4.20, "so today we are going to look at one thing".split()),
    (6.50, 7.55, "and the first part".split()),
    (7.62, 7.98, ["um"]),
    (8.05, 10.00, "is really quite simple".split()),
    (10.40, 13.00, "you start with the recording".split()),
    (17.50, 18.60, "then we listen".split()),
    (18.72, 19.05, ["uh"]),
    (19.12, 21.00, "for the quiet parts".split()),
    (24.00, 27.50, "and we cut them out without touching the speech".split()),
    (30.50, 34.00, "that is all there is to it".split()),
]
FILLERS = {"um", "uh"}


def burst(n, pitch):
    t = np.arange(n) / SR
    syl = 0.55 + 0.45 * np.sin(2 * np.pi * 4.2 * t + rng.uniform(0, 6))
    tone = np.sin(2 * np.pi * (pitch + 25 * np.sin(2 * np.pi * 0.7 * t)) * t) + 0.5 * np.sin(2 * np.pi * 3 * pitch * t)
    env = np.minimum(1, np.minimum(t, t[::-1]) / 0.03)
    return (tone + rng.standard_normal(n) * 0.35) * syl * env * 0.35


audio = np.zeros(int(DUR * SR))
words, runs, fill = [], [], []
for s, e, ws in S:
    n = int((e - s) * SR); i = int(s * SR)
    audio[i:i + n] += burst(n, 190 if ws[0] not in FILLERS else 150)
    step = (e - s) / len(ws)
    for k, w in enumerate(ws):
        words.append({"text": w, "start": round(s + k * step, 3), "end": round(s + (k + 1) * step - 0.02, 3)})
    (fill if ws[0] in FILLERS else runs).append([s, e])
t = np.arange(len(audio)) / SR
audio += rng.standard_normal(len(audio)) * 0.0035 + 0.003 * np.sin(2 * np.pi * 50 * t)       # hiss (about -49 dB) and hum
audio *= 0.5                                                                                  # a quiet recording
sf.write(os.path.join(out, "rec.wav"), audio, SR, subtype="PCM_16")

box = "+".join(f"between(t,{s},{e})" for s, e, _ in S)
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"testsrc2=s=1280x720:r=30:d={DUR}", "-i", os.path.join(out, "rec.wav"),
                "-vf", f"drawbox=x=20:y=20:w=120:h=120:color=white:t=fill:enable='{box}'",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest",
                os.path.join(out, "rec.mp4")], check=True)
json.dump({"language": "en", "source": "construction", "words": words}, open(os.path.join(out, "rec.transcript.json"), "w"), indent=1)
json.dump({"duration": DUR, "speech_runs": runs, "filler_spans": fill, "speech_total": round(sum(e - s for s, e in runs), 2)},
          open(os.path.join(out, "rec.truth.json"), "w"), indent=1)
os.remove(os.path.join(out, "rec.wav"))
print(f"{out}/rec.mp4 {DUR}s, {len(words)} words, {len(runs)} speech runs, {len(fill)} fillers")
