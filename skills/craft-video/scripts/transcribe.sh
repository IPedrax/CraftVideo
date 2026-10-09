#!/usr/bin/env bash
# transcribe.sh: the speech-to-text dispatcher. Recording (video or audio) -> transcript.json with word timings.
#   transcribe.sh recording.mp4 transcript.json [--provider NAME] [--language en] [--model small]
# Provider order: --provider, env CRAFTVIDEO_TRANSCRIBE, ./craftvideo.json, ~/.config/craftvideo/config.json, then faster-whisper,
# openai. Providers are handed a 16 kHz mono wav; whatever they return (our JSON, OpenAI verbose_json, faster-whisper segments, SRT,
# WebVTT) is normalised and validated here (transcript_norm.py), so a new engine only has to write one of those.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
IN="${1:?usage: transcribe.sh recording transcript.json [--provider NAME] [--language en] [--model small]}"; OUT="${2:?output json}"; shift 2
PROV=""; LANGN=""; MODEL=""
while [ $# -gt 0 ]; do
  [ $# -ge 2 ] || cv_die "option $1 needs a value"
  case "$1" in --provider) PROV="$2";; --language) LANGN="$2";; --model) MODEL="$2";; *) cv_die "unknown option $1";; esac; shift 2
done
[ -s "$IN" ] || cv_die "recording not found: $IN"
NAME="$(cv_resolve transcribe "$PROV")"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
ffmpeg -hide_banner -loglevel error -y -i "$IN" -vn -ac 1 -ar 16000 -c:a pcm_s16le "$T/audio.wav" || cv_die "could not extract audio from $IN (does it have an audio track?)"
DUR="$(cv_dur "$T/audio.wav")"
echo "transcribing ${DUR%.*}s of audio with provider '$NAME'" >&2
ARGS=(); [ -z "$LANGN" ] || ARGS+=(--language "$LANGN"); [ -z "$MODEL" ] || ARGS+=(--model "$MODEL")
bash "$(cv_provider_script transcribe "$NAME")" "$T/audio.wav" "$T/raw.out" "${ARGS[@]}"
[ -s "$T/raw.out" ] || cv_die "provider '$NAME' produced no transcript"
"$CV_PY" "$CV_HERE/transcript_norm.py" "$T/raw.out" "$OUT" --duration "$DUR" --source "$NAME" --audio "$T/audio.wav" ${LANGN:+--language "$LANGN"}
