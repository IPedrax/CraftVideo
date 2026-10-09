#!/usr/bin/env bash
# render.sh: the picture dispatcher. Turns a scenes file into a SILENT H.264 mp4 that matches the spec exactly.
#   render.sh scenes out.mp4 [--provider NAME] [--timeline timeline.json] [--width 1920] [--height 1080] [--fps 30] [--duration S]
#             [--brand brand.jsx] [--project out.proj] [--stills "t1 t2 ..." --sheet sheet.png]
# What "scenes" is depends on the provider: .jsx (effectcraft), .html (html), anything (command). --duration defaults to
# "total" in the timeline, else 30. With --stills it renders review frames into one contact sheet instead of a video.
# Provider order: --provider, env CRAFTVIDEO_RENDER, ./craftvideo.json, ~/.config/craftvideo/config.json, then effectcraft, html.
# The contract is checked here for EVERY provider: exact width, height, fps and frame count; any audio is stripped.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
SCENES="${1:?usage: render.sh scenes out.mp4 [--provider NAME] [options]}"; OUT="${2:?output mp4}"; shift 2
PROV=""; W=1920; H=1080; FPS=30; DUR=""; TL=""; STILLS=""; EXTRA=()
while [ $# -gt 0 ]; do
  [ $# -ge 2 ] || cv_die "option $1 needs a value"
  case "$1" in
    --provider) PROV="$2";; --width) W="$2";; --height) H="$2";; --fps) FPS="$2";; --duration) DUR="$2";; --timeline) TL="$2";;
    --stills) STILLS="$2";;
    *) EXTRA+=("$1" "$2");;
  esac; shift 2
done
[ -e "$SCENES" ] || cv_die "scenes file not found: $SCENES"
if [ -z "$DUR" ]; then
  if [ -n "$TL" ] && [ -f "$TL" ]; then DUR="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["total"])' "$TL")"; else DUR=30; fi
fi
NAME="$(cv_resolve render "$PROV")"
ARGS=(--width "$W" --height "$H" --fps "$FPS" --duration "$DUR"); [ -z "$TL" ] || ARGS+=(--timeline "$TL")
echo "rendering ${W}x${H} @ ${FPS} fps, ${DUR}s with provider '$NAME'" >&2

if [ -n "$STILLS" ]; then
  [ "$(cv_info render "$NAME" stills)" != "False" ] && [ "$(cv_info render "$NAME" stills)" != "false" ] || cv_die "provider '$NAME' cannot render stills; render the video and extract frames with ffmpeg"
  bash "$(cv_provider_script render "$NAME")" "$SCENES" "$OUT" "${ARGS[@]}" "${EXTRA[@]}" --stills "$STILLS"
  exit 0
fi

bash "$(cv_provider_script render "$NAME")" "$SCENES" "$OUT" "${ARGS[@]}" "${EXTRA[@]}"
[ -s "$OUT" ] || cv_die "provider '$NAME' produced no video at $OUT"

# ---- enforce the picture contract ----
IFS=, read -r VW VH RF < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$OUT")
NB="$(ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames -of csv=p=0 "$OUT")"
VFPS="$(python3 -c 'from fractions import Fraction; import sys; print(float(Fraction(sys.argv[1])))' "$RF")"
EXPN="$(python3 -c 'import sys; print(round(float(sys.argv[1]) * float(sys.argv[2])))' "$FPS" "$DUR")"
AUD="$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$OUT" | wc -l | tr -d ' ')"
bad=""
[ "$VW" = "$W" ] && [ "$VH" = "$H" ] || bad="$bad size ${VW}x${VH} (wanted ${W}x${H});"
python3 -c 'import sys; sys.exit(0 if abs(float(sys.argv[1]) - float(sys.argv[2])) < 0.01 else 1)' "$VFPS" "$FPS" || bad="$bad fps $VFPS (wanted $FPS);"
[ "$NB" = "$EXPN" ] || bad="$bad frames $NB (wanted $EXPN);"
[ -z "$bad" ] || cv_die "provider '$NAME' broke the picture contract:$bad fix the scenes or the provider's size/rate/length handling"
if [ "$AUD" != "0" ]; then
  cv_warn "provider '$NAME' wrote an audio track; stripping it (the contract is a silent picture)"
  ffmpeg -hide_banner -loglevel error -y -i "$OUT" -an -c:v copy "$OUT.noaudio.mp4" && mv "$OUT.noaudio.mp4" "$OUT"
fi
echo "ok: $OUT, ${VW}x${VH} @ ${FPS} fps, $NB frames (provider $NAME)"
