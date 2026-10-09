#!/usr/bin/env bash
# TTS provider: any command-line engine, by template. This is the escape hatch that makes the skill work with a TTS it has
# never heard of: Piper, espeak-ng, Coqui, edge-tts, a cloud CLI, your own script.
#   TTS_CMD   required. Placeholders are filled with shell-quoted values:
#             {script} plain text file (one sentence per line)   {out} where the audio must be written (any format ffmpeg reads)
#             {instruct} {seed} {language} {speed} {ref} {ref_text}   (empty when not given)
# Examples (set TTS_CMD to one of these):
#   piper --model /path/en_US-lessac-medium.onnx --output_file {out} < {script}
#   espeak-ng -v en-us -s 150 -f {script} -w {out}
#   edge-tts --file {script} --voice en-US-AndrewNeural --write-media {out}
#   python3 my_tts.py --text-file {script} --out {out} --seed {seed}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"command","kind":"tts","summary":"any CLI TTS via the TTS_CMD template (Piper, espeak-ng, Coqui, edge-tts, your own script)","design":"if your command supports it","clone":"if your command supports it","seed":"if your command supports it","speed":"if your command supports it","languages":"whatever the command speaks","cloud":"depends on the command"}'; exit 0;;
  --check) [ -n "${TTS_CMD:-}" ] || { echo "set TTS_CMD (see the header of providers/tts/command.sh for examples)"; exit 1; }; exit 0;;
esac
PLAIN="${1:?plain text file}"; OUT="${2:?output audio}"; shift 2
INSTRUCT=""; SEED=""; LANGN=""; SPEED=""; REF=""; REFTEXT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --instruct) INSTRUCT="$2"; shift 2;; --seed) SEED="$2"; shift 2;; --language) LANGN="$2"; shift 2;; --speed) SPEED="$2"; shift 2;;
    --ref) REF="$2"; shift 2;; --ref-text) REFTEXT="$2"; shift 2;; *) shift;;
  esac
done
CMD="$(cv_subst "$TTS_CMD" "script=$PLAIN" "out=$OUT" "instruct=$INSTRUCT" "seed=$SEED" "language=$LANGN" "speed=$SPEED" "ref=$REF" "ref_text=$REFTEXT")"
echo "command: $CMD" >&2
bash -c "$CMD" || { echo "command: TTS_CMD exited with an error" >&2; exit 1; }
[ -s "$OUT" ] || { echo "command: TTS_CMD ran but wrote nothing to $OUT (does it use {out}?)" >&2; exit 1; }
