#!/usr/bin/env bash
# preflight.sh: check what the video will actually be made with, before planning anything (a storyboard nobody can render is
# wasted work). It checks the core tools, resolves a provider for each stage (explicit choice, config, or first usable), and
# then checks the extras ONLY for the providers selected. Prints OK / WARN / FAIL; exits 1 if a stage has no usable provider.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
fail=0
ok()   { printf '  OK    %s\n' "$*"; }
info() { printf '  ..    %s\n' "$*"; }
warn() { printf '  WARN  %s\n' "$*"; }
bad()  { printf '  FAIL  %s\n' "$*"; fail=1; }

echo "core"
for t in ffmpeg ffprobe; do command -v $t >/dev/null && ok "$t" || bad "$t missing (QA, poster and the ffmpeg providers need it)"; done
"$CV_PY" -c "import numpy, soundfile, PIL" 2>/dev/null && ok "python deps (numpy, soundfile, PIL) via $CV_PY" \
  || bad "need numpy + soundfile + PIL: set VIDEO_PY to a python that has them (a VoiceStudio venv does)"

echo "providers (providers.sh list shows every option and why a missing one is missing)"
declare -A CHOSEN
for kind in $(cv_kinds); do
  if out="$(cv_resolve "$kind" 2>&1)"; then
    CHOSEN[$kind]="$out"; src="$(cv_cfg_source "$kind")"; ok "$kind: $out (${src:-auto})"
    alts=""; for n in $(cv_names "$kind"); do [ "$n" != "$out" ] && cv_usable "$kind" "$n" && alts="$alts $n"; done
    [ -z "$alts" ] || info "$kind alternatives usable here:$alts"
  else
    CHOSEN[$kind]=""; bad "$kind: $(echo "$out" | sed 's/^craft-video: //')"
  fi
done

if [ "${CHOSEN[tts]:-}" = voicestudio ]; then
  echo "voice engine (voicestudio)"
  bash "$CV_HERE/voicestudio-backend" status >/dev/null 2>&1 && ok "backend already running on :3900" || warn "backend stopped (narrate.sh starts it)"
  [ -d "${VOICESTUDIO_MODELS:-$CV_VS/.vs/models}/models--k2-fsa--OmniVoice" ] && warn "OmniVoice is installed too: its weights are CC-BY-NC (non-commercial); use VoxCPM2 for client-facing work"
  if command -v nvidia-smi >/dev/null; then
    free=$(nvidia-smi --query-gpu=memory.total,memory.used --format=csv,noheader,nounits | awk -F, '{print int(($1-$2)/1024)}')
    [ "$free" -ge 8 ] && ok "${free} GB VRAM free (VoxCPM2 needs about 7)" || warn "only ${free} GB VRAM free: close ComfyUI/games or voice generation fails with a vague 503"
  else warn "no nvidia-smi: voice generation will run on CPU (slow)"; fi
fi
if [ "${CHOSEN[tts]:-}" = dryrun ]; then warn "tts is 'dryrun': placeholder audio, fine for previews, never for a deliverable"; fi
if [ "${CHOSEN[tts]:-}" = openai ] || [ "${CHOSEN[tts]:-}" = command ]; then
  case "${OPENAI_BASE_URL:-}" in http://127.0.0.1*|http://localhost*|"") ;; *) warn "tts sends the script to ${OPENAI_BASE_URL}: a hosted service sees the text";; esac
fi
case "${CHOSEN[render]:-}" in
  effectcraft|html)
    echo "fonts (default brand: Big Shoulders Display + IBM Plex Mono)"
    FONTS="$(fc-list 2>/dev/null || true)"        # capture first: `fc-list | grep -q` dies of SIGPIPE under pipefail
    for f in "Big Shoulders Display" "IBM Plex Mono"; do
      grep -qi "$f" <<<"$FONTS" && ok "$f" || warn "$f not installed: see reference/effectcraft-scripting.md > Fonts (open-licensed, from the google/fonts repo)"
    done;;
esac
echo
[ $fail -eq 0 ] && echo "preflight passed" || echo "preflight FAILED"
exit $fail
