#!/usr/bin/env bash
# transcribe provider: any OpenAI-compatible speech-to-text endpoint (POST {base}/audio/transcriptions): OpenAI itself, Speaches,
# LocalAI, VoiceStudio's /v1 (once it has an ASR model installed), whisper.cpp servers.
#   OPENAI_BASE_URL  required (a LOCAL server keeps the audio on this machine)    OPENAI_API_KEY  optional
#   STT_MODEL        default whisper-1
# Asks for verbose_json with word timestamps. A hosted endpoint uploads the recording's audio to a third party: only with consent.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"openai","kind":"transcribe","summary":"any OpenAI-compatible /audio/transcriptions server (OpenAI, Speaches, LocalAI, whisper.cpp server)","words":true,"languages":"server dependent","cloud":"depends on OPENAI_BASE_URL"}'; exit 0;;
  --check)
    [ -n "${OPENAI_BASE_URL:-}" ] || { echo "set OPENAI_BASE_URL (and STT_MODEL) to enable"; exit 1; }
    command -v curl >/dev/null || { echo "curl missing"; exit 1; }
    code=$(curl -s -m 5 -o /dev/null -w '%{http_code}' ${OPENAI_API_KEY:+-H "Authorization: Bearer $OPENAI_API_KEY"} "${OPENAI_BASE_URL%/}/models" 2>/dev/null || true)
    case "$code" in 2*|401|403|404|405) exit 0;; *) echo "no server answering at $OPENAI_BASE_URL (HTTP ${code:-none})"; exit 1;; esac;;
esac
WAV="${1:?audio wav}"; OUT="${2:?output json}"; shift 2
LANGN=""; while [ $# -gt 0 ]; do case "$1" in --language) LANGN="$2";; esac; shift 2; done
CODE=$(curl -s -m 1800 -o "$OUT" -w '%{http_code}' ${OPENAI_API_KEY:+-H "Authorization: Bearer $OPENAI_API_KEY"} \
  -F "file=@$WAV" -F "model=${STT_MODEL:-whisper-1}" -F response_format=verbose_json -F "timestamp_granularities[]=word" -F "timestamp_granularities[]=segment" \
  ${LANGN:+-F "language=$LANGN"} "${OPENAI_BASE_URL%/}/audio/transcriptions")
[ "$CODE" = 200 ] || { echo "openai: transcription failed (HTTP $CODE): $(head -c 300 "$OUT")" >&2; exit 1; }
