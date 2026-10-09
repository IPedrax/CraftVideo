#!/usr/bin/env bash
# TTS provider: dryrun. NOT a voice: speech-shaped noise bursts, one per sentence, with sentence-length and pause patterns like
# real narration (about 2.6 words per second, longer gaps between sentences than between clauses). Lets you build and review
# scenes, music cues and the whole pipeline in seconds with no model, no GPU and no network. Never auto-selected; never ship it.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"dryrun","kind":"tts","summary":"placeholder speech-shaped audio for timing and previews (not a voice)","design":false,"clone":false,"seed":false,"speed":true,"languages":"any","cloud":false}'; exit 0;;
  --check) "$CV_PY" -c "import numpy, soundfile" 2>/dev/null && exit 0; echo "needs numpy + soundfile (set VIDEO_PY)"; exit 1;;
esac
PLAIN="${1:?plain text file}"; OUT="${2:?output audio}"; shift 2
SPEED=1.0; while [ $# -gt 0 ]; do case "$1" in --speed) SPEED="$2"; shift 2;; *) shift;; esac; done
"$CV_PY" - "$PLAIN" "$OUT" "$SPEED" <<'PY'
import sys, re, numpy as np, soundfile as sf
plain, out, speed = sys.argv[1], sys.argv[2], float(sys.argv[3]); SR = 48000
rng = np.random.default_rng(1)
def burst(words):
    n = int(SR * words / 2.6 / speed); t = np.arange(n) / SR
    syl = 0.55 + 0.45 * np.sin(2 * np.pi * 4.2 * t + rng.uniform(0, 6))          # syllable rhythm
    tone = np.sin(2 * np.pi * (110 + 25 * np.sin(2 * np.pi * 0.7 * t)) * t) + 0.5 * np.sin(2 * np.pi * 330 * t)
    noise = rng.standard_normal(n) * 0.35
    env = np.minimum(1, np.minimum(t, t[::-1]) / 0.04)
    return (tone + noise) * syl * env * 0.25
parts = [np.zeros(int(SR * 0.15))]
for line in (l.strip() for l in open(plain, encoding="utf-8") if l.strip()):
    clauses = [c for c in re.split(r"(?<=[,;:])\s+", line) if c]
    for k, c in enumerate(clauses):
        parts.append(burst(max(1, len(c.split()))))
        parts.append(np.zeros(int(SR * (0.22 if k < len(clauses) - 1 else 0.5))))   # clause pause vs sentence pause
sf.write(out, np.concatenate(parts), SR, subtype="PCM_16", format="WAV")
print("dryrun: placeholder audio (not a voice)", file=sys.stderr)
PY
