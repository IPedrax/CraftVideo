#!/usr/bin/env bash
# render provider: EffectCraft (After Effects-style scripting, pure Rust, no GPU needed). SCENES is a .jsx file written with
# jsx/ec_lib.jsx. The comp must be called "Main" (begin({name:"Main"}) is the default).
#   effectcraft.sh SCENES OUT.mp4 [--timeline F] [--width W] [--height H] [--fps N] [--duration S] [--brand B.jsx]
#                  [--project OUT.ecproj] [--stills "t1 t2 ..." --sheet sheet.png]
# Width, height, fps and duration reach the scenes as defaults through begin() (via build.sh), so begin({}) follows the spec.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"effectcraft","kind":"render","summary":"EffectCraft scripted compositions (AE-style JS), CPU render, 306 effects, expressions, 3D","scenes":".jsx","stills":true,"alpha":"via effectcraft-cli render --format prores/webm","needs":"effectcraft-cli"}'; exit 0;;
  --check) command -v effectcraft-cli >/dev/null && exit 0; echo "effectcraft-cli not on PATH (storytold/effectcraft release tarball)"; exit 1;;
esac
SCENES="${1:?scenes .jsx}"; OUT="${2:?output mp4}"; shift 2
W=1920; H=1080; FPS=30; DUR=30; BRAND=""; PROJ=""; STILLS=""; SHEET="sheet.png"
while [ $# -gt 0 ]; do
  case "$1" in
    --width) W="$2";; --height) H="$2";; --fps) FPS="$2";; --duration) DUR="$2";; --brand) BRAND="$2";;
    --project) PROJ="$2";; --stills) STILLS="$2";; --sheet) SHEET="$2";; --timeline) ;; *) ;;
  esac; shift 2
done
[ -n "$PROJ" ] || PROJ="${OUT%.*}.ecproj"
export CV_W="$W" CV_H="$H" CV_FPS="$FPS" CV_DUR="$DUR"
BARGS=(); [ -z "$BRAND" ] || BARGS=(--brand "$BRAND")
bash "$HERE/build.sh" "${BARGS[@]}" "$SCENES" "$PROJ" >&2
if [ -n "$STILLS" ]; then
  bash "$HERE/stills.sh" "$PROJ" Main "$STILLS" "$SHEET" 3 >&2
else
  effectcraft-cli render --comp Main --out "$OUT" --format h264 --bitrate 30000 --audio off "$PROJ" >&2
fi
