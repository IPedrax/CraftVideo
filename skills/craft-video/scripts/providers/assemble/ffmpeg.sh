#!/usr/bin/env bash
# assemble provider: plain ffmpeg. The universal fallback: no editor needed. Mixes narration + music (music at --music-db),
# normalises the mix to --lufs with a two-pass loudnorm (true peak -1.5 dB), copies the picture untouched, muxes H.264 + AAC.
#   ffmpeg.sh --video V [--voice N] [--music M] --out OUT [--music-db -9] [--lufs -16] [--bitrate 16000] [--project ignored]
# No interchange export (there is no timeline): use the filmcraft provider when another editor needs one.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"ffmpeg","kind":"assemble","summary":"ffmpeg mix + two-pass loudnorm + mux; no editor required","interchange":"","needs":"ffmpeg"}'; exit 0;;
  --check) command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null && exit 0; echo "ffmpeg/ffprobe missing"; exit 1;;
esac
set -euo pipefail
VIDEO=""; VOICE=""; MUSIC=""; OUT=""; MDB=-9; LUFS=-16
while [ $# -gt 0 ]; do
  case "$1" in
    --video) VIDEO="$2";; --voice) VOICE="$2";; --music) MUSIC="$2";; --out) OUT="$2";;
    --music-db) MDB="$2";; --lufs) LUFS="$2";; --bitrate|--project|--interchange|--interchange-out) ;; *) ;;
  esac; shift 2
done
DUR="$(cv_dur "$VIDEO")"
IN=(-i "$VIDEO"); FC=""; LABELS=""; n=1
if [ -n "$VOICE" ]; then IN+=(-i "$VOICE"); FC+="[$n:a]aresample=48000,aformat=channel_layouts=stereo[v];"; LABELS+="[v]"; n=$((n+1)); fi
if [ -n "$MUSIC" ]; then IN+=(-i "$MUSIC"); FC+="[$n:a]aresample=48000,aformat=channel_layouts=stereo,volume=${MDB}dB[m];"; LABELS+="[m]"; n=$((n+1)); fi
if [ -z "$LABELS" ]; then   # picture only: nothing to mix
  ffmpeg -hide_banner -loglevel error -y "${IN[@]}" -c copy -movflags +faststart "$OUT"; echo "ffmpeg: no audio given, copied the picture" >&2; exit 0
fi
if [ "$n" -gt 2 ]; then FC+="${LABELS}amix=inputs=$((n-1)):normalize=0:duration=longest[mix];"; else FC+="${LABELS}anull[mix];"; fi
TP=-1.5; LRA=11
# pass 1: measure
M="$(ffmpeg -hide_banner -nostats "${IN[@]}" -filter_complex "${FC}[mix]atrim=0:$DUR,loudnorm=I=$LUFS:TP=$TP:LRA=$LRA:print_format=json[a]" -map "[a]" -f null - 2>&1 | python3 -c '
import json, re, sys
t = sys.stdin.read(); m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", t, re.S)
d = json.loads(m[-1]); print(" ".join(d[k] for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")))')"
read -r MI MTP MLRA MTH MOFF <<< "$M"
# pass 2: apply linearly with the measured values, mux
ffmpeg -hide_banner -loglevel error -y "${IN[@]}" -filter_complex "${FC}[mix]atrim=0:$DUR,loudnorm=I=$LUFS:TP=$TP:LRA=$LRA:measured_I=$MI:measured_TP=$MTP:measured_LRA=$MLRA:measured_thresh=$MTH:offset=$MOFF:linear=true,aresample=48000[a]" \
  -map 0:v:0 -map "[a]" -c:v copy -c:a aac -b:a 320k -ar 48000 -t "$DUR" -movflags +faststart "$OUT"
echo "ffmpeg: mixed ${n:+$((n-1))} audio input(s), measured ${MI} LUFS, normalised to $LUFS -> $OUT" >&2
