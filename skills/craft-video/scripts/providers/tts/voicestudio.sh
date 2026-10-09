#!/usr/bin/env bash
# TTS provider: VoiceStudio (local REST on 127.0.0.1:3900; default engine VoxCPM2, Apache-2.0 weights).
# Designs a voice from --instruct or clones one from --ref. Needs a VoiceStudio source checkout (VOICESTUDIO_DIR).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
MODELS="${VOICESTUDIO_MODELS:-$CV_VS/.vs/models}"
case "${1:-}" in
  --info)  echo '{"name":"voicestudio","kind":"tts","summary":"local VoiceStudio REST, VoxCPM2 default (voice design + cloning, 30 languages)","design":true,"clone":true,"seed":true,"speed":true,"languages":"30 (engine dependent)","cloud":false}'; exit 0;;
  --check)
    [ -d "$CV_VS/backend" ] || { echo "no VoiceStudio checkout at $CV_VS (set VOICESTUDIO_DIR)"; exit 1; }
    [ -d "$MODELS/models--openbmb--VoxCPM2" ] || { echo "VoxCPM2 weights not found in $MODELS"; exit 1; }
    command -v curl >/dev/null || { echo "curl missing"; exit 1; }; exit 0;;
esac
PLAIN="${1:?plain text file}"; OUT="${2:?output audio}"; shift 2
INSTRUCT="(a confident, measured narrator, documentary tone, clear and natural, studio quality)"
SEED=20261009; ENGINE=voxcpm2; REF=""; REFTEXT=""; SPEED=""; LANGN=English
while [ $# -gt 0 ]; do
  case "$1" in
    --instruct) INSTRUCT="$2"; shift 2;; --seed) SEED="$2"; shift 2;; --engine) ENGINE="$2"; shift 2;;
    --ref) REF="$2"; shift 2;; --ref-text) REFTEXT="$2"; shift 2;; --speed) SPEED="$2"; shift 2;; --language) LANGN="$2"; shift 2;;
    *) shift;;
  esac
done
URL=http://127.0.0.1:3900
TEXT=$(tr '\n' ' ' < "$PLAIN" | sed -E 's/\s+/ /g; s/\s+$//')
bash "$CV_HERE/voicestudio-backend" start >/dev/null
# the startup preload can leave OmniVoice resident, and two engines do not fit in 12 GB
curl -s -m 60 -X POST $URL/system/flush-memory >/dev/null || true
ARGS=(--form-string "text=$TEXT" -F "language=$LANGN" -F "engine=$ENGINE" -F "seed=$SEED")
[ -n "$SPEED" ] && ARGS+=(-F "speed=$SPEED")
if [ -n "$REF" ]; then ARGS+=(-F "ref_audio=@$REF" --form-string "ref_text=$REFTEXT"); else ARGS+=(--form-string "instruct=$INSTRUCT"); fi
HDR=$(mktemp)
CODE=$(curl -s -m 900 -D "$HDR" -o "$OUT" -w '%{http_code}' -X POST $URL/generate "${ARGS[@]}")
if [ "$CODE" != "200" ]; then
  echo "voicestudio: generate failed (HTTP $CODE): $(head -c 400 "$OUT")" >&2
  echo "hint: 503 usually means another engine is holding VRAM: bash $CV_HERE/voicestudio-backend stop; start; retry" >&2
  rm -f "$HDR"; exit 1
fi
echo "voicestudio: $(grep -i x-audio-duration "$HDR" | tr -d '\r' | awk '{print $2}') s of audio in $(grep -i x-gen-time "$HDR" | tr -d '\r' | awk '{print $2}') s (seed $SEED)" >&2
rm -f "$HDR"
