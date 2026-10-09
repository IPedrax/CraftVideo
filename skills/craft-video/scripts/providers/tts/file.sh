#!/usr/bin/env bash
# TTS provider: bring your own narration. Point CRAFTVIDEO_NARRATION_FILE at a finished recording of the script (a voice actor,
# your own voice, another tool's export). Any audio format ffmpeg reads. The rest of the pipeline treats it like generated audio:
# tighten_voice.py finds the sentence starts from the pauses in it, so it must be read in the order of script.txt.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"file","kind":"tts","summary":"use an existing narration recording (CRAFTVIDEO_NARRATION_FILE)","design":false,"clone":false,"seed":false,"speed":false,"languages":"any","cloud":false}'; exit 0;;
  --check) [ -n "${CRAFTVIDEO_NARRATION_FILE:-}" ] && [ -s "$CRAFTVIDEO_NARRATION_FILE" ] && exit 0; echo "set CRAFTVIDEO_NARRATION_FILE to an existing audio file"; exit 1;;
esac
OUT="${2:?output audio}"
cp "$CRAFTVIDEO_NARRATION_FILE" "$OUT.src" && ffmpeg -hide_banner -loglevel error -y -i "$OUT.src" -f wav -c:a pcm_s16le "$OUT" && rm -f "$OUT.src"
echo "file: using $CRAFTVIDEO_NARRATION_FILE" >&2
