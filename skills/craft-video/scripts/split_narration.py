#!/usr/bin/env python3
"""split_narration.py: give every sentence boundary of a narration a real pause, when the voice ran sentences together.

  split_narration.py --raw narration_raw.wav --script script.txt --transcript transcript.json --out narration_split.wav \
                     [--breaks-out breaks.json] [--pause 0.3]

tighten_voice.py finds sentence starts from the pauses in the audio. A long script spoken in one pass often has boundaries with no
pause at all ("...for criminal cases. A law that February..."), while commas inside a sentence do have one, so the automatic match
picks the wrong ones. This script uses WORD TIMES instead (transcribe.sh gives them):
  1. align each script line to the transcript: search near where the line should start (by characters spoken) for the place where its
     first words follow in sequence, preferring a long silence before it
  2. at each boundary, if the audio already has a pause of at least `pause` seconds, leave it; otherwise cut at the quietest point
     between the two words and insert silence there (4 ms fades at the seam, so nothing clicks)
  3. write the new audio and breaks.json (the time of each boundary's pause in the NEW audio), which tighten_voice.py takes as --breaks
Speech is never stretched or removed. Prints one row per line with the pause it found or made. Needs numpy and soundfile."""
import argparse, json, re, sys
import numpy as np
import soundfile as sf

NORM = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())


def read_script(path):
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"): continue
        lab, _, txt = line.partition("|")
        out.append((lab.strip(), txt.strip()) if _ else (f"s{len(out) + 1}", line))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True); ap.add_argument("--script", required=True); ap.add_argument("--transcript", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--breaks-out", default="breaks.json"); ap.add_argument("--pause", type=float, default=0.3)
    a = ap.parse_args(argv)
    x, sr = sf.read(a.raw)
    if x.ndim > 1: x = x.mean(axis=1)
    lines = read_script(a.script); W = json.load(open(a.transcript))["words"]; n = len(lines)
    # ---- 1. align each line's first word ----
    chars = [len(NORM(t)) or 1 for _, t in lines]; wchars = np.cumsum([len(NORM(w["text"])) or 1 for w in W]); total_w = wchars[-1]
    starts, prev = [0], 0
    for k in range(1, n):
        want = sum(chars[:k]) / sum(chars) * total_w                     # where line k should start, by characters spoken
        centre = int(np.searchsorted(wchars, want)); toks = [NORM(t) for t in lines[k][1].split()][:5]
        cands = [i for i in range(max(prev + 1, centre - 14), min(len(W), centre + 15))]
        if not cands: sys.exit(f"split_narration: no transcript words left to place line {k + 1} ({lines[k][0]})")
        def score(i):                                                     # how many leading words of the line follow in sequence, then the silence before, then nearness
            run = 0
            while run < len(toks) and i + run < len(W) and NORM(W[i + run]["text"]) == toks[run]: run += 1
            gap = W[i]["start"] - W[i - 1]["end"]
            return run * 1.0 + min(gap, 1.0) + (W[i - 1]["text"][-1:] in ".?!") * 0.4 - abs(i - centre) * 0.02
        best = max(cands, key=score); starts.append(best); prev = best
    # ---- 2. a real pause at every boundary ----
    hop = int(0.005 * sr); db = 20 * np.log10(np.sqrt(np.convolve(x * x, np.ones(hop) / hop, mode="same"))[::hop] + 1e-9)
    def silence_run(lo, hi, thr=-38):                                      # longest run of quiet frames inside [lo, hi] seconds
        f0, f1 = int(lo / 0.005), int(hi / 0.005); best, cur, start = (0, 0), 0, 0
        for i in range(f0, min(f1, len(db))):
            if db[i] < thr:
                if cur == 0: start = i
                cur += 1
                if cur > best[0]: best = (cur, start)
            else: cur = 0
        return best[0] * 0.005, (best[1] + best[0] / 2) * 0.005
    pieces, cursor, shift, breaks, rows = [], 0, 0.0, [], []
    for k in range(1, n):
        i = starts[k]; pe, ns = W[i - 1]["end"], W[i]["start"]
        run, centre = silence_run(pe - 0.12, ns + 0.12)
        if run < a.pause * 0.8 and ns - pe <= 0.05:                         # a zero gap means Whisper stretched a word: look ahead for the real pause
            run2, centre2 = silence_run(pe, ns + 1.0)
            if run2 >= 0.4: run, centre = run2, centre2
        if run >= a.pause * 0.8:
            breaks.append(round(centre + shift, 3)); rows.append((lines[k][0], "pause", run)); continue
        lo, hi = int(max(0, pe - 0.02) / 0.005), int(min(len(x) / sr, ns + 0.05) / 0.005) + 1
        cut = (lo + int(np.argmin(db[lo:max(lo + 1, hi)]))) * hop                     # the quietest 5 ms between the two words
        add = int(round((a.pause - run) * sr)); fade = int(0.004 * sr)
        left = x[cursor:cut].copy(); left[-fade:] *= np.linspace(1, 0, min(fade, len(left)))
        pieces.append(left); pieces.append(np.zeros(add))
        right_start = cut; cursor = right_start
        nxt = x[cursor:cursor + fade].copy()                                # fade the first samples of what follows
        x = x.copy(); x[cursor:cursor + fade] = nxt * np.linspace(0, 1, len(nxt))
        shift += add / sr; breaks.append(round(cut / sr + (a.pause - run) / 2 + (shift - add / sr), 3)); rows.append((lines[k][0], "inserted", a.pause - run))
    pieces.append(x[cursor:]); y = np.concatenate(pieces)
    sf.write(a.out, y, sr, subtype="PCM_16"); json.dump(breaks, open(a.breaks_out, "w"))
    print(f"{a.out}: {len(y) / sr:.2f}s (raw {len(x) / sr:.2f}s), {len(breaks)} boundaries, {sum(1 for r in rows if r[1] == 'inserted')} pauses inserted")
    for k, (lab, how, d) in enumerate(rows, 1): print(f"  before {lab:11s} {how:9s} {d:5.2f}s  at {breaks[k - 1]:6.2f}s")


def selftest():
    """Three lines: a natural 0.5 s pause before line b, none at all before line c (the voice runs b into c). Both must end up with a pause."""
    import os, tempfile
    d = tempfile.mkdtemp(); sr = 16000; t = np.arange(int(4.2 * sr)) / sr; rng = np.random.default_rng(3)
    x = rng.standard_normal(len(t)) * 0.0015
    for a, b in ((0.2, 1.2), (1.7, 2.7), (2.7, 3.7)):                      # b and c touch: speech with a brief dip, no silence
        m = (t >= a) & (t < b); edge = np.minimum(1, np.minimum(t[m] - a, b - t[m]) / 0.02)
        x[m] += 0.3 * np.sin(2 * np.pi * 170 * t[m]) * (0.55 + 0.45 * np.sin(2 * np.pi * 3 * t[m])) * edge
    sf.write(f"{d}/raw.wav", x, sr)
    open(f"{d}/script.txt", "w").write("a | one two\nb | three four\nc | five six\n")
    W = [("one", .2, .7), ("two", .7, 1.2), ("three", 1.7, 2.2), ("four", 2.2, 2.7), ("five", 2.7, 3.2), ("six", 3.2, 3.7)]
    json.dump({"words": [{"text": w, "start": s0, "end": e0} for w, s0, e0 in W]}, open(f"{d}/t.json", "w"))
    main(["--raw", f"{d}/raw.wav", "--script", f"{d}/script.txt", "--transcript", f"{d}/t.json", "--out", f"{d}/out.wav", "--breaks-out", f"{d}/b.json"])
    y, _ = sf.read(f"{d}/out.wav"); br = json.load(open(f"{d}/b.json"))
    assert len(br) == 2, br
    assert 0.28 <= len(y) / sr - len(x) / sr <= 0.4, (len(y) / sr, len(x) / sr)                 # one 0.3 s pause was inserted, the natural one was left alone
    for b in br:                                                                                 # every break sits inside real silence of 0.25 s or more
        lo, hi = int((b - 0.14) * sr), int((b + 0.14) * sr)
        assert np.sqrt((y[lo:hi] ** 2).mean()) < 0.01, (b, np.sqrt((y[lo:hi] ** 2).mean()))
    assert abs(np.sqrt((y ** 2).sum()) - np.sqrt((x ** 2).sum())) / np.sqrt((x ** 2).sum()) < 0.02   # no speech was removed or stretched
    print("split_narration selftest: ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest": selftest()
    else: main()
