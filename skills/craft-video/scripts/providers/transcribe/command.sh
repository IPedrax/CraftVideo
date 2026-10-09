#!/usr/bin/env bash
# transcribe provider: any speech-to-text command, by template. Whisper CLIs, whisper.cpp, vosk, a cloud CLI, your own script.
#   STT_CMD   required. Placeholders (shell-quoted): {audio} (16 kHz mono wav) {out} (where the result must be written)
#             {language} {model}
# The command may write {out} as our JSON, OpenAI-style verbose_json, faster-whisper-style segments, SRT or WebVTT: the dispatcher
# normalises it. Cue-level output (SRT/VTT) has no word times, so they are estimated (good for captions, not for filler cuts).
# Examples:
#   whisper-ctranslate2 {audio} --model small --word_timestamps True --output_format json --output_dir "$(dirname {out})"   (then point {out} at the .json)
#   whisper-cli -m /models/ggml-small.en.bin -f {audio} -osrt -of {out}.tmp && mv {out}.tmp.srt {out}                    (whisper.cpp, cue-level SRT)
#   python3 my_stt.py --audio {audio} --out {out}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"command","kind":"transcribe","summary":"any speech-to-text CLI via the STT_CMD template (whisper.cpp, Whisper CLIs, your script)","words":"if your command writes them","languages":"whatever the command handles","cloud":"depends on the command"}'; exit 0;;
  --check) [ -n "${STT_CMD:-}" ] || { echo "set STT_CMD (see the header of providers/transcribe/command.sh)"; exit 1; }; exit 0;;
esac
WAV="${1:?audio wav}"; OUT="${2:?output}"; shift 2
LANGN=""; MODEL=""; while [ $# -gt 0 ]; do case "$1" in --language) LANGN="$2";; --model) MODEL="$2";; esac; shift 2; done
CMD="$(cv_subst "$STT_CMD" "audio=$WAV" "out=$OUT" "language=$LANGN" "model=$MODEL")"
echo "command: $CMD" >&2
bash -c "$CMD" || { echo "command: STT_CMD exited with an error" >&2; exit 1; }
[ -s "$OUT" ] || { echo "command: STT_CMD wrote nothing to $OUT (does it use {out}?)" >&2; exit 1; }
