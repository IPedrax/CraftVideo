#!/usr/bin/env bash
# conformance.sh: prove a provider honours its contract. Run it on every provider you write or configure.
#   conformance.sh <tts|render|assemble|transcribe|edit|all> [provider|all]
# tts      script.txt fixture -> narrate.sh -> valid 48 kHz mono wav, audible, long enough, AND tighten_voice.py can find the
#          sentence boundaries in it (that is what the rest of the pipeline needs from a voice)
# render   a 1 s scene -> render.sh -> silent mp4 of exactly the requested size, fps and frame count; a provider that advertises alpha is
#          asked for a transparent overlay and the alpha channel is checked; html also renders the three.js example (when three is installed)
#          and fails if the scene is not deterministic
# assemble 4 s picture + voice + music -> assemble.sh -> final mp4 with video and audio, same length, loudness near target
# transcribe  9 s of real speech (fixtures/speech.flac) -> transcribe.sh -> valid word timings in order, inside the audio, and at least
#          70% of the known words recognised
# edit     synthetic footage (fixtures/make_footage.py: speech-shaped bursts, fillers, dead air, a flashing marker that is on exactly while
#          speech plays) -> analyze -> plan_edit -> edit.sh -> qa_edit.py gates (duration, size, fps, loudness, clicks, captions) AND
#          ground-truth checks (speech kept, fillers gone, dead air trimmed, picture and sound still in sync, hiss reduced when the
#          provider claims audio processing), plus a minimal hand-written EDL (source and segments only) and, when FilmCraft is installed, an
#          OTIO and EDL round trip through its importer
# A provider that is not usable here (missing tool, no TTS_CMD, ...) is reported SKIP with the reason; naming it explicitly
# makes that a FAIL. Exit 1 if anything FAILs. Needs ffmpeg and a python with numpy + soundfile.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
KIND="${1:?usage: conformance.sh <tts|render|assemble|transcribe|edit|all> [provider|all]}"; ONLY="${2:-all}"
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
  # features a provider advertises are tested too, not trusted
  if [ "$(cv_info render "$n" alpha)" = True ] || [ "$(cv_info render "$n" alpha)" = true ]; then
    if bash "$CV_HERE/render.sh" "$FIX/scene_alpha.html" "$T/$n-alpha.mov" --provider "$n" --width 320 --height 180 --fps 12 --duration 1 --alpha 1 >"$T/ra.log" 2>&1 \
       && "$CV_PY" - "$T/$n-alpha.mov" <<'PY'
import subprocess, sys
import numpy as np
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", sys.argv[1], "-frames:v", "1", "-vf", "format=rgba", "-f", "rawvideo", "-"], capture_output=True).stdout
a = np.frombuffer(raw, np.uint8).reshape(-1, 4)[:, 3]
sys.exit(0 if a.min() == 0 and a.max() == 255 else 1)    # both fully transparent and fully opaque pixels must exist
PY
    then row render "$n+alpha" PASS "transparent overlay (ProRes 4444) has real alpha"; else row render "$n+alpha" FAIL "alpha output has no transparency: $(tail -1 "$T/ra.log")"; fi
  fi
  if [ "$n" = html ] && [ -f "${THREE_DIR:-$HOME/.local/share/craftvideo/three}/build/three.module.js" ]; then
    if bash "$CV_HERE/render.sh" "$CV_SKILL/examples/three-3d/scene.html" "$T/$n-3d.mp4" --provider "$n" --timeline "$CV_SKILL/examples/three-3d/timeline.json" --width 320 --height 180 --fps 12 --duration 1 >"$T/r3.log" 2>&1 \
       && ! grep -q "WARNING" "$T/r3.log"; then row render "$n+three" PASS "three.js scene renders and is deterministic"
    else row render "$n+three" FAIL "$(grep -m1 -E "WARNING|error|404" "$T/r3.log" || tail -1 "$T/r3.log")"; fi
  elif [ "$n" = html ]; then row render "$n+three" SKIP "three.js not installed (scripts/get_three.sh)"; fi
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

test_transcribe() {
  local n="$1"; gate transcribe "$n" || return
  if ! bash "$CV_HERE/transcribe.sh" "$FIX/speech.flac" "$T/$n.json" --provider "$n" --language en >"$T/tr.log" 2>&1; then row transcribe "$n" FAIL "$(tail -1 "$T/tr.log")"; return; fi
  local res; res="$("$CV_PY" - "$T/$n.json" "$FIX/speech.txt" <<'PY'
import json, re, sys
t = json.load(open(sys.argv[1])); want = re.findall(r"[a-z0-9']+", open(sys.argv[2]).read().lower()); w = t["words"]
if not w: print("FAIL no words"); sys.exit()
if any(x["end"] < x["start"] or (i and x["start"] < w[i - 1]["start"] - 1e-6) for i, x in enumerate(w)): print("FAIL word times out of order"); sys.exit()
if w[-1]["end"] > 9.6: print(f"FAIL a word ends at {w[-1]['end']:.1f}s, the audio is 9.4s"); sys.exit()
got = [g for g in (re.sub(r"[^a-z0-9']", "", x["text"].lower()) for x in w) if g]; hit = sum(1 for x in want if x in got)
print(("PASS" if hit / len(want) >= 0.7 else "FAIL") + f" {len(w)} words, {hit}/{len(want)} known words recognised" + (", word times estimated" if t.get("approx_word_times") else ""))
PY
)"
  row transcribe "$n" "${res%% *}" "${res#* }"
}

test_edit() {
  local n="$1"; gate edit "$n" || return
  local d="$T/edit-$n"; mkdir -p "$d"
  [ -s "$T/footage/rec.mp4" ] || "$CV_PY" "$FIX/make_footage.py" "$T/footage" >/dev/null 2>&1 || { row edit "$n" FAIL "could not make the test footage (needs numpy, soundfile, ffmpeg)"; return; }
  "$CV_PY" "$CV_HERE/analyze.py" "$T/footage/rec.mp4" "$d/analysis.json" >/dev/null 2>&1 || { row edit "$n" FAIL "analyze.py failed"; return; }
  "$CV_PY" "$CV_HERE/plan_edit.py" --source "$T/footage/rec.mp4" --analysis "$d/analysis.json" --transcript "$T/footage/rec.transcript.json" --out "$d/edit.json" >/dev/null 2>&1 || { row edit "$n" FAIL "plan_edit.py failed"; return; }
  if ! bash "$CV_HERE/edit.sh" "$d/edit.json" "$d/out.mp4" --provider "$n" --transcript "$T/footage/rec.transcript.json" >"$d/log" 2>&1; then row edit "$n" FAIL "$(tail -1 "$d/log")"; return; fi
  local srt=(); [ ! -s "$d/out.srt" ] || srt=(--srt "$d/out.srt")
  "$CV_PY" "$CV_HERE/qa_edit.py" "$d/edit.json" "$d/out.mp4" "${srt[@]}" >"$d/qa" 2>&1 || { row edit "$n" FAIL "$(grep FAIL "$d/qa" | head -1 | sed 's/^ *FAIL *//')"; return; }
  local skip=(); bash "$(cv_provider_script edit "$n")" --info | grep -q '"audio"' || skip=(--no-hiss)
  "$CV_PY" "$FIX/check_footage.py" "$d/edit.json" "$d/out.mp4" "$T/footage/rec.truth.json" "${skip[@]}" >"$d/gt" 2>&1 || { row edit "$n" FAIL "$(grep FAIL "$d/gt" | head -1 | sed 's/^ *FAIL *//')"; return; }
  printf '{"source":"%s","segments":[{"in":1.0,"out":4.2},{"in":6.5,"out":10.0}]}' "$T/footage/rec.mp4" > "$d/min.json"      # the smallest valid EDL, written by hand
  bash "$CV_HERE/edit.sh" "$d/min.json" "$d/min.mp4" --provider "$n" >"$d/minlog" 2>&1 || { row edit "$n" FAIL "a hand-written EDL (source and segments only) was refused: $(tail -1 "$d/minlog")"; return; }
  row edit "$n" PASS "$(sed -n 's/^ok: [^,]*, //p' "$d/log" | tail -1), QA, ground truth and a minimal hand-written EDL passed"
  if [ "$n" = ffmpeg ] && command -v filmcraft-cli >/dev/null; then       # the cut, written as OTIO and as EDL, must survive a real NLE importer
    local res; res="$("$CV_PY" - "$CV_HERE" "$d" <<'PY'
import json, re, subprocess, sys
here, d = sys.argv[1], sys.argv[2]; edl = json.load(open(f"{d}/edit.json")); fps = edl["output"]["fps"]
def tc(s): f = round(s * fps); n = round(fps); return f"{f // (n * 3600):02d}:{(f // (n * 60)) % 60:02d}:{(f // n) % 60:02d}:{f % n:02d}"
want = [(tc(s["in"]), tc(s["out"])) for s in edl["segments"]]
pat = re.compile(r"^\d{3}\s+\S+\s+\S+\s+\S\s+(\d\d:\d\d:\d\d:\d\d) (\d\d:\d\d:\d\d:\d\d) ", re.M)
for fmt in ("otio", "edl"):
    subprocess.run([sys.executable, f"{here}/interchange.py", f"{d}/edit.json", f"{d}/x.{fmt}", "--format", fmt], check=True, capture_output=True)
    rows = [{"id": "file.import", "params": {"paths": [edl["source"]]}}, {"id": "file.import", "params": {"paths": [f"{d}/x.{fmt}"]}}]
    if fmt == "otio": rows += [{"id": "sequence.open", "params": {"item": 2}}, {"id": "file.exportEdl", "params": {"path": f"{d}/rt.edl"}}]
    open(f"{d}/imp.jsonl", "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
    out = subprocess.run(["filmcraft-cli", "run", f"{d}/imp.jsonl"], capture_output=True, text=True).stdout
    if '"ok":false' in out or '"offlineMedia":[]' not in out: print(f"FAIL FilmCraft could not import the {fmt.upper()} with its media linked"); sys.exit()
ev = pat.findall(open(f"{d}/rt.edl").read()); half = [e for e in ev[0::2]]
print("PASS" if ev[0::2] == want and ev[1::2] == want else "FAIL", "OTIO and EDL import into FilmCraft with media linked; the cuts survive a round trip" if ev[0::2] == want else "the cuts changed in a FilmCraft round trip")
PY
)"
    row edit "interchange" "${res%% *}" "${res#* }"
  fi
}

kinds="$KIND"; [ "$KIND" = all ] && kinds="tts render assemble transcribe edit"
for k in $kinds; do for n in $(names "$k"); do "test_$k" "$n"; done; done
echo "kind      provider     result detail"; printf '%s\n' "${ROWS[@]}"
echo; [ "$FAILS" -eq 0 ] && echo "conformance passed" || { echo "conformance FAILED ($FAILS)"; exit 1; }
