#!/usr/bin/env bash
# edit.sh: the edit dispatcher. Applies an edit decision list (edit.json from plan_edit.py, or one you wrote or changed) to the recording.
#   edit.sh edit.json OUT.mp4 [--provider NAME] [--transcript transcript.json] [--caption-style box|plain|karaoke]
#           [--title "A Proper Title"] [--interchange otio|edl --interchange-out FILE]
# Name OUT after the video (ai-is-taking-games-apart.mp4, not edited.mp4). --title also writes it into the file's metadata (a lossless
# stream copy, whatever the provider, chapters kept), which is what players and uploads show.
# Provider order: --provider, env CRAFTVIDEO_EDIT, ./craftvideo.json, ~/.config/craftvideo/config.json, then ffmpeg, filmcraft.
# The EDL needs only {source, segments}; edl.py fills in the rest from the recording.
# Captions: if the EDL enables them and a transcript is given, they are remapped through the cuts, written next to OUT as .srt (sidecar)
# and burned in (unless the EDL says burn=false). --interchange writes the CUT as a timeline for another editor (OTIO or CMX3600 EDL).
# The result is checked for every provider: duration = the kept segments (within 2 frames), size and fps as asked, audio present if the
# source had it. A provider that cannot do something the EDL asks for (zoom, colour, music ...) is named in a warning, never silent.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
EDL="${1:?usage: edit.sh edit.json OUT.mp4 [--provider NAME] [--transcript T.json] [--interchange otio|edl --interchange-out F]}"; OUT="${2:?output file}"; shift 2
PROV=""; TR=""; CSTYLE=""; IFMT=""; IOUT=""; TITLE=""
while [ $# -gt 0 ]; do
  [ $# -ge 2 ] || cv_die "option $1 needs a value"
  case "$1" in --provider) PROV="$2";; --transcript) TR="$2";; --caption-style) CSTYLE="$2";; --interchange) IFMT="$2";; --interchange-out) IOUT="$2";; --title) TITLE="$2";; *) cv_die "unknown option $1";; esac; shift 2
done
[ -s "$EDL" ] || cv_die "edit decision list not found: $EDL"
[ -z "$IFMT" ] || [ -n "$IOUT" ] || cv_die "--interchange needs --interchange-out FILE"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
# a hand-written EDL may be just {source, segments}: complete it from the source, and give every step below the completed copy
"$CV_PY" "$CV_HERE/edl.py" "$EDL" "$T/edl.json" || exit 1
EDL="$T/edl.json"
SRC="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source"])' "$EDL")"
[ -s "$SRC" ] || cv_die "the EDL's source recording is missing: $SRC"
NAME="$(cv_resolve edit "$PROV")"
CAPS_ON="$(python3 -c 'import json,sys; c=json.load(open(sys.argv[1])).get("captions") or {}; print("1" if c.get("enabled") else "")' "$EDL")"
ARGS=()
if [ -n "$CAPS_ON" ]; then
  if [ -z "$TR" ]; then cv_warn "the EDL enables captions but no --transcript was given: no captions"
  else
    STYLE="${CSTYLE:-$(python3 -c 'import json,sys; print((json.load(open(sys.argv[1])).get("captions") or {}).get("style","box"))' "$EDL")}"; [ "$STYLE" != karaoke ] || true
    case "$STYLE" in box|plain|karaoke) ;; *) STYLE=box;; esac
    SRT="${OUT%.*}.srt"
    "$CV_PY" "$CV_HERE/captions.py" --transcript "$TR" --edl "$EDL" --srt "$SRT" --ass "$T/captions.ass" --style "$STYLE" >&2
    BURN="$(python3 -c 'import json,sys; print("0" if (json.load(open(sys.argv[1])).get("captions") or {}).get("burn", True) is False else "1")' "$EDL")"
    [ "$BURN" = 1 ] && ARGS+=(--ass "$T/captions.ass")
  fi
fi
CH="$(python3 - "$EDL" "$T/chapters.txt" <<'PY'
import json, sys
e = json.load(open(sys.argv[1])); ch = e.get("chapters") or []
if ch:
    tot = sum(s["out"] - s["in"] for s in e["segments"]); L = [";FFMETADATA1"]
    for i, c in enumerate(ch):
        end = ch[i + 1]["at"] if i + 1 < len(ch) else tot
        L += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(c['at'] * 1000)}", f"END={int(end * 1000)}", f"title={c['title']}"]
    open(sys.argv[2], "w").write("\n".join(L) + "\n"); print(sys.argv[2])
PY
)"
[ -z "$CH" ] || ARGS+=(--chapters "$CH")

# what the EDL asks for vs what the provider can do
python3 - "$EDL" "$(bash "$(cv_provider_script edit "$NAME")" --info)" "$([ -n "${ARGS[*]:-}" ] && printf '%s ' "${ARGS[@]}")" <<'PY' >&2 || true
import json, sys
e, info = json.load(open(sys.argv[1])), json.loads(sys.argv[2]); feats = set(info.get("features", []))
a = e.get("audio") or {}; v = e.get("video") or {}; ask = set()
if any(s.get("zoom", 1) > 1 for s in e["segments"]): ask.add("zoom")
if any(a.get(k) for k in ("denoise", "compress", "presence", "highpass")): ask.add("audio")
if e.get("music"): ask.add("music")
if v.get("color") not in (None, "none") or v.get("lut"): ask.add("color")
if v.get("stabilize"): ask.add("stabilize")
if (e.get("output") or {}).get("reframe", "none") != "none": ask.add("reframe")
if e.get("overlays"): ask.add("overlays")
if e.get("chapters"): ask.add("chapters")
if "--ass" in sys.argv[3].split(): ask.add("captions")
missing = sorted(ask - feats)
if missing: print(f"craft-video: warning: provider '{info['name']}' does not do: {', '.join(missing)}; those parts of the EDL will be ignored")
PY
echo "applying $(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["segments"]))' "$EDL") segments with provider '$NAME'" >&2
bash "$(cv_provider_script edit "$NAME")" "$EDL" "$OUT" "${ARGS[@]}"
[ -s "$OUT" ] || cv_die "provider '$NAME' produced no file at $OUT"

# ---- enforce the output contract ----
python3 - "$EDL" "$OUT" <<'PY' || exit 1
import json, subprocess, sys
e = json.load(open(sys.argv[1])); out = sys.argv[2]
want = sum(s["out"] - s["in"] for s in e["segments"]); fps = (e.get("output") or {}).get("fps") or 30
def ff(*a): return subprocess.run(["ffprobe", "-v", "error", *a], capture_output=True, text=True).stdout.strip()
vs = ff("-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,duration", "-of", "csv=p=0", out)
au = ff("-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", out)
src_au = ff("-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", e["source"])
src_v = ff("-select_streams", "v", "-show_entries", "stream=index", "-of", "csv=p=0", e["source"])
bad = []
dur = float(ff("-show_entries", "format=duration", "-of", "csv=p=0", out) or 0)
if abs(dur - want) > max(0.1, 2 / fps): bad.append(f"duration {dur:.2f}s but the kept segments add up to {want:.2f}s")
if src_v and not vs: bad.append("the source has video but the output does not")
if vs:
    w, h, r, _ = vs.split(",")[:4]; o = e.get("output") or {}
    if o.get("width") and (int(w), int(h)) != (o["width"] - o["width"] % 2, o["height"] - o["height"] % 2): bad.append(f"size {w}x{h}, wanted {o['width']}x{o['height']}")
    n, d = map(float, r.split("/"));
    if abs(n / d - fps) > 0.05: bad.append(f"fps {n / d:.3f}, wanted {fps}")
if src_au and not au and (e.get("music") is None): bad.append("the source has audio but the output does not")
if bad:
    print("craft-video: the edit broke the output contract: " + "; ".join(bad), file=sys.stderr); sys.exit(1)
print(f"ok: {out}, {dur:.2f}s from {e['stats']['source_duration']}s" + (f", {w}x{h}" if vs else ", audio only"))
PY
if [ -n "$TITLE" ]; then
  ffmpeg -hide_banner -loglevel error -y -i "$OUT" -map 0 -c copy -metadata title="$TITLE" -movflags +faststart "$T/titled.${OUT##*.}" && mv "$T/titled.${OUT##*.}" "$OUT" || cv_die "could not write the title into $OUT"
  echo "title: $TITLE" >&2
fi
if [ -n "$IFMT" ]; then "$CV_PY" "$CV_HERE/interchange.py" "$EDL" "$IOUT" --format "$IFMT" >&2; fi
