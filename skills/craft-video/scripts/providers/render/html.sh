#!/usr/bin/env bash
# render provider: HTML/CSS/JS scenes drawn by headless Chromium (Playwright) and encoded by ffmpeg. This is brag's own route, so
# anything the web can draw works: React, Tailwind, SVG, canvas, WebGL, CSS animation (driven by seek(t), not by wall-clock time).
# SCENES is an .html file that defines window.craftvideo.seek(t); see reference/html-scenes.md and examples/html-hello/.
#   html.sh SCENES OUT.mp4 --width W --height H --fps N --duration S [--timeline F] [--stills "t1 t2" --sheet F]
#           [--gpu off|auto|vulkan|egl] [--alpha 1 (OUT.mov, transparent, ProRes 4444)] [--root DIR]
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
MJS="$CV_HERE/providers/render/html-render.mjs"
case "${1:-}" in
  --info)  echo '{"name":"html","kind":"render","summary":"HTML/CSS/JS scenes via headless Chromium + ffmpeg (anything the web can draw)","scenes":".html with window.craftvideo.seek(t)","stills":true,"alpha":true,"gpu":"off|auto|vulkan|egl","needs":"node, playwright, chromium"}'; exit 0;;
  --check) command -v node >/dev/null || { echo "node missing"; exit 1; }; command -v ffmpeg >/dev/null || { echo "ffmpeg missing"; exit 1; }
           node "$MJS" --check; exit $?;;
esac
SCENES="${1:?scenes .html}"; OUT="${2:?output mp4}"; shift 2
exec node "$MJS" "$SCENES" "$OUT" "$@"
