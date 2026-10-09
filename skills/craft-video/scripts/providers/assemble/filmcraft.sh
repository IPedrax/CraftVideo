#!/usr/bin/env bash
# assemble provider: FilmCraft (V1 picture, A1 narration, A2 music at --music-db, H.264 + AAC normalised to --lufs).
#   filmcraft.sh --video V [--voice N] [--music M] --out OUT [--music-db -9] [--lufs -16] [--bitrate 16000] [--project P]
#                [--interchange edl|xml|fcpxml|otio|aaf|omf --interchange-out FILE]
# --interchange also writes the edited timeline for ANOTHER editor (DaVinci Resolve, Premiere, Final Cut, Kdenlive, Avid...):
# media is referenced by absolute path, so import the file where those paths still exist (or relink).
# The headless FilmCraft engine starts EMPTY and every `run` is a fresh session, so this does three runs: import (learn item ids),
# build the sequence (learn clip ids), then the full job with gain + interchange + export.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"filmcraft","kind":"assemble","summary":"FilmCraft headless NLE: tracks, clip gain, loudness-normalised H.264/AAC export, editor interchange","interchange":"edl,xml,fcpxml,otio,aaf,omf","needs":"filmcraft-cli"}'; exit 0;;
  --check) command -v filmcraft-cli >/dev/null && exit 0; echo "filmcraft-cli not on PATH (storytold/filmcraft release tarball)"; exit 1;;
esac
set -euo pipefail
VIDEO=""; VOICE=""; MUSIC=""; OUT=""; MDB=-9; LUFS=-16; BR=16000; PROJ=""; IFMT=""; IOUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --video) VIDEO="$(realpath "$2")";; --voice) VOICE="$(realpath "$2")";; --music) MUSIC="$(realpath "$2")";;
    --out) OUT="$(realpath -m "$2")";; --music-db) MDB="$2";; --lufs) LUFS="$2";; --bitrate) BR="$2";;
    --project) PROJ="$(realpath -m "$2")";; --interchange) IFMT="$2";; --interchange-out) IOUT="$(realpath -m "$2")";; *) ;;
  esac; shift 2
done
[ -n "$PROJ" ] || PROJ="${OUT%.*}.fcproj"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
PATHS=("$VIDEO"); [ -z "$VOICE" ] || PATHS+=("$VOICE"); [ -z "$MUSIC" ] || PATHS+=("$MUSIC")
JP=$(python3 -c 'import json,sys; print(json.dumps({"paths": sys.argv[1:]}))' "${PATHS[@]}")
imp() { echo "{\"id\":\"file.import\",\"params\":$JP}"; }

imp > "$T/0.jsonl"
read -r -a ITEM <<< "$(filmcraft-cli run "$T/0.jsonl" | python3 -c 'import json,sys; print(" ".join(map(str, json.loads(sys.stdin.read().splitlines()[0])["result"]["items"])))')"
VI=${ITEM[0]}; n=1
if [ -n "$VOICE" ]; then VOI=${ITEM[$n]}; n=$((n+1)); fi
if [ -n "$MUSIC" ]; then MUI=${ITEM[$n]}; fi
place() { echo "{\"id\":\"timeline.place\",\"params\":{\"item\":$1,\"track\":\"$2\",\"seconds\":0}}"; }
build() {
  imp; echo "{\"id\":\"file.newSequence\",\"params\":{\"name\":\"$(basename "${OUT%.*}")\",\"fromItem\":$VI}}"
  [ -z "$VOICE" ] || place "$VOI" A1
  [ -z "$MUSIC" ] || place "$MUI" A2
}
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
  if [ -n "$IFMT" ]; then echo "{\"id\":\"file.exportInterchange\",\"params\":{\"format\":\"$IFMT\",\"path\":\"$IOUT\"}}"; fi
  echo "{\"id\":\"file.exportMedia\",\"params\":{\"path\":\"$OUT\",\"format\":\"h264\",\"bitrateKbps\":$BR,\"bitrateMode\":\"vbr1Pass\",\"loudnessLufs\":$LUFS,\"wait\":true}}"
} > "$T/2.jsonl"
filmcraft-cli run "$T/2.jsonl" | tee "$T/out.log" | tail -1 | cut -c1-200 >&2
if grep -q '"ok":false' "$T/out.log"; then grep '"ok":false' "$T/out.log" >&2; echo "a FilmCraft command failed, see above" >&2; exit 1; fi
echo "filmcraft: exported $OUT (project $PROJ${IFMT:+, $IFMT timeline $IOUT})" >&2
