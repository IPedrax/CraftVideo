#!/usr/bin/env bash
# narrate.sh: generate narration with VoiceStudio (default engine VoxCPM2, Apache-2.0 weights).
#   narrate.sh script.txt narration_raw.wav [--instruct "(voice description)"] [--seed N] [--engine voxcpm2]
#              [--ref ref.wav --ref-text "what the reference says"] [--speed 1.0]
# script.txt: one sentence per line, optional "label | sentence" (labels are stripped here).
# Without --ref the voice is DESIGNED from --instruct; with --ref it is CLONED (only clone voices you have permission to use).
# Leaves the backend running (more takes are common); stop it when you are done: voicestudio-backend stop
set -euo pipefail
SCRIPT="${1:?usage: narrate.sh script.txt narration_raw.wav [options]}"; OUT="${2:?output wav}"; shift 2
INSTRUCT="(a confident, measured narrator, documentary tone, clear and natural, studio quality)"
SEED=20261009; ENGINE=voxcpm2; REF=""; REFTEXT=""; SPEED=""
while [ $# -gt 0 ]; do
  case "$1" in
    --instruct) INSTRUCT="$2"; shift 2;; --seed) SEED="$2"; shift 2;; --engine) ENGINE="$2"; shift 2;;
    --ref) REF="$2"; shift 2;; --ref-text) REFTEXT="$2"; shift 2;; --speed) SPEED="$2"; shift 2;;
    *) echo "unknown option $1" >&2; exit 2;;
  esac
done
[ -z "$REF" ] || [ -n "$REFTEXT" ] || { echo "--ref needs --ref-text (the transcript of the reference clip)" >&2; exit 2; }
URL=http://127.0.0.1:3900
TEXT=$(grep -v '^\s*#' "$SCRIPT" | sed -E 's/^[^|]{1,40}\|\s*//' | tr '\n' ' ' | sed -E 's/\s+/ /g; s/\s+$//')
echo "narrating ${#TEXT} characters, about $(echo "$TEXT" | wc -w | awk '{printf "%.0f", $1 / 2.6}') s expected (VoxCPM2 speaks about 2.6 words/s)"

voicestudio-backend start >/dev/null
# the startup preload can leave OmniVoice resident, and two engines do not fit in 12 GB
curl -s -m 60 -X POST $URL/system/flush-memory >/dev/null || true

ARGS=(--form-string "text=$TEXT" -F language=English -F "engine=$ENGINE" -F "seed=$SEED")
[ -n "$SPEED" ] && ARGS+=(-F "speed=$SPEED")
if [ -n "$REF" ]; then
  ARGS+=(-F "ref_audio=@$REF" --form-string "ref_text=$REFTEXT")
else
  ARGS+=(--form-string "instruct=$INSTRUCT")
fi
HDR=$(mktemp)
CODE=$(curl -s -m 900 -D "$HDR" -o "$OUT" -w '%{http_code}' -X POST $URL/generate "${ARGS[@]}")
if [ "$CODE" != "200" ]; then
  echo "generate failed (HTTP $CODE): $(head -c 400 "$OUT")" >&2
  echo "hint: 503 usually means another engine is holding VRAM: voicestudio-backend stop; start; retry" >&2
  rm -f "$HDR"; exit 1
fi
echo "ok: $OUT, $(grep -i x-audio-duration "$HDR" | tr -d '\r' | awk '{print $2}') s of audio in $(grep -i x-gen-time "$HDR" | tr -d '\r' | awk '{print $2}') s (seed $SEED)"
rm -f "$HDR"
