#!/usr/bin/env bash
# assemble.sh: FilmCraft mix + export.
#   assemble.sh --video silent.mp4 [--voice narration.wav] [--music music.wav] --out final.mp4
#               [--music-db -9] [--lufs -16] [--bitrate 16000] [--project edit.fcproj]
# V1 = picture, A1 = narration, A2 = music (clip gain --music-db), exported H.264 + AAC normalised to --lufs.
# The headless FilmCraft engine starts EMPTY and every `run` is a fresh session, so this does three runs:
# import (learn item ids), build the sequence (learn clip ids), then the full job with gain + export.
set -euo pipefail
VIDEO=""; VOICE=""; MUSIC=""; OUT=""; MDB=-9; LUFS=-16; BR=16000; PROJ=""
while [ $# -gt 0 ]; do
  case "$1" in
    --video) VIDEO="$(realpath "$2")"; shift 2;; --voice) VOICE="$(realpath "$2")"; shift 2;;
    --music) MUSIC="$(realpath "$2")"; shift 2;; --out) OUT="$(realpath -m "$2")"; shift 2;;
    --music-db) MDB="$2"; shift 2;; --lufs) LUFS="$2"; shift 2;; --bitrate) BR="$2"; shift 2;;
    --project) PROJ="$(realpath -m "$2")"; shift 2;; *) echo "unknown option $1" >&2; exit 2;;
  esac
done
[ -n "$VIDEO" ] && [ -n "$OUT" ] || { echo "usage: assemble.sh --video v.mp4 [--voice n.wav] [--music m.wav] --out final.mp4" >&2; exit 2; }
[ -n "$PROJ" ] || PROJ="${OUT%.*}.fcproj"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
PATHS=("$VIDEO"); [ -n "$VOICE" ] && PATHS+=("$VOICE"); [ -n "$MUSIC" ] && PATHS+=("$MUSIC")
JP=$(python3 -c 'import json,sys; print(json.dumps({"paths": sys.argv[1:]}))' "${PATHS[@]}")
imp() { echo "{\"id\":\"file.import\",\"params\":$JP}"; }
ids() { python3 -c 'import json,sys; print(" ".join(map(str, json.loads(sys.stdin.read().splitlines()[0])["result"]["items"])))' ; }

# run 0: item ids
imp > "$T/0.jsonl"; read -r -a ITEM <<< "$(filmcraft-cli run "$T/0.jsonl" | ids)"
VI=${ITEM[0]}; n=1
[ -n "$VOICE" ] && { VOI=${ITEM[$n]}; n=$((n+1)); }; [ -n "$MUSIC" ] && MUI=${ITEM[$n]}

place() {  # item track
  echo "{\"id\":\"timeline.place\",\"params\":{\"item\":$1,\"track\":\"$2\",\"seconds\":0}}"
}
build() {
  imp; echo "{\"id\":\"file.newSequence\",\"params\":{\"name\":\"$(basename "${OUT%.*}")\",\"fromItem\":$VI}}"
  [ -n "$VOICE" ] && place "$VOI" A1
  [ -n "$MUSIC" ] && place "$MUI" A2
}
# run 1: clip ids of the placed audio (picture comes with newSequence fromItem)
build > "$T/1.jsonl"
CLIPS=$(filmcraft-cli run "$T/1.jsonl" | python3 -c '
import json, sys
rows = [json.loads(l) for l in sys.stdin.read().splitlines() if l.startswith("{")]
print(" ".join(str(c) for r in rows if r["id"] == "timeline.place" for c in r["result"]["clips"]))')
read -r -a CLIP <<< "$CLIPS"
{
  build
  if [ -n "$MUSIC" ]; then
    MC=${CLIP[$(( ${#CLIP[@]} - 1 ))]}                          # music is placed last
    echo "{\"id\":\"clip.audioGain\",\"params\":{\"clips\":[$MC],\"mode\":\"set\",\"db\":$MDB}}"
  fi
  echo "{\"id\":\"file.save\",\"params\":{\"path\":\"$PROJ\"}}"
  echo "{\"id\":\"file.exportMedia\",\"params\":{\"path\":\"$OUT\",\"format\":\"h264\",\"bitrateKbps\":$BR,\"bitrateMode\":\"vbr1Pass\",\"loudnessLufs\":$LUFS,\"wait\":true}}"
} > "$T/2.jsonl"
filmcraft-cli run "$T/2.jsonl" | tee "$T/out.log" | tail -1 | cut -c1-240
grep -q '"ok":false' "$T/out.log" && { echo "a FilmCraft command failed, see above" >&2; grep '"ok":false' "$T/out.log" >&2; exit 1; }
echo "exported $OUT (project $PROJ)"
