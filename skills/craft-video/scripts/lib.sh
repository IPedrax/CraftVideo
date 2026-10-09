#!/usr/bin/env bash
# lib.sh: shared helpers for the dispatchers (narrate.sh, render.sh, assemble.sh) and providers/*. Source it; never run it.
#
# A "provider" is one script, providers/<kind>/<name>.sh, with this shape (full contract: reference/providers.md):
#   <name>.sh --info     print one line of JSON describing it
#   <name>.sh --check    exit 0 if usable right now; otherwise print the reason on one line and exit 1
#   <name>.sh <args>     do the work (arguments depend on the kind)
# kinds: tts (script text -> audio), render (scenes -> silent mp4), assemble (video + voice + music -> final mp4),
#        transcribe (recording -> word timings), edit (recording + edit decision list -> edited mp4)
CV_HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CV_SKILL="$(cd "$CV_HERE/.." && pwd)"
CV_VS="${VOICESTUDIO_DIR:-/mnt/ai/VoiceStudio}"
CV_PY="${VIDEO_PY:-$CV_VS/.venv/bin/python}"
[ -x "$CV_PY" ] || CV_PY="$(command -v python3)"          # the scripts only need numpy/soundfile/PIL: any python that has them works

cv_die()  { echo "craft-video: $*" >&2; exit 1; }
cv_warn() { echo "craft-video: warning: $*" >&2; }

# Order tried when nothing is configured. Providers that would fake or upload things (dryrun, file, command) are never
# auto-selected unless configured: a silent fallback to a fake voice would be worse than a clear error.
cv_order() {
  case "$1" in
    tts)      echo "voicestudio openai" ;;
    render)   echo "effectcraft html" ;;
    assemble) echo "filmcraft ffmpeg" ;;
    transcribe) echo "faster-whisper openai" ;;
    edit)     echo "ffmpeg filmcraft" ;;
    *) cv_die "unknown kind '$1' (tts, render, assemble, transcribe, edit)" ;;
  esac
}
cv_provider_script() { echo "$CV_HERE/providers/$1/$2.sh"; }
cv_kinds() { echo "tts render assemble transcribe edit"; }
cv_names() { ls "$CV_HERE/providers/$1" 2>/dev/null | grep '\.sh$' | sed 's/\.sh$//' | sort; }   # only *.sh files are providers (helpers like html-render.mjs sit beside them)

# Configured provider for a kind: env CRAFTVIDEO_<KIND>, then ./craftvideo.json, then ~/.config/craftvideo/config.json
cv_cfg() {
  local kind="$1" var v f
  var="CRAFTVIDEO_$(echo "$kind" | tr 'a-z' 'A-Z')"
  if [ -n "${!var:-}" ]; then echo "${!var}"; return; fi
  for f in ./craftvideo.json "${XDG_CONFIG_HOME:-$HOME/.config}/craftvideo/config.json"; do
    if [ -f "$f" ]; then
      v="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2],""))' "$f" "$kind" 2>/dev/null || true)"
      if [ -n "$v" ]; then echo "$v"; return; fi
    fi
  done
}
cv_cfg_source() {   # where the choice came from, for messages (always returns 0: callers run under set -e)
  local kind="$1" var f v
  var="CRAFTVIDEO_$(echo "$kind" | tr 'a-z' 'A-Z')"
  if [ -n "${!var:-}" ]; then echo "env $var"; return 0; fi
  for f in ./craftvideo.json "${XDG_CONFIG_HOME:-$HOME/.config}/craftvideo/config.json"; do
    if [ -f "$f" ]; then
      v="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2],""))' "$f" "$kind" 2>/dev/null || true)"
      if [ -n "$v" ]; then echo "$f"; return 0; fi
    fi
  done
  return 0
}

cv_usable() { bash "$(cv_provider_script "$1" "$2")" --check >/dev/null 2>&1; }
cv_why_not() { bash "$(cv_provider_script "$1" "$2")" --check 2>&1 | head -1 || true; }   # never non-zero: callers run under set -e

# cv_resolve <kind> [explicit]: print the provider to use. Explicit or configured choices are honoured and must be usable;
# otherwise the first usable provider in cv_order is chosen.
cv_resolve() {
  local kind="$1" want="${2:-}" p
  [ -n "$want" ] || want="$(cv_cfg "$kind")"
  if [ -n "$want" ]; then
    [ -f "$(cv_provider_script "$kind" "$want")" ] || cv_die "unknown $kind provider '$want' (available: $(cv_names "$kind" | tr '\n' ' '))"
    cv_usable "$kind" "$want" || cv_die "$kind provider '$want' is not usable: $(cv_why_not "$kind" "$want")"
    echo "$want"; return
  fi
  for p in $(cv_order "$kind"); do
    if cv_usable "$kind" "$p"; then echo "$p"; return; fi
  done
  cv_die "no usable $kind provider. Tried: $(cv_order "$kind"). Run scripts/providers.sh list, set one up, or write an adapter (reference/providers.md)"
}

# cv_info <kind> <name> <key>: one field of the provider's --info JSON (true/false/strings)
cv_info() {
  bash "$(cv_provider_script "$1" "$2")" --info 2>/dev/null | python3 -c 'import json,sys; d=json.loads(sys.stdin.read() or "{}"); print(d.get(sys.argv[1], ""))' "$3" || true
}

# Any audio ffmpeg can read -> 48 kHz mono PCM16 wav (the TTS contract is enforced here, so adapters may emit mp3/flac/ogg/wav)
cv_wav48() { ffmpeg -hide_banner -loglevel error -y -i "$1" -ac 1 -ar 48000 -c:a pcm_s16le "$2"; }
cv_dur()   { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
cv_words() { wc -w < "$1" | tr -d ' '; }

# Substitute {KEY} placeholders in a template with shell-quoted values: cv_subst 'cmd {a} {b}' a=1 b="x y"
cv_subst() {
  python3 - "$@" <<'PY'
import shlex, sys
tpl, pairs = sys.argv[1], sys.argv[2:]
for p in pairs:
    k, _, v = p.partition("=")
    tpl = tpl.replace("{" + k + "}", shlex.quote(v))
print(tpl)
PY
}
