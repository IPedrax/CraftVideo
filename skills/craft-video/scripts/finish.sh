#!/usr/bin/env bash
# finish.sh final.mp4 outdir [--poster-time 1.6] [--voice narration.wav]
# brag's delivery step: pull the strongest SETTLED frame to brag.jpg and bake it in as frame 0 of brag.mp4
# (replace frame 0, never add a frame, so duration and audio sync stay identical), then run the QA gates.
set -euo pipefail
IN="$(realpath "${1:?usage: finish.sh final.mp4 outdir [--poster-time 1.6] [--voice narration.wav]}")"; OUTDIR="$(realpath -m "${2:?outdir}")"; shift 2
PT=1.6; VOICE=""
while [ $# -gt 0 ]; do case "$1" in --poster-time) PT="$2"; shift 2;; --voice) VOICE="$(realpath "$2")"; shift 2;; *) echo "unknown option $1" >&2; exit 2;; esac; done
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; PY="${VIDEO_PY:-/mnt/ai/VoiceStudio/.venv/bin/python}"
mkdir -p "$OUTDIR"
FPS=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$IN")
ffmpeg -hide_banner -loglevel error -y -ss "$PT" -i "$IN" -frames:v 1 -q:v 2 "$OUTDIR/brag.jpg"
ffmpeg -hide_banner -loglevel error -y -i "$IN" -i "$OUTDIR/brag.jpg" \
  -filter_complex "[1:v]scale=iw:ih,format=yuv420p[p];[0:v]format=yuv420p[v];[v][p]overlay=0:0:enable='eq(n,0)'[o]" \
  -map "[o]" -map 0:a -c:v libx264 -preset slow -crf 13 -pix_fmt yuv420p -r "$FPS" -c:a copy -movflags +faststart "$OUTDIR/brag.mp4"

echo "== QA: $OUTDIR/brag.mp4 =="; bad=0
IFS=, read -r W H < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$OUTDIR/brag.mp4")
FR=$(ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames -of csv=p=0 "$OUTDIR/brag.mp4")
DUR=$(ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 "$OUTDIR/brag.mp4")
echo "video: ${W}x${H} @ $FPS, $FR frames, ${DUR}s"
LOUD=$(ffmpeg -hide_banner -nostats -i "$OUTDIR/brag.mp4" -vn -af ebur128=peak=true -f null - 2>&1 | grep -E '^\s+(I:|Peak:)' | tail -2 | tr -s ' ' | tr '\n' ' ')
echo "loudness: $LOUD"
LUFS=$(echo "$LOUD" | sed -E 's/.*I: (-?[0-9.]+) LUFS.*/\1/'); PEAK=$(echo "$LOUD" | sed -E 's/.*Peak: (-?[0-9.]+) dBFS.*/\1/')
awk -v l="$LUFS" 'BEGIN{exit !(l>=-17 && l<=-15)}' && echo "  PASS loudness within -16 +/- 1 LUFS" || { echo "  FAIL loudness $LUFS LUFS"; bad=1; }
awk -v p="$PEAK" 'BEGIN{exit !(p<=-1.0)}' && echo "  PASS peak <= -1 dBFS" || { echo "  FAIL peak $PEAK dBFS (clipping risk)"; bad=1; }
if [ -n "$VOICE" ]; then "$PY" "$HERE/qa_sync.py" "$OUTDIR/brag.mp4" "$VOICE" && echo "  PASS sync" || { echo "  FAIL sync"; bad=1; }; fi
"$PY" - "$OUTDIR/brag.jpg" "$OUTDIR/brag.mp4" <<'EOF'
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
