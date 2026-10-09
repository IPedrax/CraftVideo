#!/usr/bin/env bash
# edit provider: any editor or script, by template. DaVinci Resolve scripting, Kdenlive/melt, Shotcut, Blender's VSE, Premiere or
# After Effects ExtendScript, your own Python: anything that can read an edit decision list and write the edited mp4.
#   EDIT_CMD  required. Placeholders (shell-quoted): {edl} (the edit.json, see reference/edit.md) {source} (the recording) {out}
#             {ass} (burn-in captions, or empty) {chapters} (ffmetadata file, or empty) {lufs} {width} {height} {fps}
# Examples:
#   python3 resolve_apply.py --edl {edl} --out {out}      (read segments[] from the JSON, build the timeline, render)
#   my_cutter {source} --cuts {edl} -o {out}
# The dispatcher then checks the result (duration = the kept segments, size, fps, audio present) and refuses it if it is off.
# `features` below is what the dispatcher assumes you handle: only "cuts". Add what your command really does by setting EDIT_FEATURES
# (comma list: zoom,audio,music,loudness,color,stabilize,reframe,captions,overlays,chapters) so it does not warn about those.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  python3 -c 'import json,os; print(json.dumps({"name":"command","kind":"edit","summary":"any editor or script via the EDIT_CMD template (Resolve scripting, melt/Kdenlive, Blender VSE, your script)","features":["cuts"]+[f for f in os.environ.get("EDIT_FEATURES","").split(",") if f],"needs":"EDIT_CMD"}))'; exit 0;;
  --check) [ -n "${EDIT_CMD:-}" ] || { echo "set EDIT_CMD (see the header of providers/edit/command.sh)"; exit 1; }; exit 0;;
esac
EDL="${1:?edl}"; OUT="${2:?output}"; shift 2
ASS=""; CH=""; while [ $# -gt 0 ]; do case "$1" in --ass) ASS="$2";; --chapters) CH="$2";; esac; shift 2; done
read -r LUFS W H FPS <<< "$(python3 -c 'import json,sys; e=json.load(open(sys.argv[1])); o=e["output"]; print((e.get("audio") or {}).get("lufs",-16), o.get("width",0), o.get("height",0), o.get("fps",30))' "$EDL")"
SRC="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source"])' "$EDL")"
CMD="$(cv_subst "$EDIT_CMD" "edl=$EDL" "source=$SRC" "out=$OUT" "ass=$ASS" "chapters=$CH" "lufs=$LUFS" "width=$W" "height=$H" "fps=$FPS")"
echo "command: $CMD" >&2
bash -c "$CMD" || { echo "command: EDIT_CMD exited with an error" >&2; exit 1; }
[ -s "$OUT" ] || { echo "command: EDIT_CMD wrote nothing to $OUT (does it use {out}?)" >&2; exit 1; }
