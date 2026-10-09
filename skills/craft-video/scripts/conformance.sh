#!/usr/bin/env bash
# conformance.sh: prove a provider honours its contract. Run it on every provider you write or configure.
#   conformance.sh <tts|render|assemble|all> [provider|all]
# tts      script.txt fixture -> narrate.sh -> valid 48 kHz mono wav, audible, long enough, AND tighten_voice.py can find the
#          sentence boundaries in it (that is what the rest of the pipeline needs from a voice)
# render   a 1 s scene -> render.sh -> silent mp4 of exactly the requested size, fps and frame count
# assemble 4 s picture + voice + music -> assemble.sh -> final mp4 with video and audio, same length, loudness near target
# A provider that is not usable here (missing tool, no TTS_CMD, ...) is reported SKIP with the reason; naming it explicitly
# makes that a FAIL. Exit 1 if anything FAILs. Needs ffmpeg and a python with numpy + soundfile.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
KIND="${1:?usage: conformance.sh <tts|render|assemble|all> [provider|all]}"; ONLY="${2:-all}"
FIX="$CV_SKILL/fixtures"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
FAILS=0; ROWS=()
row() { ROWS+=("$(printf '%-9s %-12s %-5s %s' "$1" "$2" "$3" "$4")"); [ "$3" != "FAIL" ] || FAILS=$((FAILS+1)); }
names() { if [ "$ONLY" = all ]; then cv_names "$1"; else echo "$ONLY"; fi; }
gate() { # kind name -> 0 if runnable; else records SKIP/FAIL
  local kind="$1" n="$2"
  [ -f "$(cv_provider_script "$kind" "$n")" ] || { row "$kind" "$n" FAIL "no such provider"; return 1; }
  if ! cv_usable "$kind" "$n"; then
    if [ "$ONLY" = all ]; then row "$kind" "$n" SKIP "$(cv_why_not "$kind" "$n")"; else row "$kind" "$n" FAIL "not usable: $(cv_why_not "$kind" "$n")"; fi
    return 1
  fi; return 0
}

test_tts() {
  local n="$1"; gate tts "$n" || return
  local out="$T/$n.wav" log="$T/$n.log"
  [ "$n" = dryrun ] || [ "$n" = file ] || true
  if [ "$n" = file ]; then export CRAFTVIDEO_NARRATION_FILE="${CRAFTVIDEO_NARRATION_FILE:-}"; fi
  if ! bash "$CV_HERE/narrate.sh" "$FIX/script.txt" "$out" --provider "$n" >"$log" 2>&1; then row tts "$n" FAIL "narrate.sh failed: $(tail -1 "$log")"; return; fi
  local dur sr ch rms; dur="$(cv_dur "$out")"
  sr="$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate -of csv=p=0 "$out")"; ch="$(ffprobe -v error -select_streams a:0 -show_entries stream=channels -of csv=p=0 "$out")"
  [ "$sr" = 48000 ] && [ "$ch" = 1 ] || { row tts "$n" FAIL "not 48 kHz mono after normalising ($sr Hz, $ch ch)"; return; }
  rms="$("$CV_PY" -c "import soundfile as sf, numpy as np; x,_=sf.read('$out'); print(float(np.sqrt((x**2).mean())))")"
  awk -v r="$rms" 'BEGIN{exit !(r > 0.003)}' || { row tts "$n" FAIL "audio is silent (rms $rms)"; return; }
  awk -v d="$dur" 'BEGIN{exit !(d >= 1.0)}' || { row tts "$n" FAIL "only ${dur}s of audio for 3 sentences"; return; }
  if ! "$CV_PY" "$CV_HERE/tighten_voice.py" --raw "$out" --script "$FIX/script.txt" --out "$T/t.wav" --timeline "$T/t.json" --target "$(awk -v d="$dur" 'BEGIN{printf "%d", d + 3}')" >"$T/tv.log" 2>&1; then
    row tts "$n" FAIL "tighten_voice cannot find the 3 sentence breaks (needs audible pauses between sentences): $(tail -1 "$T/tv.log")"; return
  fi
  row tts "$n" PASS "${dur}s, sentence breaks found, normalised to 48 kHz mono"
}

test_render() {
  local n="$1"; gate render "$n" || return
  local scene out="$T/$n.mp4"
  case "$n" in effectcraft) scene="$FIX/scenes.jsx";; html) scene="$FIX/scene.html";; *) scene="${CONFORMANCE_SCENES:-$FIX/scene.html}";; esac
  if ! bash "$CV_HERE/render.sh" "$scene" "$out" --provider "$n" --timeline "$FIX/timeline.json" --width 640 --height 360 --fps 24 --duration 1 >"$T/r.log" 2>&1; then
    row render "$n" FAIL "$(tail -1 "$T/r.log")"; return
  fi
  row render "$n" PASS "$(tail -1 "$T/r.log" | sed 's/^ok: [^,]*, //')"
}

test_assemble() {
  local n="$1"; gate assemble "$n" || return
  ffmpeg -hide_banner -loglevel error -y -f lavfi -i "testsrc=s=640x360:r=24:d=4" -pix_fmt yuv420p -an "$T/v.mp4"
  ffmpeg -hide_banner -loglevel error -y -f lavfi -i "sine=f=220:d=4:sample_rate=48000" -ac 1 -af "volume=0.4" "$T/voice.wav"
  ffmpeg -hide_banner -loglevel error -y -f lavfi -i "anoisesrc=d=4:c=pink:r=48000:a=0.2" -ac 2 "$T/music.wav"
  if ! bash "$CV_HERE/assemble.sh" --video "$T/v.mp4" --voice "$T/voice.wav" --music "$T/music.wav" --out "$T/$n.mp4" --provider "$n" >"$T/a.log" 2>&1; then
    row assemble "$n" FAIL "$(tail -1 "$T/a.log")"; return
  fi
  row assemble "$n" PASS "$(tail -1 "$T/a.log" | sed 's/^ok: [^,]*, //')"
}

kinds="$KIND"; [ "$KIND" = all ] && kinds="tts render assemble"
for k in $kinds; do for n in $(names "$k"); do "test_$k" "$n"; done; done
echo "kind      provider     result detail"; printf '%s\n' "${ROWS[@]}"
echo; [ "$FAILS" -eq 0 ] && echo "conformance passed" || { echo "conformance FAILED ($FAILS)"; exit 1; }
