#!/usr/bin/env bash
# transcribe provider: bring your own transcript. CRAFTVIDEO_TRANSCRIPT_FILE points at JSON (with word times), SRT or WebVTT that
# matches the recording (a human transcript, an export from another tool). Word times from SRT/VTT are estimated per cue.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"file","kind":"transcribe","summary":"use an existing transcript (CRAFTVIDEO_TRANSCRIPT_FILE: JSON, SRT or VTT)","words":"JSON only; SRT/VTT are estimated","languages":"any","cloud":false}'; exit 0;;
  --check) [ -n "${CRAFTVIDEO_TRANSCRIPT_FILE:-}" ] && [ -s "$CRAFTVIDEO_TRANSCRIPT_FILE" ] && exit 0; echo "set CRAFTVIDEO_TRANSCRIPT_FILE to an existing transcript (json, srt or vtt)"; exit 1;;
esac
cp "$CRAFTVIDEO_TRANSCRIPT_FILE" "${2:?output}"
echo "file: using $CRAFTVIDEO_TRANSCRIPT_FILE" >&2
