#!/usr/bin/env bash
# finish.sh final.mp4 outdir --title "A Proper Title" [--filename name] [--poster-time 1.6] [--voice narration.wav]
# brag's delivery step: pull the strongest SETTLED frame to <name>.jpg and bake it in as frame 0 of <name>.mp4
# (replace frame 0, never add a frame, so duration and audio sync stay identical), then run the QA gates.
# --title is required: it is the title written into the video's metadata (players and uploads show it) and, slugified, the file name
# (ai-is-taking-games-apart.mp4). --filename overrides the file name only (no extension). Accents are folded to plain letters.
set -euo pipefail
IN="$(realpath "${1:?usage: finish.sh final.mp4 outdir --title \"A Proper Title\" [--filename name] [--poster-time 1.6] [--voice narration.wav]}")"; OUTDIR="$(realpath -m "${2:?outdir}")"; shift 2
PT=1.6; VOICE=""; TITLE=""; FNAME=""
while [ $# -gt 0 ]; do
  [ $# -ge 2 ] || { echo "option $1 needs a value" >&2; exit 2; }
  case "$1" in --poster-time) PT="$2";; --voice) VOICE="$(realpath "$2")";; --title) TITLE="$2";; --filename) FNAME="$2";; *) echo "unknown option $1" >&2; exit 2;; esac; shift 2
done
[ -n "$TITLE" ] || { echo "finish.sh: --title is required: the finished video is named after it (never 'brag.mp4'). Example: --title \"AI Is Taking Games Apart\"" >&2; exit 2; }
BASE="$(python3 - "${FNAME:-$TITLE}" <<'PY'
import re, sys, unicodedata
t = unicodedata.normalize("NFKD", sys.argv[1]).encode("ascii", "ignore").decode()      # accents fold to plain letters
print(re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:80].strip("-"))
PY
)"
[ -n "$BASE" ] || { echo "finish.sh: the title gives an empty file name; pass --filename" >&2; exit 2; }
VID="$OUTDIR/$BASE.mp4"; POSTER="$OUTDIR/$BASE.jpg"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; PY="${VIDEO_PY:-${VOICESTUDIO_DIR:-/mnt/ai/VoiceStudio}/.venv/bin/python}"
mkdir -p "$OUTDIR"
FPS=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$IN")
ffmpeg -hide_banner -loglevel error -y -ss "$PT" -i "$IN" -frames:v 1 -q:v 2 "$POSTER"
ffmpeg -hide_banner -loglevel error -y -i "$IN" -i "$POSTER" \
  -filter_complex "[1:v]scale=iw:ih,format=yuv420p[p];[0:v]format=yuv420p[v];[v][p]overlay=0:0:enable='eq(n,0)'[o]" \
  -map "[o]" -map 0:a -c:v libx264 -preset slow -crf 13 -pix_fmt yuv420p -r "$FPS" -c:a copy -metadata title="$TITLE" -movflags +faststart "$VID"

echo "== QA: $VID =="; bad=0
GOT=$(ffprobe -v error -show_entries format_tags=title -of csv=p=0 "$VID")
[ "$GOT" = "$TITLE" ] && echo "  PASS title embedded: $GOT" || { echo "  FAIL title not in the file's metadata (got '$GOT')"; bad=1; }
IFS=, read -r W H < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$VID")
FR=$(ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames -of csv=p=0 "$VID")
DUR=$(ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 "$VID")
echo "video: ${W}x${H} @ $FPS, $FR frames, ${DUR}s"
LOUD=$(ffmpeg -hide_banner -nostats -i "$VID" -vn -af ebur128=peak=true -f null - 2>&1 | grep -E '^\s+(I:|Peak:)' | tail -2 | tr -s ' ' | tr '\n' ' ')
echo "loudness: $LOUD"
LUFS=$(echo "$LOUD" | sed -E 's/.*I: (-?[0-9.]+) LUFS.*/\1/'); PEAK=$(echo "$LOUD" | sed -E 's/.*Peak: (-?[0-9.]+) dBFS.*/\1/')
awk -v l="$LUFS" 'BEGIN{exit !(l>=-17 && l<=-15)}' && echo "  PASS loudness within -16 +/- 1 LUFS" || { echo "  FAIL loudness $LUFS LUFS"; bad=1; }
awk -v p="$PEAK" 'BEGIN{exit !(p<=-1.0)}' && echo "  PASS peak <= -1 dBFS" || { echo "  FAIL peak $PEAK dBFS (clipping risk)"; bad=1; }
if [ -n "$VOICE" ]; then "$PY" "$HERE/qa_sync.py" "$VID" "$VOICE" && echo "  PASS sync" || { echo "  FAIL sync"; bad=1; }; fi
"$PY" - "$POSTER" "$VID" <<'EOF'
import subprocess, sys, numpy as np
from PIL import Image
p = np.asarray(Image.open(sys.argv[1]).convert("RGB")).astype(float)
raw = subprocess.run(["ffmpeg","-v","error","-i",sys.argv[2],"-vf","select=eq(n\\,0)","-frames:v","1","-f","image2pipe","-vcodec","png","-"],capture_output=True).stdout
import io; f0 = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB")).astype(float)
d = abs(p - f0).mean(); print(f"  {'PASS' if d < 3 else 'FAIL'} poster is frame 0 (mean diff {d:.2f})")
sys.exit(0 if d < 3 else 1)
EOF
[ $? -eq 0 ] || bad=1
[ $bad -eq 0 ] && echo "QA passed" || { echo "QA FAILED"; exit 1; }
