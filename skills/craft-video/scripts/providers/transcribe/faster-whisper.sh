#!/usr/bin/env bash
# transcribe provider: faster-whisper (CTranslate2), local, word timestamps. Never downloads on its own.
#   faster-whisper.sh AUDIO_16K_WAV OUT.json [--language en] [--model small]
#   WHISPER_MODEL   model name (tiny, small, large-v3 ...) or a local path; default: the biggest of large-v3, medium, small that is present
#                   (a 30 s clip takes ~1.4 s on a GPU with small)
#   WHISPER_DIR     folder holding faster-whisper-<name> model directories (default /mnt/ai/Whisper); the Hugging Face cache is searched too
#   WHISPER_DEVICE  auto (default: cuda if usable, else cpu int8), cuda, or cpu
#   CRAFTVIDEO_ALLOW_DOWNLOAD=1  let it fetch a model it does not have (Hugging Face, hundreds of MB to 3 GB)
# Models are looked up in the Hugging Face cache (Systran/faster-whisper-<name>). The cuDNN 8 libraries CTranslate2 needs are taken
# from VoiceStudio's venv (cudnn8_compat) when present. ASR word start times are rough (the first word of a segment often starts early):
# the planner snaps cuts to the audio's energy and never trusts them alone.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
WHISPER_DIR="${WHISPER_DIR:-/mnt/ai/Whisper}"      # a folder of faster-whisper-<name> model directories kept outside the Hugging Face cache
hf_dir() { ls -d "${HF_HOME:-$HOME/.cache/huggingface}/hub/models--Systran--faster-whisper-$1/snapshots/"* 2>/dev/null | head -1; }
dir_of() { local d; for d in "$WHISPER_DIR/faster-whisper-$1" "$(hf_dir "$1")"; do [ -f "$d/model.bin" ] && { echo "$d"; return; }; done; }
MODEL="${WHISPER_MODEL:-}"
if [ -z "$MODEL" ]; then MODEL=small; for m in large-v3 medium; do [ -n "$(dir_of $m)" ] && { MODEL=$m; break; }; done; fi   # no choice made: the biggest model that is here
[ -d "$MODEL" ] || { d="$(dir_of "$MODEL")"; [ -z "$d" ] || MODEL="$d"; }
case "${1:-}" in
  --info)  echo '{"name":"faster-whisper","kind":"transcribe","summary":"local faster-whisper (CTranslate2): word timestamps, GPU or CPU, no download","words":true,"languages":"99 (Whisper)","cloud":false}'; exit 0;;
  --check)
    "$CV_PY" -c "import faster_whisper" 2>/dev/null || { echo "faster_whisper is not importable by $CV_PY (set VIDEO_PY to a python that has it)"; exit 1; }
    if [ -d "$MODEL" ] || [ -n "$(hf_dir "$MODEL")" ] || [ "${CRAFTVIDEO_ALLOW_DOWNLOAD:-}" = 1 ]; then exit 0; fi
    echo "whisper model '$MODEL' is not downloaded (set WHISPER_MODEL to one you have, or CRAFTVIDEO_ALLOW_DOWNLOAD=1 to fetch it)"; exit 1;;
esac
WAV="${1:?audio wav}"; OUT="${2:?output json}"; shift 2
LANGN=""; while [ $# -gt 0 ]; do case "$1" in --language) LANGN="$2";; --model) MODEL="$2";; esac; shift 2; done
CUDNN="$(ls -d "$(dirname "$CV_PY")"/../lib/python*/site-packages/cudnn8_compat/nvidia/cudnn/lib 2>/dev/null | head -1)"
[ -z "$CUDNN" ] || export LD_LIBRARY_PATH="$CUDNN:${LD_LIBRARY_PATH:-}"
"$CV_PY" - "$WAV" "$OUT" "$MODEL" "$LANGN" "${WHISPER_DEVICE:-auto}" "${CRAFTVIDEO_ALLOW_DOWNLOAD:-0}" <<'PY'
import json, sys
from faster_whisper import WhisperModel
wav, out, model, lang, device, allow = sys.argv[1:7]
local = allow != "1"
def load(dev, ct):
    return WhisperModel(model, device=dev, compute_type=ct, local_files_only=local)
m, used = None, ""
if device in ("auto", "cuda"):
    try: m, used = load("cuda", "float16"), "cuda/float16"
    except Exception as e:
        if device == "cuda": sys.exit(f"faster-whisper: CUDA failed: {str(e).splitlines()[0]}")
if m is None: m, used = load("cpu", "int8"), "cpu/int8"
segs, info = m.transcribe(wav, language=lang or None, word_timestamps=True, vad_filter=False)
words = [{"text": w.word.strip(), "start": round(float(w.start), 3), "end": round(float(w.end), 3)} for s in segs for w in (s.words or [])]
json.dump({"language": info.language, "words": words}, open(out, "w"), ensure_ascii=False)
print(f"faster-whisper {model} on {used}: {len(words)} words, language {info.language}", file=sys.stderr)
PY
