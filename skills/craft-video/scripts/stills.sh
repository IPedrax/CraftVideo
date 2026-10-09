#!/usr/bin/env bash
# stills.sh project.ecproj comp "t1 t2 t3 ..." [sheet.png] [cols]
# Renders a frame at each time (seconds) and tiles them into one contact sheet you can look at.
# This is the fast review loop: do it for every scene AND for mid-transition times before the full render.
set -euo pipefail
PROJ="${1:?usage: stills.sh project.ecproj comp \"t1 t2 ...\" [sheet.png] [cols]}"; COMP="${2:?comp name}"; TIMES="${3:?times}"
SHEET="${4:-sheet.png}"; COLS="${5:-3}"
PY="${VIDEO_PY:-${VOICESTUDIO_DIR:-/mnt/ai/VoiceStudio}/.venv/bin/python}"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
for t in $TIMES; do effectcraft-cli render-frame --comp "$COMP" --time "$t" --scale 0.4 --out "$T/still_$t.png" "$PROJ" >/dev/null 2>"$T/err" || { cat "$T/err" >&2; exit 1; }; done
"$PY" - "$T" "$SHEET" "$COLS" $TIMES <<'EOF'
import sys
from PIL import Image, ImageDraw
tmp, sheet, cols, times = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4:]
ims = [Image.open(f"{tmp}/still_{t}.png").convert("RGB") for t in times]
w, h = ims[0].size; rows = (len(ims) + cols - 1) // cols
s = Image.new("RGB", (cols * w, rows * h)); d = ImageDraw.Draw(s)
for i, (t, im) in enumerate(zip(times, ims)):
    x, y = (i % cols) * w, (i // cols) * h
    s.paste(im, (x, y)); d.rectangle([x, y, x + 62, y + 18], fill=(0, 0, 0)); d.text((x + 4, y + 3), f"{t}s", fill=(255, 255, 255))
s.save(sheet); print(f"{sheet}: {len(ims)} stills, {s.size[0]}x{s.size[1]}")
EOF
