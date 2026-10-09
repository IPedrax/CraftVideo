#!/usr/bin/env bash
# assemble.sh: the mix-and-export dispatcher. Picture + narration + music -> one final mp4 (H.264 + AAC) at the target loudness.
#   assemble.sh --video silent.mp4 [--voice narration.wav] [--music music.wav] --out final.mp4 [--provider NAME]
#               [--music-db -9] [--lufs -16] [--bitrate 16000] [--project edit.proj]
#               [--interchange edl|xml|fcpxml|otio|aaf|omf --interchange-out timeline.otio]
# Provider order: --provider, env CRAFTVIDEO_ASSEMBLE, ./craftvideo.json, ~/.config/craftvideo/config.json, then filmcraft, ffmpeg.
# --interchange writes the edited timeline for another editor (Resolve, Premiere, Final Cut, Kdenlive, Avid) and needs a provider
# that supports it (filmcraft). The result is checked here for every provider: video and audio present, same length as the
# picture, loudness near the target.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
PROV=""; VIDEO=""; VOICE=""; MUSIC=""; OUT=""; LUFS=-16; IFMT=""; IOUT=""; PASS=()
while [ $# -gt 0 ]; do
  [ $# -ge 2 ] || cv_die "option $1 needs a value"
  case "$1" in
    --provider) PROV="$2";;
    --video) VIDEO="$2"; PASS+=("$1" "$2");; --voice) VOICE="$2"; PASS+=("$1" "$2");; --music) MUSIC="$2"; PASS+=("$1" "$2");;
    --out) OUT="$2"; PASS+=("$1" "$2");; --lufs) LUFS="$2"; PASS+=("$1" "$2");;
    --interchange) IFMT="$2"; PASS+=("$1" "$2");; --interchange-out) IOUT="$2"; PASS+=("$1" "$2");;
    *) PASS+=("$1" "$2");;
  esac; shift 2
done
[ -n "$VIDEO" ] && [ -n "$OUT" ] || cv_die "usage: assemble.sh --video silent.mp4 [--voice n.wav] [--music m.wav] --out final.mp4 [--provider NAME]"
for f in "$VIDEO" "$VOICE" "$MUSIC"; do [ -z "$f" ] || [ -s "$f" ] || cv_die "input not found: $f"; done
[ -z "$IFMT" ] || [ -n "$IOUT" ] || cv_die "--interchange needs --interchange-out FILE"
NAME="$(cv_resolve assemble "$PROV")"
if [ -n "$IFMT" ]; then
  SUP="$(cv_info assemble "$NAME" interchange)"
  case ",$SUP," in *",$IFMT,"*) ;; *) cv_die "provider '$NAME' cannot export '$IFMT' timelines (supports: ${SUP:-none}); rerun with --provider filmcraft for the hand-off";; esac
fi
echo "assembling with provider '$NAME' (voice $([ -n "$VOICE" ] && echo yes || echo no), music $([ -n "$MUSIC" ] && echo yes || echo no), target $LUFS LUFS)" >&2
bash "$(cv_provider_script assemble "$NAME")" "${PASS[@]}"
[ -s "$OUT" ] || cv_die "provider '$NAME' produced no file at $OUT"
[ -z "$IFMT" ] || [ -s "$IOUT" ] || cv_die "provider '$NAME' did not write the $IFMT timeline to $IOUT"

# ---- enforce the output contract ----
VS="$(ffprobe -v error -select_streams v -show_entries stream=index -of csv=p=0 "$OUT" | wc -l | tr -d ' ')"
AS="$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$OUT" | wc -l | tr -d ' ')"
[ "$VS" -ge 1 ] || cv_die "provider '$NAME': the output has no video stream"
if [ -n "$VOICE$MUSIC" ] && [ "$AS" -lt 1 ]; then cv_die "provider '$NAME': the output has no audio stream although voice/music were given"; fi
PD="$(ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 "$VIDEO")"
OD="$(ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 "$OUT")"
python3 -c 'import sys; sys.exit(0 if abs(float(sys.argv[1]) - float(sys.argv[2])) <= 0.1 else 1)' "$PD" "$OD" || cv_die "provider '$NAME': output picture is ${OD}s but the input picture is ${PD}s"
LU="n/a"
if [ "$AS" -ge 1 ]; then
  LU="$(ffmpeg -hide_banner -nostats -i "$OUT" -vn -af ebur128 -f null - 2>&1 | grep -E '^\s+I:' | tail -1 | awk '{print $2}')"
  python3 -c 'import sys; sys.exit(0 if abs(float(sys.argv[1]) - float(sys.argv[2])) <= 1.5 else 1)' "$LU" "$LUFS" \
    || cv_warn "loudness is ${LU} LUFS, more than 1.5 LU from the ${LUFS} target (finish.sh will gate on this)"
fi
echo "ok: $OUT, video ${OD}s, loudness ${LU} LUFS (provider $NAME)"
