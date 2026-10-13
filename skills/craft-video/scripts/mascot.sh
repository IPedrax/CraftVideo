#!/usr/bin/env bash
# mascot.sh: render the mascot (Clawd, the Claude Code mascot) as a transparent overlay, and optionally lay it over a video.
#   mascot.sh mascot.json out.mov [--timeline work/timeline.json] [--width 1920] [--height 1080] [--fps 30] [--duration S]     (with --over, size and fps follow the picture)
#             [--workers N|auto] [--gpu off|auto|vulkan|egl]
#             [--sheet sheet.png]              review stills of the cues over a dark ground INSTEAD of rendering the clip (seconds; do this first)
#             [--over picture.mp4 --into out.mp4]   also lay the clip over a video (its sound is kept), for a made video; for an edit use the overlay entry below
# Output: out.mov (ProRes 4444, the size and fps you gave, covering only the span the mascot is on screen) and out.overlay.json, the `overlays` entry for
# an edit.json ({"type":"clip", "start": ...}). Needs the kit: scripts/get_mascot.sh. mascot.json and its craft: reference/mascot.md.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
CUES="${1:?usage: mascot.sh mascot.json out.mov [--timeline T] [--width W --height H --fps F --duration S] [--sheet sheet.png] [--over video.mp4 --into out.mp4]}"; OUT="${2:?output .mov}"; shift 2
W=""; H=""; FPS=""; DUR=""; TL=""; SHEET=""; OVER=""; INTO=""; EXTRA=()
while [ $# -gt 0 ]; do
  [ $# -ge 2 ] || cv_die "option $1 needs a value"
  case "$1" in
    --width) W="$2";; --height) H="$2";; --fps) FPS="$2";; --duration) DUR="$2";; --timeline) TL="$2";;
    --sheet) SHEET="$2";; --over) OVER="$2";; --into) INTO="$2";;
    --workers|--gpu) EXTRA+=("$1" "$2");;
    *) cv_die "unknown option $1";;
  esac; shift 2
done
[ -f "$CUES" ] || cv_die "cue file not found: $CUES"
MASCOT="${MASCOT_DIR:-$HOME/.local/share/craftvideo/mascot}"
[ -f "$MASCOT/clawd/clawd.js" ] || cv_die "the mascot kit is not installed. Run scripts/get_mascot.sh (CRAFTVIDEO_ALLOW_DOWNLOAD=1 downloads it; Clawd is the Claude Code mascot, MIT drawing code by John Heibel)."
case "$OUT" in *.mov) ;; *) cv_die "the overlay is ProRes 4444, so the output must be a .mov (got $OUT)";; esac
[ -z "$OVER$INTO" ] || { [ -n "$OVER" ] && [ -n "$INTO" ] || cv_die "--over and --into go together"; }
if [ -n "$OVER" ]; then      # the overlay must match the picture exactly: its size and fps are the picture's unless you give them, and then they must agree
  [ -f "$OVER" ] || cv_die "video not found: $OVER"; DUR="${DUR:-$(cv_dur "$OVER")}"
  IFS=, read -r PW PH PF < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$OVER")
  PF="$(python3 -c 'from fractions import Fraction; import sys; print(float(Fraction(sys.argv[1])))' "$PF")"
  W="${W:-$PW}"; H="${H:-$PH}"; FPS="${FPS:-$PF}"
  [ "$W" = "$PW" ] && [ "$H" = "$PH" ] || cv_die "the overlay would be ${W}x${H} but the picture is ${PW}x${PH}: leave --width and --height out and they follow the picture"
  python3 -c 'import sys; sys.exit(0 if abs(float(sys.argv[1]) - float(sys.argv[2])) < 0.01 else 1)' "$FPS" "$PF" || cv_die "the overlay would be $FPS fps but the picture is $PF: leave --fps out and it follows the picture"
elif [ -z "$DUR" ] && [ -n "$TL" ] && [ -f "$TL" ]; then DUR="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["total"])' "$TL")"; fi
W="${W:-1920}"; H="${H:-1080}"; FPS="${FPS:-30}"

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
INFO="$(python3 -I "$CV_HERE/mascot.py" "$CUES" --out "$T/spec.json" ${SHEET:+--sheet} ${TL:+--timeline "$TL"} ${DUR:+--duration "$DUR"})"   # checks it all; prints start, end, stills
START="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["start"])' "$INFO")"
END="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["end"])' "$INFO")"
PAGE="$CV_SKILL/mascot/clawd.html"

if [ -n "$SHEET" ]; then       # the page draws the review sheet itself (one frame): the character at each cue, once its take has settled
  bash "$CV_HERE/render.sh" "$PAGE" "$T/unused.mov" --provider html --alpha 1 --timeline "$T/spec.json" --width "$W" --height "$H" --fps "$FPS" --duration 1 \
    --stills 0 --sheet "$SHEET" "${EXTRA[@]}" >&2
  echo "$SHEET: the character at video times $(python3 -c 'import json,sys; print(" ".join(f"{t:.2f}" for t in json.loads(sys.argv[1])["stills"]))' "$INFO")" >&2
  exit 0
fi

CLIP="$(python3 -c "print(round($END-$START, 3))")"
# p5.brush on the software renderer disagrees with itself by a level in a pixel or two on frames with the glowing bulb (about 100 dB apart), which a byte-exact preflight
# would call history: --preflight-psnr 60 forgives that and still stops anything that really depends on history (a moved object is 20 to 40 dB)
bash "$CV_HERE/render.sh" "$PAGE" "$OUT" --provider html --alpha 1 --timeline "$T/spec.json" --width "$W" --height "$H" --fps "$FPS" --duration "$CLIP" --preflight-psnr 60 "${EXTRA[@]}"
ABS="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
python3 - "$ABS" "$START" "${OUT%.mov}.overlay.json" <<'PY'
import json, sys
json.dump({"overlays": [{"type": "clip", "file": sys.argv[1], "start": float(sys.argv[2]), "x": 0, "y": 0}]}, open(sys.argv[3], "w"), indent=1)
PY
echo "overlay entry for an edit.json: ${OUT%.mov}.overlay.json (starts at ${START} s, lasts ${CLIP} s)" >&2

if [ -n "$OVER" ]; then        # the same graph the edit step uses for overlay clips; the picture is encoded once more at the house quality, the sound is copied
  ffmpeg -hide_banner -loglevel error -y -i "$OVER" -i "$OUT" \
    -filter_complex "[1:v]format=yuva444p,setpts=PTS-STARTPTS+${START}/TB[m];[0:v][m]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[v]" \
    -map "[v]" -map "0:a?" -c:v libx264 -preset slow -crf 14 -c:a copy -movflags +faststart "$INTO"
  echo "ok: $INTO ($(cv_dur "$INTO") s), the mascot on screen from ${START} s to ${END} s" >&2
fi
