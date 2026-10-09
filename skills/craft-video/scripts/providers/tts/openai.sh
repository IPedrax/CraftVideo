#!/usr/bin/env bash
# TTS provider: any OpenAI-compatible speech endpoint (POST {base}/audio/speech). Covers Kokoro-FastAPI, Speaches, LocalAI,
# Chatterbox servers, VoiceStudio's own /v1 route, and OpenAI itself.
#   OPENAI_BASE_URL   required, e.g. http://127.0.0.1:8880/v1  (a LOCAL server keeps everything on this machine)
#   OPENAI_API_KEY    optional bearer key
#   TTS_MODEL         default tts-1        TTS_VOICE   default alloy
#   OPENAI_EXTRA_JSON optional JSON object merged into the body (e.g. '{"language":"English","seed":7}' for servers that take them)
#   OPENAI_GAP        seconds of silence between sentences (default 0.35)
# Only standard fields are sent by default because OpenAI itself rejects unknown ones. A hosted endpoint uploads your script
# text to a third party: use it only when that is acceptable for the video.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"openai","kind":"tts","summary":"any OpenAI-compatible /audio/speech endpoint (Kokoro-FastAPI, Speaches, LocalAI, VoiceStudio /v1, OpenAI)","design":"instructions (server dependent)","clone":false,"seed":false,"speed":true,"languages":"server dependent","cloud":"depends on OPENAI_BASE_URL"}'; exit 0;;
  --check)
    [ -n "${OPENAI_BASE_URL:-}" ] || { echo "set OPENAI_BASE_URL (and TTS_MODEL / TTS_VOICE) to enable"; exit 1; }
    command -v curl >/dev/null || { echo "curl missing"; exit 1; }
    code=$(curl -s -m 5 -o /dev/null -w '%{http_code}' ${OPENAI_API_KEY:+-H "Authorization: Bearer $OPENAI_API_KEY"} "${OPENAI_BASE_URL%/}/models" 2>/dev/null || true)
    case "$code" in 2*|401|403|404|405) exit 0;; *) echo "no server answering at $OPENAI_BASE_URL (HTTP ${code:-none})"; exit 1;; esac;;
esac
PLAIN="${1:?plain text file}"; OUT="${2:?output audio}"; shift 2
INSTRUCT=""; SPEED=""
while [ $# -gt 0 ]; do
  case "$1" in --instruct) INSTRUCT="$2"; shift 2;; --speed) SPEED="$2"; shift 2;; *) shift;; esac
done
MODEL="${TTS_MODEL:-tts-1}"; VOICE="${TTS_VOICE:-alloy}"; BASE="${OPENAI_BASE_URL%/}"
# One request PER SENTENCE (each script line), joined with a fixed gap. Two reasons: the rest of the pipeline needs audible pauses
# between sentences to find the cues, and many servers run sentences together when given the whole script. Lines over 3800
# characters (OpenAI's input cap is 4096) are split at sentence ends. OPENAI_GAP sets the silence between sentences (default 0.35 s).
"$CV_PY" - "$PLAIN" "$OUT" "$BASE" "$MODEL" "$VOICE" "$INSTRUCT" "$SPEED" "${OPENAI_API_KEY:-}" "${OPENAI_EXTRA_JSON:-}" "${OPENAI_GAP:-0.35}" <<'PY'
import json, os, re, subprocess, sys, tempfile, urllib.request
import numpy as np, soundfile as sf
plain, out, base, model, voice, instruct, speed, key, extra, gap = sys.argv[1:11]
SR = 48000
pieces = []
for line in (l.strip() for l in open(plain, encoding="utf-8") if l.strip()):
    while len(line) > 3800:
        cut = max(line.rfind(". ", 0, 3800), line.rfind("? ", 0, 3800), line.rfind("! ", 0, 3800))
        cut = cut + 1 if cut > 0 else 3800
        pieces.append(line[:cut].strip()); line = line[cut:].strip()
    pieces.append(line)
tmp = tempfile.mkdtemp(); wavs = []
for i, text in enumerate(pieces):
    body = {"model": model, "input": text, "voice": voice, "response_format": "wav"}
    if instruct: body["instructions"] = instruct
    if speed: body["speed"] = float(speed)
    if extra: body.update(json.loads(extra))
    req = urllib.request.Request(base + "/audio/speech", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + key} if key else {})})
    try:
        data = urllib.request.urlopen(req, timeout=900).read()
    except Exception as e:
        detail = getattr(e, "read", lambda: b"")()[:300].decode("utf-8", "replace")
        sys.exit(f"openai: request {i + 1}/{len(pieces)} failed: {e} {detail}")
    raw = os.path.join(tmp, f"{i:03d}.in"); open(raw, "wb").write(data)
    w = os.path.join(tmp, f"{i:03d}.wav")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", raw, "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", "-f", "wav", w], check=True)
    wavs.append(w)
silence = np.zeros(int(float(gap) * SR))
audio = [np.zeros(int(0.1 * SR))]
for k, w in enumerate(wavs):
    x, _ = sf.read(w); audio.append(x)
    if k < len(wavs) - 1: audio.append(silence)
sf.write(out, np.concatenate(audio), SR, subtype="PCM_16", format="WAV")
print(f"openai: {len(pieces)} request(s) to {base} (model {model}, voice {voice}), {gap}s between sentences", file=sys.stderr)
PY
