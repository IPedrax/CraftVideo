#!/usr/bin/env bash
# preflight.sh: check the whole suite before planning anything (a storyboard nobody can render is wasted work).
# Prints OK / WARN / FAIL per item and exits 1 if anything FAILs.
PY="${VIDEO_PY:-/mnt/ai/VoiceStudio/.venv/bin/python}"
fail=0
ok()   { printf '  OK    %s\n' "$*"; }
warn() { printf '  WARN  %s\n' "$*"; }
bad()  { printf '  FAIL  %s\n' "$*"; fail=1; }

echo "tools"
for t in filmcraft-cli effectcraft-cli; do
  if command -v $t >/dev/null; then ok "$t $($t --version 2>&1 | head -1)"; else bad "$t not on PATH (release tarballs go in ~/.local, see the plugin README)"; fi
done
for t in ffmpeg ffprobe; do command -v $t >/dev/null && ok "$t" || bad "$t missing (needed for QA and the poster step)"; done
[ -x "$PY" ] && "$PY" -c "import numpy, soundfile, PIL" 2>/dev/null && ok "python deps (numpy, soundfile, PIL) via $PY" \
  || bad "need numpy + soundfile + PIL: set VIDEO_PY to a python that has them (the VoiceStudio venv does)"

echo "voice"
if command -v voicestudio-backend >/dev/null; then
  ok "voicestudio-backend helper"
  if voicestudio-backend status >/dev/null 2>&1; then ok "backend already running on :3900"; else warn "backend stopped (narrate.sh starts it)"; fi
else bad "voicestudio-backend helper missing (see voicestudio-source-install in memory)"; fi
[ -d "${VOICESTUDIO_MODELS:-/mnt/ai/VoiceStudio/.vs/models}/models--openbmb--VoxCPM2" ] && ok "VoxCPM2 weights present (Apache-2.0, safe for client work)" || bad "VoxCPM2 weights missing"
[ -d "${VOICESTUDIO_MODELS:-/mnt/ai/VoiceStudio/.vs/models}/models--k2-fsa--OmniVoice" ] && warn "OmniVoice installed too: its weights are CC-BY-NC (non-commercial), use VoxCPM2 for anything client-facing"

echo "gpu"
if command -v nvidia-smi >/dev/null; then
  free=$(nvidia-smi --query-gpu=memory.total,memory.used --format=csv,noheader,nounits | awk -F, '{print int(($1-$2)/1024)}')
  [ "$free" -ge 8 ] && ok "${free} GB VRAM free (VoxCPM2 needs about 7)" || warn "only ${free} GB VRAM free: close ComfyUI/games or voice generation will fail with a vague 503"
else warn "no nvidia-smi: voice generation will run on CPU (slow)"; fi

echo "fonts (brand: Big Shoulders Display + IBM Plex Mono)"
for f in "Big Shoulders Display" "IBM Plex Mono"; do
  fc-list | grep -qi "$f" && ok "$f" || warn "$f not installed: see reference/effectcraft-scripting.md > Fonts (OFL, from the google/fonts repo)"
done
echo
[ $fail -eq 0 ] && echo "preflight passed" || echo "preflight FAILED"
exit $fail
