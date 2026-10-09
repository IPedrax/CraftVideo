---
name: craft-video
description: "Make or edit video on your own machine. MAKE: a short narrated motion-graphics video (15 to 60 s, 16:9, 9:16 or 1:1) from a topic, with brag's hook, reveal, highlights, punchline storyboard, then whatever TTS, renderer and editor are available (VoiceStudio or any OpenAI-compatible or command-line TTS; EffectCraft, HTML/CSS/Three.js/WebGPU in headless Chromium, or any renderer; FilmCraft, ffmpeg, or any editor), a generated soundtrack and measured QA gates. EDIT: take a recording (talking head, screen capture with narration, podcast) and cut it professionally: dead air and filler words out, audio denoised and levelled to -16 LUFS, jump-cut zooms, burned-in or sidecar captions, reframing to vertical, titles, music with ducking, chapters, OTIO or EDL hand-off to Resolve, Premiere, Final Cut or Kdenlive. Both modes can add 3D and motion graphics: Three.js scenes, img2threejs models, shaders, GSAP, and transparent overlays composited onto the footage. Use when the user asks for a video, explainer, announcement or launch clip, social video, a 'brag' video, 'make a video about X'; or to edit, cut, clean up, caption, tighten or professionalise a recording, remove ums and silences, make a video look more professional; or for 3D or motion graphics in a video. Not for generated live-action footage, avatars, lip-sync, or photoreal people."
---

# craft-video

Two modes on one set of swappable tools. **Make** is narration-first: the script is spoken first, then every on-screen event is placed on a
spoken cue. **Edit** takes a recording and cuts, cleans, captions and levels it from measurements. The tools are **providers** behind
**contracts** (voice, picture, mix; transcribe, edit), so the same workflow runs on whatever is installed and a new tool is one small adapter.

| The user wants | Mode | Start at |
|---|---|---|
| a video from a topic, product or news item (the picture is graphics, text, numbers, 3D) | **A: make** | "Mode A" below |
| an existing recording cut, cleaned up, captioned, levelled, reframed, or made to look professional | **B: edit** | "Mode B" below, then `reference/edit.md` |
| 3D, shaders, kinetic type, lower thirds or other motion graphics in either | **C: motion layer** | "Motion graphics and 3D" below, then `reference/motion-graphics.md` |

Both can combine: edit a recording, then lay rendered 3D or motion-graphics overlays on it; or make a video whose picture is a Three.js scene.

```
research -> storyboard (brag) -> script -> narrate -> tighten (timeline.json) -> scenes -> review stills
                                                             \-> music cues -> synth -> assemble -> finish + QA -> deliver
              narrate.sh = tts provider · render.sh = render provider · assemble.sh = assemble provider
```

`S="${CLAUDE_SKILL_DIR}/scripts"` below. Work in `./brag-output/work/` (brag's layout; deliverables go in `./brag-output/`).
`PY="${VIDEO_PY:-${VOICESTUDIO_DIR:-/mnt/ai/VoiceStudio}/.venv/bin/python}"` (any python with numpy, soundfile, PIL works).
Worked examples with every input file: `examples/decomp-30s/` (EffectCraft + VoiceStudio + FilmCraft), `examples/html-hello/` (HTML scene), and for the
motion layer `three-3d`, `img2threejs-bridge`, `webgpu-shader`, `gsap-timeline`, `overlay-lowerthird` (see `examples/README.md`).

## Adapting to the tools that exist

| Stage | Dispatcher | Bundled providers | Falls back to |
|---|---|---|---|
| voice | `narrate.sh` | `voicestudio`, `openai` (any OpenAI-compatible server), `command` (any CLI), `file` (your recording), `dryrun` (placeholder) | first usable of voicestudio, openai |
| picture | `render.sh` | `effectcraft` (.jsx), `html` (.html), `command` (any renderer) | first usable of effectcraft, html |
| mix | `assemble.sh` | `filmcraft`, `ffmpeg` (no editor), `command` (any editor or mixer) | first usable of filmcraft, ffmpeg |
| transcribe | `transcribe.sh` | `faster-whisper` (local), `openai` (any OpenAI-compatible server), `command` (any STT CLI), `file` (a transcript you have) | first usable of faster-whisper, openai |
| edit | `edit.sh` | `ffmpeg` (full: cuts, zoom, audio chain, captions, overlays...), `filmcraft` (cuts and loudness), `command` (any editor or script) | first usable of ffmpeg, filmcraft |

`bash $S/providers.sh list` shows what works here and why a missing one is missing; `which` shows what will be used; `set <kind> <name>`
remembers a choice (`--global` for all projects); `--provider` or `CRAFTVIDEO_TTS|RENDER|ASSEMBLE|TRANSCRIBE|EDIT` overrides per call. The dispatchers
**enforce the contract on every provider** (48 kHz mono voice, exact picture size/fps/frames and no audio, video+audio at the right
length; a transcript with sorted, in-range word times; an edit whose length equals its kept segments), so a provider swap cannot silently degrade the result. To use a tool the skill has never seen: set a command template
(`TTS_CMD`, `RENDER_CMD`, `ASSEMBLE_CMD`, `STT_CMD`, `EDIT_CMD`) or write a small adapter, then run `bash $S/conformance.sh <kind> <name>`.
All of it, with the contracts and recipes, is in `reference/providers.md`. Read it before adding or debugging a provider.

## House rules

1. **Only supportable claims.** Check the primary source, keep the nuance it states, label press-only facts "reported" on screen, label
   illustrative content EXAMPLE, put sources on the end card. No invented numbers or testimonials. Details: `reference/storyboard.md`.
2. **Make the music, never fetch it.** `synth_music.py` writes it. A recognisable track pulled from the web gets videos muted.
3. **Voice.** Whatever the provider, say "AI-generated voiceover" in the share copy. Clone a voice only with the speaker's permission.
   Model licences differ per engine: VoiceStudio's VoxCPM2 is Apache-2.0 (fine for client work), its OmniVoice is CC-BY-NC (personal use
   only); check the licence of any engine you switch to before client work. VoiceStudio adds an invisible AudioSeal watermark; leave it on.
4. **Hosted providers upload the script.** `openai` pointed at a hosted URL, or a `command` that calls a web API, sends the text to a third
   party. Use one only when the user has said that is fine for this video, and tell them which service saw the text.
5. **Fonts and assets.** Published work uses open-licensed fonts only. Never rip proprietary or Adobe fonts for anything published.
6. **A client's project is the client's to post**; for client work the video is a draft for approval. **Never post or upload**: deliver files.
7. **One GPU engine at a time** on a 12 GB card: stop the VoiceStudio backend when done (`bash $S/voicestudio-backend stop`).
8. `dryrun` is for previews only. If a deliverable's voice came from `dryrun`, it is not done.
9. **A recording belongs to the person in it.** Edit only with their say-so; a hosted transcribe provider uploads the audio, so use one only with consent;
   never cut words so that someone seems to say something they did not (read `review.md`); captions come from the real transcript, never invented.

## Mode A: make a video from a topic

**0. Preflight and providers.** `bash $S/preflight.sh` checks the core tools, resolves a provider per stage and checks the extras for
what was chosen. Stop and say what is missing if a stage has no usable provider. If more than one is usable and nothing is configured,
tell the user what will be used; ask only when the choice matters (a hosted TTS, or a different look). Record a choice with `providers.sh set`.

**1. Inspect.** Gather the material (research for a news or explainer topic; the code or site for a product). Answer first: what is it in
one sentence, who is it for, the most surprising true thing, the one-line caption. Fetch primary sources; record each claim with link and date.

**2. Plan (brag).** Read brag's playbook if OmniSkill is installed (path in `reference/storyboard.md`), then write `brag-output/brag-plan.md`
from the template there: angle, tone (default `polished` for factual topics), storyboard table, claims table. Hook first.

**3. Script.** One sentence per line in `work/script.txt`, optional `label | sentence`. About 2.6 words per second (30 s is 75 to 80 words).
Spell numbers as they are said ("eighty-four").

**4. Narrate.**
```bash
bash $S/narrate.sh work/script.txt work/narration_raw.wav --seed 20261009 \
  --instruct "(a confident, measured male narrator in his thirties, documentary tone, clear and natural, studio quality)"
```
Add `--provider NAME` to override. Cloning: `--ref clip.wav --ref-text "exact words in the clip"` (refused by providers that cannot clone; permission
first). Another language: `--language Portuguese`. Your own recording: `CRAFTVIDEO_NARRATION_FILE=take.wav bash $S/narrate.sh ... --provider file`.
Fast preview with no model: `--provider dryrun`. With voicestudio the first call after a start spends ~90 s on one-time compilation.

**5. Tighten and get the cues.**
```bash
$PY $S/tighten_voice.py --raw work/narration_raw.wav --script work/script.txt --out work/narration.wav --timeline work/timeline.json --target 30
```
Cuts only inside pauses (no time-stretch), finds each sentence start, writes `timeline.json`. Check the printed table against the script. A
wrong break: `--breaks` (raw seconds) or `--gaps`. "Too long": shorten the script, do not speed it up.

**6. Scenes.** What a scenes file is depends on the render provider.
- `effectcraft`: write `work/scenes.jsx` with `jsx/ec_lib.jsx` (`begin`, `background`, `scanbar`, `footer`, `txt`, `rect`, `kicker`, `panel`, `chip`,
  `underscore`, `finish`); start from `examples/decomp-30s/scenes.jsx`; traps in `reference/effectcraft-scripting.md`. `begin({})` follows the render spec.
- `html`: write `work/scene.html` defining `window.craftvideo.seek(t)`; start from `examples/html-hello/scene.html`; rules in `reference/html-scenes.md`.
- `command`: whatever your renderer takes; it must honour `{width} {height} {fps} {duration}`.
Time every event from `timeline.json` (scenes follow words). Patterns that worked: slam-in hook with a trailing underscore; two-panel before/after;
count-up numbers with bars drawn to scale; progress bar with a big percentage; split panels with a quote; punchline with a held end card and sources.

**7. Review stills (do not skip).** Look at every scene AND mid-transition, fix overflow, collisions and low contrast, look again.
```bash
bash $S/render.sh work/scenes.jsx work/sheet.png --timeline work/timeline.json --stills "1.4 3.0 4.6 6.2 8.6 11.2" --sheet work/sheet.png
```
Then read the sheet image. Check the creative laws: readable ~0.3 s per word, hook strong in 2 s, no text leaving its panel, every claim supportable.

**8. Music.** Write `work/cues.json` (format in the `synth_music.py` docstring; hits on scene changes, arp density by scene, risers, count-up
ticks, chord per bar), then `$PY $S/synth_music.py --cues work/cues.json --narration work/narration.wav --out work/music.wav`.
Or bring your own music file and skip this step (it will not be ducked under the voice unless you duck it).

**9. Render and assemble.**
```bash
bash $S/render.sh work/scenes.jsx work/silent.mp4 --timeline work/timeline.json --width 1920 --height 1080 --fps 30   # duration = timeline total
bash $S/assemble.sh --video work/silent.mp4 --voice work/narration.wav --music work/music.wav --out work/final.mp4
```
Music sits at -9 dB, mix normalised to -16 LUFS. Hand-off to another editor: add `--provider filmcraft --interchange otio --interchange-out work/edit.otio`
(formats edl, xml, fcpxml, otio, aaf, omf); media is referenced by absolute path.

**10. Finish and QA.** `bash $S/finish.sh work/final.mp4 brag-output --poster-time 1.6 --voice work/narration.wav` bakes the poster into frame 0
(`brag.jpg`, `brag.mp4`) and gates loudness (-16 +/- 1 LUFS), peak (<= -1 dBFS), narration sync (<= 40 ms) and poster-equals-frame-0.
The gates are provider-independent. A FAIL means fix and re-run, not ship.

**11. Deliver.** Write `brag-output/share-copy.txt` (1 to 3 sentences, specific, postable as-is, includes the AI-voiceover disclosure; never
"excited to share"). Fill the delivery checks in `brag-plan.md`, naming the providers used. Stop the VoiceStudio backend if it ran. Send
`brag.mp4` (SendUserFile), say where everything is, one sentence on the creative angle, offer a re-roll, another tone or a vertical version.
Say plainly what you could not verify (you cannot hear or watch the result).

## Mode B: edit a recording

Full playbook, `edit.json` schema, style presets, traps and measured results: `reference/edit.md`. In short:

```bash
mkdir -p edit-output
$PY $S/analyze.py rec.mp4 edit-output/analysis.json
bash $S/transcribe.sh rec.mp4 edit-output/transcript.json --language en          # needed for fillers and captions
$PY $S/plan_edit.py --source rec.mp4 --analysis edit-output/analysis.json --transcript edit-output/transcript.json --out edit-output/edit.json --style talking-head
bash $S/edit.sh edit-output/edit.json edit-output/edited.mp4 --transcript edit-output/transcript.json     # + --interchange otio --interchange-out FILE for another editor
$PY $S/qa_edit.py edit-output/edit.json edit-output/edited.mp4 --srt edit-output/edited.srt
$PY $S/review_edit.py edit-output/edit.json edit-output/edited.mp4 edit-output/review --transcript edit-output/transcript.json
```

1. Pick the style from what the recording is (`talking-head`, `screen`, `podcast`, `raw`). Ask only if it is unclear; say what you chose.
2. **Read `edit.json` before applying it**: `stats.filler_cuts` is every word it will cut, `segments` is what stays. Adjust the JSON, not the script.
3. After the edit, **read `review/review.md`** (the words removed at every cut) and **look at `review/cuts.jpg`** (before and after each cut). Fix and
   re-apply until nothing real was cut and no cut jumps oddly. `qa_edit.py` must pass: a FAIL means fix, not ship.
4. Deliver `edited.mp4` and the `.srt`; say which provider cut it and what that provider does not do. You cannot watch or hear it: say so.

## Motion graphics and 3D (both modes)

Everything renders through the `html` provider (`render.sh ... --provider html`), so it needs a scene that defines `window.craftvideo.seek(t)` as a
**pure function of t**. Details, the traps found, speeds and what was proven: `reference/motion-graphics.md`. Choose by the shot:

| The shot | Use | Example |
|---|---|---|
| 3D object, camera, particles, bloom | Three.js (`bash $S/get_three.sh <path-to-three>` once; render with `--gpu auto` for speed) | `examples/three-3d/` |
| a 3D model from a photo | img2threejs builds it (heavy: say 80k to 180k tokens first), `bundle.sh` bundles it, a scene plays it | `examples/img2threejs-bridge/` |
| shader or generative background | WebGPU/WGSL, or a WebGL fragment shader | `examples/webgpu-shader/` |
| kinetic type, UI motion, counters, SVG drawing | GSAP on a paused timeline, or CSS/WAAPI | `examples/gsap-timeline/` |
| lower third or sting over footage | `render.sh ... out.mov --alpha 1`, then an `overlays` clip in `edit.json` | `examples/overlay-lowerthird/` |

Review motion-graphics stills before the full render (`--stills`), keep lower thirds above the bottom 20% when captions are on, and render a whole
video on one backend (GPU or software, not both). The renderer warns if a scene is not deterministic: treat that warning as a failed render.

## Quality gates (all must hold)

Mode A: frames = fps x seconds · LUFS -16 +/- 1, peak <= -1 dBFS · sync 0 to 40 ms · poster is frame 0 · every claim in the claims table · sources on the
end card · no text outside its panel in any still · nothing invented that is not labelled EXAMPLE · the voice is not `dryrun` · hosted providers only with consent.
Mode B: `qa_edit.py` passes (length, size, fps, LUFS, true peak, A/V skew, caption sidecar) · `review.md` read and no real words lost · cuts looked at · no `WARNING` from the renderer.

## If something breaks

| Symptom | Likely cause and fix |
|---|---|
| `provider 'X' is not usable: ...` | the reason is printed; `providers.sh list`; install it, set its env var, or `providers.sh set` another |
| `provider 'X' broke the picture contract: ...` | the exact mismatch (size, fps, frames) is printed: fix the scenes or the provider's size/rate handling |
| `tighten_voice cannot find the sentence breaks` | the voice runs sentences together: call the engine per sentence with a fixed gap (what `openai` does), or pass `--breaks` |
| voicestudio `HTTP 503` | another engine holds VRAM: `voicestudio-backend stop`, start again, retry; close ComfyUI or games |
| narration "too long" | shorten the script (2.6 words/s); or `--speed 1.05` when narrating; never time-stretch afterwards |
| multi-line text on one line, wrong alignment, odd fonts (effectcraft) | `reference/effectcraft-scripting.md` (`\n`, justification, PostScript names) |
| HTML scene never starts or animates on its own clock | `reference/html-scenes.md` (`seek(t)` contract, take over CSS animations with `getAnimations()`) |
| FilmCraft "no sequence is open" | the headless engine starts empty: use `assemble.sh`, which builds the sequence in the same run |
| `voxcpm` import fails after a VoiceStudio re-setup | `uv pip install --python $VOICESTUDIO_DIR/.venv/bin/python "voxcpm>=2.0.3"` (setup removes it) |
| a word is missing from the captions, or `captions: warning: N word(s) fall in removed spans` | the transcript's times were off; `transcribe.sh` snaps them to the voice, so re-run it on the same file; check `review.md` |
| the edit is shorter than `edit.json` says, or `edit.sh` refuses the output | the contract check names the mismatch (length, size, fps, audio); a provider ignoring part of the EDL is named in a warning |
| `ffmpeg: Unrecognized option 'filter_complex_script'` | ffmpeg 9 removed it; the bundled provider already passes the graph inline, so update the skill |
| a Three.js frame differs from the preview, or `WARNING: the frame at t=0 came out different` | the scene depends on history; use `scene.background`, no clocks, seeded random (`reference/motion-graphics.md`) |
| `no WebGPU adapter` or a white WebGPU frame | request the adapter with `powerPreference` and fall back to `forceFallbackAdapter`; read back to a 2D canvas instead of presenting (`examples/webgpu-shader/`) |
| `scene: 404 /__cv/three/...` | three.js is not installed: `bash $S/get_three.sh <path-to-three>` |
| new MCP tools not visible | servers registered mid-session load only in a new chat; the scripts use CLIs and REST, same engines |

When the `effectcraft`, `filmcraft` or `voicestudio` MCP tools are available in the session they can replace the CLI calls (same commands,
same engines); the scripts remain the reproducible path.
