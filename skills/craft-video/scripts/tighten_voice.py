#!/usr/bin/env python3
"""tighten_voice.py: make narration land on an exact length and tell you where each sentence starts.

Cuts ONLY inside pauses, so the speech is never time-stretched. Sentence boundaries are found by matching the
N-1 sentence breaks of your script to the detected pauses (character-proportional position; recovered 8 of 8 on
the first video), or you can pin them with --breaks. Writes the tightened WAV plus timeline.json:
  {"sentences":[{"label","start","end"}...], "speech_end", "total"}   (seconds in the NEW audio)
Scenes should be timed from those starts, not the other way round.

  tighten_voice.py --raw narration_raw.wav --script script.txt --out narration.wav --timeline timeline.json \
                   [--target 30] [--lead 0.4] [--gap 0.26] [--gaps 0.26,0.2,...] [--breaks 1.54,6.72,...]
script.txt: one sentence per line, optionally `label | sentence`.
Needs numpy + soundfile (the VoiceStudio venv has them) and ffmpeg."""
import argparse, json, re, subprocess, sys
import numpy as np
import soundfile as sf

PAD = 0.05            # keep this much of the surrounding silence on each cut so words never clip
FADE = 0.008


def pauses(path, noise_db, min_d):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
                          f"silencedetect=n={noise_db}dB:d={min_d}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    return [(max(0.0, s), en[i] if i < len(en) else None) for i, s in enumerate(st)]


def read_script(path):
    out = []
    for n, line in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        label, text = (x.strip() for x in line.split("|", 1)) if "|" in line else (f"s{len(out) + 1}", line)
        out.append((label, text))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--script", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--target", type=float, default=30.0)
    ap.add_argument("--lead", type=float, default=0.4)
    ap.add_argument("--gap", type=float, default=0.26)
    ap.add_argument("--gaps", help="per-boundary gaps, comma separated (overrides --gap)")
    ap.add_argument("--breaks", help="seconds in the RAW audio of each sentence break, comma separated")
    ap.add_argument("--noise-db", type=float, default=-38)
    ap.add_argument("--min-pause", type=float, default=0.16)
    a = ap.parse_args()

    x, sr = sf.read(a.raw)
    total = len(x) / sr
    sentences = read_script(a.script)
    n = len(sentences)
    allp = pauses(a.raw, a.noise_db, a.min_pause)
    speech_start, speech_end, inner = 0.0, total, []
    for s, e in allp:
        if s <= 0.03 and e is not None:
            speech_start = e                     # leading silence
        elif e is None or e >= total - 0.03:
            speech_end = s                       # trailing silence
        else:
            inner.append((s, e))
    if n > 1 and len(inner) < n - 1:
        sys.exit(f"found {len(inner)} inner pauses but the script has {n - 1} sentence breaks; "
                 f"try --noise-db -34 or --min-pause 0.12, or pass --breaks")

    # --- choose which pauses are sentence breaks ---
    if n == 1:
        picks = []
    elif a.breaks:
        wanted = [float(v) for v in a.breaks.split(",")]
        assert len(wanted) == n - 1, "--breaks needs one time per sentence break"
        picks = sorted({min(range(len(inner)), key=lambda i: abs(inner[i][0] - w)) for w in wanted})
        assert len(picks) == n - 1, "two --breaks snapped to the same pause"
    else:
        chars = [len(re.sub(r"[^A-Za-z0-9]", "", t)) or 1 for _, t in sentences]
        speech_len = (speech_end - speech_start) - sum(e - s for s, e in inner)
        used, picks, cum = set(), [], 0
        for k in range(n - 1):
            cum += chars[k]
            want = cum / sum(chars) * speech_len              # position in pause-free speech time
            def speech_before(i):
                return inner[i][0] - speech_start - sum(e - s for s, e in inner[:i])
            best = min((i for i in range(len(inner)) if i not in used), key=lambda i: abs(speech_before(i) - want))
            used.add(best); picks.append(best)
        picks.sort()

    # --- rebuild: lead + spans joined with fixed gaps + exact-length tail ---
    bounds = [inner[i] for i in picks]
    spans = []
    for k, (label, _) in enumerate(sentences):
        s = speech_start if k == 0 else bounds[k - 1][1]
        e = speech_end if k == n - 1 else bounds[k][0]
        spans.append((label, s, e))
    gaps = [float(v) for v in a.gaps.split(",")] if a.gaps else [a.gap] * (n - 1)
    fade = int(FADE * sr)
    shape = (0,) if x.ndim == 1 else (0, x.shape[1])
    parts, t, starts = [np.zeros((int(a.lead * sr),) + shape[1:])], a.lead, []
    for k, (label, s, e) in enumerate(spans):
        i0, i1 = int(max(0.0, s - PAD) * sr), int(min(total, e + PAD) * sr)
        seg = x[i0:i1].copy()
        ramp_in, ramp_out = np.linspace(0, 1, fade), np.linspace(1, 0, fade)
        if seg.ndim > 1:
            ramp_in, ramp_out = ramp_in[:, None], ramp_out[:, None]
        seg[:fade] *= ramp_in; seg[-fade:] *= ramp_out
        starts.append({"label": label, "start": round(t + min(PAD, s), 3)})
        parts.append(seg); t += len(seg) / sr
        starts[-1]["end"] = round(t - PAD, 3)
        if k < n - 1:
            g = max(0.0, gaps[k] - 2 * PAD)                  # the segments already carry PAD each side
            parts.append(np.zeros((int(g * sr),) + shape[1:])); t += g
    tail = a.target - t
    if tail < 0.3:
        sys.exit(f"narration is {-tail + 0.3:.2f}s too long for {a.target}s: shorten the script, lower --lead/--gap, "
                 f"or regenerate with --speed 1.05")
    parts.append(np.zeros((int(round(tail * sr)),) + shape[1:]))
    y = np.concatenate(parts)[: int(a.target * sr)]
    sf.write(a.out, y, sr, subtype="PCM_16")
    info = {"sentences": starts, "speech_end": starts[-1]["end"], "total": round(len(y) / sr, 3),
            "raw_total": round(total, 3), "breaks_used_raw": [round(b[0], 2) for b in bounds]}
    json.dump(info, open(a.timeline, "w"), indent=2)
    print(f"{a.out}: {info['total']}s (raw {info['raw_total']}s, speech ends {info['speech_end']}s, tail {tail:.2f}s)")
    for s in starts:
        print(f"  {s['start']:6.2f} - {s['end']:6.2f}  {s['label']}")


if __name__ == "__main__":
    main()
