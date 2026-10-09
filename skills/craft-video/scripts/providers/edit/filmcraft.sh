#!/usr/bin/env bash
# edit provider: FilmCraft's headless NLE. Cuts the segments onto V1/A1 of an explicit-settings sequence and exports H.264 + AAC
# normalised to the EDL's LUFS. It does the cuts and the loudness; zoom, the audio chain, colour, captions, titles and music are
# NOT applied (edit.sh warns about each). Also leaves the project next to the output (OUT.fcproj) so a person can finish it in the editor.
#   filmcraft.sh EDL.json OUT.mp4 [--ass F] [--chapters F]   (the last two are ignored)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"filmcraft","kind":"edit","summary":"FilmCraft headless NLE: frame-accurate cuts on a real timeline, loudness-normalised export, project left for hand finishing","features":["cuts","loudness"],"needs":"filmcraft-cli"}'; exit 0;;
  --check) command -v filmcraft-cli >/dev/null && exit 0; echo "filmcraft-cli not on PATH (storytold/filmcraft release tarball)"; exit 1;;
esac
set -euo pipefail
EDL="${1:?edl}"; OUT="$(realpath -m "${2:?output}")"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
PROJ="${OUT%.*}.fcproj"
python3 - "$EDL" "$T" "$OUT" "$PROJ" <<'PY'
import json, sys
edl, T, out, proj = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3], sys.argv[4]
o = edl["output"]; fps = float(o.get("fps") or 30); TPS = 254016000000          # FilmCraft ticks per second
W, H = o.get("width"), o.get("height"); lufs = (edl.get("audio") or {}).get("lufs", o.get("lufs", -16.0))
imp = {"id": "file.import", "params": {"paths": [edl["source"]]}}
open(f"{T}/0.jsonl", "w").write(json.dumps(imp) + "\n")
rows = [imp, {"id": "file.newSequence", "params": {"name": "edit", "width": W or 1920, "height": H or 1080, "fps": fps, "sampleRate": 48000, "video": 1, "audio": 1}}]
at = 0
for s in edl["segments"]:                                                      # snap every cut to a whole frame so nothing gaps or overlaps
    a = round(s["in"] * fps); n = max(1, round((s["out"] - s["in"]) * fps))
    rows.append({"id": "timeline.place", "params": {"item": "ITEM", "track": "V1", "seconds": at / fps, "sourceIn": round(a / fps * TPS), "duration": round(n / fps * TPS)}})
    at += n
rows += [{"id": "file.save", "params": {"path": proj}},
         {"id": "file.exportMedia", "params": {"path": out, "format": "h264", "bitrateKbps": 16000, "bitrateMode": "vbr1Pass", "loudnessLufs": lufs, "wait": True}}]
json.dump(rows, open(f"{T}/rows.json", "w"))
PY
ITEM="$(filmcraft-cli run "$T/0.jsonl" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read().splitlines()[0])["result"]["items"][0])')"
python3 -c 'import json,sys; [print(json.dumps(r).replace("\"ITEM\"", sys.argv[2])) for r in json.load(open(sys.argv[1]))]' "$T/rows.json" "$ITEM" > "$T/run.jsonl"
filmcraft-cli run "$T/run.jsonl" | tee "$T/out.log" | tail -1 | cut -c1-200 >&2
if grep -q '"ok":false' "$T/out.log"; then grep '"ok":false' "$T/out.log" >&2; echo "a FilmCraft command failed, see above" >&2; exit 1; fi
echo "filmcraft: exported $OUT (project $PROJ)" >&2
