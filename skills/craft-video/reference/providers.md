# Providers: how the skill adapts to other TTS engines, renderers and editors

The skill is a pipeline of **stages**. Each stage has a **contract** (what it must hand to the next one) and one or more
**providers** that fulfil it. The dispatchers (`narrate.sh`, `render.sh`, `assemble.sh`) pick a provider, run it, and then
**enforce the contract on whatever came back**, so a new tool is one small adapter script, never a rewrite.

```
script.txt ──narrate.sh──▶ narration_raw.wav ──tighten_voice.py──▶ narration.wav + timeline.json (the cues)
scenes ─────render.sh────▶ silent.mp4 (exact size, fps, frames)         ▲ every scene is timed from these cues
cues.json ──synth_music.py▶ music.wav
silent.mp4 + narration.wav + music.wav ──assemble.sh──▶ final.mp4 (+ optional editor timeline)  ──finish.sh──▶ QA gates
```

## The three contracts

| Stage | Provider is handed | Provider must produce | The dispatcher then enforces |
|---|---|---|---|
| **tts** | `PLAIN_TEXT_FILE OUT [--instruct T] [--seed N] [--language L] [--speed X] [--ref F --ref-text T]` (one sentence per line, labels stripped; `OUT` ends in `.wav`) | speech in `OUT`, any format ffmpeg can read | converted to 48 kHz mono PCM16; longer than 0.3 s; warns if the length is far from 2.6 words/s |
| **render** | `SCENES OUT.mp4 --timeline F --width W --height H --fps N --duration S [--brand F] [--project F] [--stills "t.." --sheet F]` | a silent H.264 mp4 | exact width, height, fps and frame count (`round(fps x duration)`); any audio track is stripped with a warning |
| **assemble** | `--video V [--voice N] [--music M] --out OUT [--music-db -9] [--lufs -16] [--bitrate K] [--project P] [--interchange FMT --interchange-out FILE]` | a final mp4 with video and audio | video and audio streams present, picture length equal to the input, loudness within 1.5 LU of the target, interchange file written if asked |

One more rule on top of the contract for **tts**: sentences must be **separated by audible pauses** (about 0.2 s or more at -38 dB),
because `tighten_voice.py` finds each sentence's start from them. An engine that runs sentences together should be called once
per sentence and joined with a fixed gap, which is what `providers/tts/openai.sh` does.

## Provider protocol

A provider is `scripts/providers/<kind>/<name>.sh`. It must answer three calls and nothing else is required:

```
<name>.sh --info     one line of JSON: {"name","kind","summary", plus capabilities}
<name>.sh --check    exit 0 if usable right now; otherwise print the reason on ONE line and exit 1
<name>.sh <args>     do the work (arguments per the table above)
```

Capabilities the dispatchers read from `--info`: tts `clone` and `design` (set `false` if the engine cannot; the dispatcher then
refuses `--ref` and warns on `--instruct` instead of silently ignoring them), render `stills`, assemble `interchange`
(comma list of formats it can write, empty if none). Logs go to stderr. Never prompt. Exit non-zero with a one-line reason on failure.

## Choosing a provider

First match wins: `--provider NAME` on the dispatcher, env `CRAFTVIDEO_TTS` / `CRAFTVIDEO_RENDER` / `CRAFTVIDEO_ASSEMBLE`,
`./craftvideo.json` (this project), `~/.config/craftvideo/config.json` (you), then the first **usable** provider in the auto
order (tts: voicestudio, openai; render: effectcraft, html; assemble: filmcraft, ffmpeg). `dryrun`, `file` and `command` are never
auto-selected: a silent fallback to a fake voice, or to a command you did not mean to run, would be worse than a clear error.

```bash
bash scripts/providers.sh list              # every provider, usable here or not, and why
bash scripts/providers.sh which             # what will be used now and where the choice came from
bash scripts/providers.sh set render html   # remember it for this project (--global for all projects)
bash scripts/conformance.sh all             # prove every usable provider honours its contract
```

## Bundled providers (all tested here; "live" means it ran against the real engine)

| Kind | Provider | What it is | Tested |
|---|---|---|---|
| tts | `voicestudio` | local VoiceStudio REST, VoxCPM2 default: voice design, cloning, 30 languages | live, conformance passes |
| tts | `openai` | any OpenAI-compatible `/audio/speech` server (Kokoro-FastAPI, Speaches, LocalAI, Chatterbox servers, OpenAI itself); one request per sentence | live against VoiceStudio's own `/v1`, conformance passes |
| tts | `command` | any CLI via the `TTS_CMD` template | with a stand-in command, conformance passes |
| tts | `file` | your own recording (`CRAFTVIDEO_NARRATION_FILE`) | narrate.sh with the first video's narration |
| tts | `dryrun` | speech-shaped placeholder audio for previews, never a deliverable | conformance passes |
| render | `effectcraft` | scripted compositions (After Effects-style JS), CPU, 306 effects, expressions | live, conformance passes |
| render | `html` | HTML/CSS/JS drawn by headless Chromium, anything the web can draw | live incl. a CSS-keyframes scene, conformance passes |
| render | `command` | any renderer via `RENDER_CMD` | with a stand-in command, conformance passes |
| assemble | `filmcraft` | headless NLE: tracks, gain, loudness, **editor interchange** (edl, xml, fcpxml, otio, aaf, omf) | live, export of identical size to the first video's; the OTIO file was checked structurally |
| assemble | `ffmpeg` | mix + two-pass loudnorm + mux, **no editor needed** | live on the first video's media, QA gates pass |
| assemble | `command` | any editor or mixer via `ASSEMBLE_CMD` | with a stand-in command, conformance passes |

Not tested here: importing the interchange files into DaVinci Resolve, Premiere, Final Cut or Kdenlive (the files are produced by
FilmCraft; media is referenced by absolute path, so import where those paths exist or relink).

## Writing a provider

1. Copy the closest bundled provider to `scripts/providers/<kind>/<yourname>.sh`.
2. Implement `--info`, `--check` and the work. Put heavy setup behind `--check` returning a reason, not a crash.
3. `bash scripts/conformance.sh <kind> <yourname>`. It fails with the exact mismatch (size, frames, silence, missing pauses...).
4. `bash scripts/providers.sh set <kind> <yourname>`. To make it part of the auto order, add its name to `cv_order` in `lib.sh`.

Skeleton (tts; render and assemble have the same three-call shape):

```bash
#!/usr/bin/env bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"mytts","kind":"tts","summary":"what it is","design":false,"clone":false}'; exit 0;;
  --check) command -v my-tts >/dev/null && exit 0; echo "my-tts is not installed"; exit 1;;
esac
PLAIN="$1"; OUT="$2"; shift 2                       # then parse --instruct / --seed / --language / --speed / --ref ...
my-tts --text-file "$PLAIN" --out "$OUT"            # write speech to $OUT, any format ffmpeg reads
```

### No script needed: the command providers

Set a template and the matching `command` provider does the rest (values are shell-quoted for you):

| Provider | Variable | Placeholders |
|---|---|---|
| tts | `TTS_CMD` | `{script} {out} {instruct} {seed} {language} {speed} {ref} {ref_text}` |
| render | `RENDER_CMD` | `{scenes} {out} {timeline} {width} {height} {fps} {duration} {brand} {project}` |
| assemble | `ASSEMBLE_CMD` | `{video} {voice} {music} {out} {music_db} {lufs} {bitrate} {project}` |

## Recipes for other tools (sketches: only the ones marked tested were run here)

**TTS** (set `CRAFTVIDEO_TTS=command` plus `TTS_CMD`, or use `openai` for servers):
- Piper: `piper --model /path/en_US-lessac-medium.onnx --output_file {out} < {script}`. Run `conformance.sh tts command` to confirm the pauses
  between sentences are long enough (Piper has a sentence-silence option if they are not).
- espeak-ng (robotic, but offline and instant): `espeak-ng -v en-us -s 150 -f {script} -w {out}`
- edge-tts: `edge-tts --file {script} --voice en-US-AndrewNeural --write-media {out}` (a hosted service: the text leaves the machine)
- Kokoro-FastAPI, Speaches, LocalAI: `export OPENAI_BASE_URL=http://127.0.0.1:8880/v1 TTS_MODEL=kokoro TTS_VOICE=af_bella`, `providers.sh set tts openai`
- OpenAI hosted: `OPENAI_BASE_URL=https://api.openai.com/v1`, `OPENAI_API_KEY`, `TTS_MODEL=gpt-4o-mini-tts` (hosted: the text leaves the machine)
- ElevenLabs and other hosted APIs: wrap a `curl` call in a script and point `TTS_CMD` at it (hosted: the text leaves the machine, and
  check the service's licence for your use). Tested: the openai and command mechanics, not these services.

**Picture:**
- React/Tailwind/SVG/canvas/WebGL: use the `html` provider (`reference/html-scenes.md`). Tested.
- Remotion: `RENDER_CMD='npx remotion render src/index.ts Main {out} --width={width} --height={height} --fps={fps}'`. Sketch.
- Manim: `RENDER_CMD='manim -qh --fps {fps} -o {out} {scenes} Main'`. Sketch (check the output size and name match `{out}`).
- Blender: `RENDER_CMD='blender -b {scenes} -o //frames_ -F PNG -a && ffmpeg ... {out}'`. Sketch.

**Editor hand-off (for people who finish in a real editor):**
- Any NLE that imports OpenTimelineIO, FCPXML, FCP7 XML, EDL or AAF: `assemble.sh --provider filmcraft --interchange otio --interchange-out edit.otio`
  (formats: edl, xml, fcpxml, otio, aaf, omf). Produced and structurally checked here; not imported into those editors.
- DaVinci Resolve scripting, Kdenlive (`melt`), Shotcut, Blender VSE, Premiere/After Effects ExtendScript: `ASSEMBLE_CMD` with your script. Sketch.
