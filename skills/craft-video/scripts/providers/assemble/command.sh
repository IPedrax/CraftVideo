#!/usr/bin/env bash
# assemble provider: any editor or mixer, by template. Use it to drive DaVinci Resolve's scripting API, Kdenlive's melt/MLT,
# Shotcut, Blender's VSE, a Premiere/After Effects ExtendScript, or your own script: anything that can take a silent picture,
# a narration wav and a music wav and write a final mp4.
#   ASSEMBLE_CMD  required. Placeholders (shell-quoted): {video} {voice} {music} {out} {music_db} {lufs} {bitrate} {project}
# Examples:
#   melt {video} -audio-track {voice} -audio-track {music} -consumer avformat:{out} vcodec=libx264 acodec=aac
#   python3 resolve_deliver.py --video {video} --voice {voice} --music {music} --music-db {music_db} --out {out}
# The dispatcher then checks the result (video + audio present, same length, loudness near the target) and warns if it is off.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"command","kind":"assemble","summary":"any editor or mixer via the ASSEMBLE_CMD template (Resolve scripting, melt/Kdenlive, Shotcut, Blender VSE, your script)","interchange":"if your command supports it","needs":"ASSEMBLE_CMD"}'; exit 0;;
  --check) [ -n "${ASSEMBLE_CMD:-}" ] || { echo "set ASSEMBLE_CMD (see the header of providers/assemble/command.sh)"; exit 1; }; exit 0;;
esac
VIDEO=""; VOICE=""; MUSIC=""; OUT=""; MDB=-9; LUFS=-16; BR=16000; PROJ=""
while [ $# -gt 0 ]; do
  case "$1" in --video) VIDEO="$2";; --voice) VOICE="$2";; --music) MUSIC="$2";; --out) OUT="$2";; --music-db) MDB="$2";;
    --lufs) LUFS="$2";; --bitrate) BR="$2";; --project) PROJ="$2";; *) ;; esac; shift 2
done
CMD="$(cv_subst "$ASSEMBLE_CMD" "video=$VIDEO" "voice=$VOICE" "music=$MUSIC" "out=$OUT" "music_db=$MDB" "lufs=$LUFS" "bitrate=$BR" "project=$PROJ")"
echo "command: $CMD" >&2
bash -c "$CMD" || { echo "command: ASSEMBLE_CMD exited with an error" >&2; exit 1; }
[ -s "$OUT" ] || { echo "command: ASSEMBLE_CMD wrote nothing to $OUT (does it use {out}?)" >&2; exit 1; }
