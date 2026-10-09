#!/usr/bin/env bash
# render provider: any renderer, by template. Use it for Remotion, Manim, Motion Canvas, Blender, a Python or Node script of
# your own: anything that can write a silent H.264 mp4 of the requested size, rate and length.
#   RENDER_CMD  required. Placeholders (shell-quoted): {scenes} {out} {timeline} {width} {height} {fps} {duration} {brand} {project}
# Examples:
#   npx remotion render src/index.ts Main {out} --width={width} --height={height} --fps={fps}
#   manim -qh --fps {fps} -o {out} {scenes} Main
#   python3 my_renderer.py --scenes {scenes} --timeline {timeline} --out {out} --size {width}x{height} --fps {fps} --seconds {duration}
# The dispatcher checks the result against the spec, strips any audio, and fails loudly on a mismatch.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"command","kind":"render","summary":"any renderer via the RENDER_CMD template (Remotion, Manim, Motion Canvas, Blender, your script)","scenes":"whatever your command takes","stills":false,"alpha":"if your command supports it","needs":"RENDER_CMD"}'; exit 0;;
  --check) [ -n "${RENDER_CMD:-}" ] || { echo "set RENDER_CMD (see the header of providers/render/command.sh)"; exit 1; }; exit 0;;
esac
SCENES="${1:?scenes}"; OUT="${2:?output mp4}"; shift 2
W=1920; H=1080; FPS=30; DUR=30; TL=""; BRAND=""; PROJ=""
while [ $# -gt 0 ]; do
  case "$1" in --width) W="$2";; --height) H="$2";; --fps) FPS="$2";; --duration) DUR="$2";; --timeline) TL="$2";; --brand) BRAND="$2";; --project) PROJ="$2";; *) ;; esac; shift 2
done
CMD="$(cv_subst "$RENDER_CMD" "scenes=$SCENES" "out=$OUT" "timeline=$TL" "width=$W" "height=$H" "fps=$FPS" "duration=$DUR" "brand=$BRAND" "project=$PROJ")"
echo "command: $CMD" >&2
bash -c "$CMD" || { echo "command: RENDER_CMD exited with an error" >&2; exit 1; }
[ -s "$OUT" ] || { echo "command: RENDER_CMD wrote nothing to $OUT (does it use {out}?)" >&2; exit 1; }
