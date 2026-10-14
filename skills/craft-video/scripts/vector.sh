#!/usr/bin/env bash
# vector.sh: play an animated vector asset as video, deterministically, on any background or on none.
#   vector.sh asset.svg out.mp4 [--width 1920] [--height 1080] [--fps 30] [--duration 5] [--fit contain|cover] [--period S] [--speed 1]
#             [--alpha 1]              a transparent overlay: out must be .mov (ProRes 4444), ready for an edit.json `overlays` clip entry or edit's overlay graph
#             [--look NAME] [--workers N|auto] [--stills "0 1 2" --sheet sheet.png]    a look gives the ground colour (--cv-ground); stills review without rendering a clip
# The asset is an animated SVG (SMIL, CSS animations, Web Animations): it is inlined in vector/player.html, which moves SMIL with setCurrentTime() and sets every CSS and Web
# Animation to the frame's time, so the same time always gives the same picture and a render can use parallel workers. --period loops the asset every S seconds,
# --speed plays it faster or slower. Anything that keeps its own clock inside the asset (a script, a requestAnimationFrame loop) is not deterministic: the renderer's
# preflight refuses it (exit 4). Licences of the asset are yours to check: nothing here fetches or ships animation files.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
ASSET="${1:?usage: vector.sh asset.svg out.mp4|out.mov [--width W --height H --fps F --duration S] [--fit contain|cover] [--period S] [--speed X] [--alpha 1]}"; OUT="${2:?output}"; shift 2
W=1920; H=1080; FPS=30; DUR=5; FIT=contain; PERIOD=""; SPEED=1; EXTRA=()
while [ $# -gt 0 ]; do
  [ $# -ge 2 ] || cv_die "option $1 needs a value"
  case "$1" in
    --width) W="$2";; --height) H="$2";; --fps) FPS="$2";; --duration) DUR="$2";; --fit) FIT="$2";; --period) PERIOD="$2";; --speed) SPEED="$2";;
    --alpha|--look|--workers|--gpu|--stills|--sheet|--lint) EXTRA+=("$1" "$2");;
    *) cv_die "unknown option $1";;
  esac; shift 2
done
[ -f "$ASSET" ] || cv_die "asset not found: $ASSET"
case "$ASSET" in *.svg) ;; *) cv_die "only animated SVG is played here (got $ASSET)";; esac
case " ${EXTRA[*]:-} " in *" --alpha "*) case "$OUT" in *.mov) ;; *) cv_die "an overlay is ProRes 4444, so the output must be a .mov (got $OUT)";; esac;; esac
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
cp "$ASSET" "$T/asset.svg"; cp "$CV_SKILL/vector/player.html" "$T/player.html"
python3 - "$T/spec.json" "$FIT" "${PERIOD:-0}" "$SPEED" <<'PY'
import json, sys
p = float(sys.argv[3]); json.dump({"vector": {"asset": "asset.svg", "fit": sys.argv[2], "period": p or None, "speed": float(sys.argv[4])}, "sentences": [], "total": 0}, open(sys.argv[1], "w"))
PY
# SMIL is byte-exact from one visit of a time to the next. A CSS or Web Animation on a transform can differ by a sub-pixel between visits (measured: 679 edge pixels of one circle, up to 79 levels, 49 dB
# PSNR), which the renderer's byte-exact preflight would call history. When the asset has one, the preflight accepts a revisit within 40 dB (a moved object is 20 to 40).
PF=(); if grep -qE '@keyframes|animation[-:]|transition[-:]|\.animate\(' "$ASSET"; then PF=(--preflight-psnr 40); echo "vector: the asset has CSS or Web Animations: preflight tolerance 40 dB (sub-pixel raster noise between visits)" >&2; fi
bash "$CV_HERE/render.sh" "$T/player.html" "$OUT" --provider html --timeline "$T/spec.json" --width "$W" --height "$H" --fps "$FPS" --duration "$DUR" "${PF[@]}" "${EXTRA[@]}"
