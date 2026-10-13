---
name: craft-video
description: "Make or edit video on your own machine. MAKE: a short narrated motion-graphics video (15 to 60 s, 16:9, 9:16 or 1:1) from a topic, with brag's hook, reveal, highlights, punchline storyboard, then whatever TTS, renderer and editor are available (VoiceStudio or any OpenAI-compatible or command-line TTS; EffectCraft, HTML/CSS/Three.js/WebGPU in headless Chromium, or any renderer; FilmCraft, ffmpeg, or any editor), a generated soundtrack and measured QA gates. EDIT: take a recording (talking head, screen capture with narration, podcast) and cut it professionally: dead air and filler words out, audio denoised and levelled to -16 LUFS, jump-cut zooms, burned-in or sidecar captions, reframing to vertical, titles, music with ducking, chapters, OTIO or EDL hand-off to Resolve, Premiere, Final Cut or Kdenlive. Both modes can add 3D and motion graphics: Three.js scenes, img2threejs models, shaders, GSAP, a hand-painted mascot (Clawd), and transparent overlays composited onto the footage. Use when the user asks for a video, explainer, announcement or launch clip, social video (a Reel, Short or TikTok, 9:16), a 'brag' video, 'make a video about X'; or to edit, cut, clean up, caption, tighten or professionalise a recording, remove ums and silences, make a video look more professional; or for 3D or motion graphics in a video, or a drawn mascot (Clawd, the Claude Code mascot) on a video where it fits. Not for generated live-action footage, talking-head avatars, lip-sync, or photoreal people."
---

# craft-video

Two modes on one set of swappable tools. **Make** is narration-first: the script is spoken first, then every on-screen event is placed on a
spoken cue. **Edit** takes a recording and cuts, cleans, captions and levels it from measurements. The tools are **providers** behind
**contracts** (voice, picture, mix; transcribe, edit), so the same workflow runs on whatever is installed and a new tool is one small adapter.

| The user wants | Mode | Start at |
|---|---|---|
| a video from a topic, product or news item (the picture is graphics, text, numbers, 3D) | **A: make** | "Mode A" below |
| a Reel, Short or TikTok (vertical, for social) | **A: make**, with the short-form numbers | `reference/short-form.md`, then "Mode A" |
| an existing recording cut, cleaned up, captioned, levelled, reframed, or made to look professional | **B: edit** | "Mode B" below, then `reference/edit.md` |
| 3D, shaders, kinetic type, lower thirds or other motion graphics in either | **C: motion layer** | "Motion graphics and 3D" below, then `reference/motion-graphics.md` |
| a mascot on the video: Clawd, hand-painted, reacting to the narration | **C: motion layer** | `reference/mascot.md` (it says when a mascot fits and when it does not) |

Both can combine: edit a recording, then lay rendered 3D or motion-graphics overlays on it; or make a video whose picture is a Three.js scene.

```
research -> storyboard (brag) -> script -> narrate -> tighten (timeline.json) -> scenes -> review stills
                                                             \-> music cues -> synth -> assemble -> finish + QA -> deliver
              narrate.sh = tts provider · render.sh = render provider · assemble.sh = assemble provider
```

`S="${CLAUDE_SKILL_DIR}/scripts"` below. Everything for one video lives in **one folder named after its title**, `./<title-slug>/` (for example `./ai-is-taking-games-apart/`):
deliverables in it, working files in its `work/`. Choose the title in step 2, then `mkdir -p <title-slug>/work && cd <title-slug>` and run every command below from
inside that folder. There is no shared output folder.
`PY="${VIDEO_PY:-${VOICESTUDIO_DIR:-/mnt/ai/VoiceStudio}/.venv/bin/python}"` (any python with numpy, soundfile, PIL works).
Worked examples with every input file: `examples/decomp-30s/` (EffectCraft + VoiceStudio + FilmCraft), `examples/html-hello/` (HTML scene), and for the
motion layer `three-3d`, `img2threejs-bridge`, `webgpu-shader`, `gsap-timeline`, `overlay-lowerthird`, `mascot` (see `examples/README.md`).

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
9. **Name deliverables after the video.** A real title, in the file name and in the file's metadata: never `brag.mp4`, `final.mp4` or `edited.mp4`. One folder
   per video, named after its title: never a shared `brag-output/` or `output/` folder.
10. **A recording belongs to the person in it.** Edit only with their say-so; a hosted transcribe provider uploads the audio, so use one only with consent;
   never cut words so that someone seems to say something they did not (read `review.md`); captions come from the real transcript, never invented.
11. **A mascot is someone's character.** Clawd is Anthropic's: use it in videos about Claude and its world, never to suggest an endorsement, and leave it out of serious subjects and of
   anything the user did not ask for and the topic does not call for (`reference/mascot.md`). Its drawing code is MIT (John Heibel) and is installed, not stored here.

## Mode A: make a video from a topic

**0. Preflight and providers.** `bash $S/preflight.sh` checks the core tools, resolves a provider per stage and checks the extras for
what was chosen. Stop and say what is missing if a stage has no usable provider. If more than one is usable and nothing is configured,
tell the user what will be used; ask only when the choice matters (a hosted TTS, or a different look). Record a choice with `providers.sh set`.

**1. Inspect.** Gather the material (research for a news or explainer topic; the code or site for a product). Answer first: what is it in
one sentence, who is it for, the most surprising true thing, the one-line caption. Fetch primary sources; record each claim with link and date.

**2. Plan (brag) and title.** Choose the video's **title** now: what a viewer would call it, 3 to 8 words in title case, never "brag", "final" or "video".
It names the folder and the files. Read brag's playbook if OmniSkill is installed (path in `reference/storyboard.md`), then write `plan.md` in the
video's folder from the template there: angle, tone (default `polished` for factual topics), storyboard table, claims table. Hook first. Each storyboard row says what the viewer
comes to believe ("Buys") and how much the beat matters (1 to 3, at most a quarter of them 3). If the topic is Claude, agents or developer tooling, decide here whether the
mascot gets any beats (`reference/mascot.md` says when he fits and when he does not) and keep his corner free in them.

**3. Script.** One sentence per line in `work/script.txt`, optional `label | sentence`. About 2.6 words per second (30 s is 75 to 80 words).
Spell numbers as they are said ("eighty-four").

**4. Narrate.**
```bash
bash $S/narrate.sh work/script.txt work/narration_raw.wav --seed 20261009 \
  --instruct "(a confident, measured male narrator in his thirties, documentary tone, clear and natural, studio quality)"
```
Write a name the voice may get wrong the way it should sound ("Keyside" for Quayside) and spell it correctly in the captions. Add `--provider NAME` to override. Cloning: `--ref clip.wav --ref-text "exact words in the clip"` (refused by providers that cannot clone; permission
first). Another language: `--language Portuguese`. Your own recording: `CRAFTVIDEO_NARRATION_FILE=take.wav bash $S/narrate.sh ... --provider file`.
Fast preview with no model: `--provider dryrun`. With voicestudio the first call after a start spends ~90 s on one-time compilation.

**Verify the words** before tightening: `$PY $S/verify_narration.py --audio work/narration_raw.wav --script work/script.txt --language en` transcribes the take and prints every script
line that came back different, with what was expected and what was heard ("mostly in force" came back as "enforced"). Reword or regenerate the lines it fails; a name the voice gets
wrong is respelled in the script and passed as `--ignore keyside`. Numbers are checked for presence, not value: listen to those.

**5. Tighten and get the cues.**
```bash
$PY $S/tighten_voice.py --raw work/narration_raw.wav --script work/script.txt --out work/narration.wav --timeline work/timeline.json --target 30
```
Cuts only inside pauses (no time-stretch), finds each sentence start, writes `timeline.json`. Check the printed table against the script. A
wrong break: `--breaks` (raw seconds) or `--gaps`. "Too long": shorten the script, do not speed it up.

**When the voice runs sentences together** (typical in the second half of a long script: `tighten_voice` stops with "found N inner pauses" or picks comma pauses
and the cues come out wrong), find the boundaries from word times instead, then pin them:
```bash
bash $S/transcribe.sh work/narration_raw.wav work/raw_transcript.json --language en
$PY $S/split_narration.py --raw work/narration_raw.wav --script work/script.txt --transcript work/raw_transcript.json --out work/narration_split.wav --breaks-out work/breaks.json
$PY $S/tighten_voice.py --raw work/narration_split.wav --script work/script.txt --out work/narration.wav --timeline work/timeline.json --target 87 \
  --breaks "$($PY -c 'import json; print(",".join(map(str, json.load(open("work/breaks.json")))))')" --gaps 0.3,0.3,0.7,0.3,...   # one gap per boundary
```
`split_narration.py` leaves a natural pause alone and inserts one (0.3 s by default) only where the voice had none; speech is never cut or stretched. `--gaps` takes one value
per boundary, so a scene change can get 0.7 s for its wipe. Size the length in two runs: `--target 200` to read `speech_end`, then `--target <speech_end + the end-card hold>`.
Check the printed table: each sentence's duration must fit its word count.

**6. Scenes.** What a scenes file is depends on the render provider.
- `effectcraft`: write `work/scenes.jsx` with `jsx/ec_lib.jsx` (`begin`, `background`, `scanbar`, `footer`, `txt`, `rect`, `kicker`, `panel`, `chip`,
  `underscore`, `finish`); start from `examples/decomp-30s/scenes.jsx`; traps in `reference/effectcraft-scripting.md`. `begin({})` follows the render spec.
- `html`: write `work/scene.html` defining `window.craftvideo.seek(t)`; start from `examples/html-hello/scene.html`; rules in `reference/html-scenes.md`.
  **A look**: pick one of the nine in `looks/` (`signature`, `dark-keynote`, `dataviz`, `iso-infographic`, `swiss-motion`, `whiteboard`, `blueprint`, `hologram-hud`, `ascii-crt`; the table is in
  `looks/README.md`), style the scene with its variables (`var(--cv-ink, #f2f2f0)`, `var(--cv-display-size, 9vh)`) and render with `--look NAME`. Its `motion`, `avoid` and `sound` fields are direction for the
  scenes and the music. **One camera, no cuts**: `examples/continuous-camera/` keys a single camera through every beat from `timeline.json`. **An exact word inside a sentence**: list it in `work/anchors.txt`
  and run `anchors.py` (`reference/html-scenes.md`); the scene reads `spec.timeline.moments.name.start`.
- `command`: whatever your renderer takes; it must honour `{width} {height} {fps} {duration}`.
Time every event from `timeline.json` (scenes follow words). Patterns that worked: slam-in hook with a trailing underscore; two-panel before/after;
count-up numbers with bars drawn to scale; progress bar with a big percentage; split panels with a quote; punchline with a held end card and sources.

**7. Review stills (do not skip).** Look at every scene AND mid-transition, fix overflow, collisions and low contrast, look again.
```bash
bash $S/render.sh work/scenes.jsx work/sheet.png --timeline work/timeline.json --stills "1.4 3.0 4.6 6.2 8.6 11.2" --sheet work/sheet.png
# html scenes: also audit the layout (no video; a json report; exit 1 on an error: text cut by the frame or a box, text on text; warnings: small text, caption band, contrast)
bash $S/render.sh work/scene.html work/lint.json --provider html --lint 1 --timeline work/timeline.json --width 1920 --height 1080
```
Then read the sheet image. Check the creative laws: readable ~0.3 s per word, hook strong in 2 s, no text leaving its panel, every claim supportable.

**7b. Critic pass.** Score every scene out of 10 against the rubric in `reference/visual-craft.md` (hook, hierarchy, readable, alive, sound, truth), write the scores in `plan.md`,
fix anything under 8 and re-render only those scenes. Type sizes, easing, transitions and finish are in the same file. Anything for social (Reel, Short, TikTok): read
`reference/short-form.md` first (pace, lead-in, captions, a loudness of -14).

**8. Music.** Write `work/cues.json` (format in the `synth_music.py` docstring; 1 to 3 hand-placed hits, not one per scene change; arp density by scene, risers, count-up
ticks, chord per bar; `dips` to pull the bed down while a card is read in silence), then `$PY $S/synth_music.py --cues work/cues.json --narration work/narration.wav --out work/music.wav`.
Or bring your own music file and skip this step (it will not be ducked under the voice unless you duck it).

**9. Render and assemble.**
```bash
bash $S/render.sh work/scenes.jsx work/silent.mp4 --timeline work/timeline.json --width 1920 --height 1080 --fps 30   # duration = timeline total
bash $S/assemble.sh --video work/silent.mp4 --voice work/narration.wav --music work/music.wav --out work/final.mp4
```
`render.sh` takes `--workers 4` (a DOM scene rendered about 4x faster with identical frames; software WebGL gains nothing), and for short scenes with fast type or 3D `--shutter 180 --subframes 8`
(motion blur) and `--grain 8`: `reference/motion-graphics.md`. A scene that depends on history is refused before encoding (exit 4).
With a mascot, run `bash $S/mascot.sh work/mascot.json work/mascot.mov --timeline work/timeline.json --over work/silent.mp4 --into work/silent-clawd.mp4` after the render and assemble that
picture instead (look at its `--sheet` first; `reference/mascot.md`).
Music sits at -9 dB, mix normalised to -16 LUFS. Hand-off to another editor: add `--provider filmcraft --interchange otio --interchange-out work/edit.otio`
(formats edl, xml, fcpxml, otio, aaf, omf); media is referenced by absolute path.

**10. Finish and QA.** `bash $S/finish.sh work/final.mp4 . --title "AI Is Taking Games Apart" --poster-time 1.6 --voice work/narration.wav` (run inside the
video's folder, so `.` is that folder) bakes the poster into frame 0, names the files after the title (`ai-is-taking-games-apart.mp4` and `.jpg`), writes the title into the video's metadata, and gates loudness
(-16 +/- 1 LUFS, or `--lufs -14` for a reel), peak (<= -1 dBFS), narration sync (<= 40 ms), poster-equals-frame-0, the embedded title, and the picture (`qa_frames.py`: a blank
picture FAILs; stretches where it barely changes and a long end hold print as WARN, so look at each one and keep it on purpose or add motion). `--title` is required; `--filename`
overrides only the file name. The gates are provider-independent. A FAIL means fix and re-run, not ship.

**11. Deliver.** Write `share-copy.txt` in the video's folder (1 to 3 sentences, specific, postable as-is, includes the AI-voiceover disclosure; never
"excited to share"). Fill the delivery checks in `plan.md`, naming the providers used. Stop the VoiceStudio backend if it ran. Send
the titled mp4 (SendUserFile), say where everything is, one sentence on the creative angle, offer a re-roll, another tone or a vertical version.
Say plainly what you could not verify (you cannot hear or watch the result).

## Mode B: edit a recording

Full playbook, `edit.json` schema, style presets, traps and measured results: `reference/edit.md`. In short:

```bash
D=how-the-edit-works; mkdir -p $D; V=$D/$D.mp4        # one folder per video, and the output named after the video's title, not edited.mp4
$PY $S/analyze.py rec.mp4 $D/analysis.json
bash $S/transcribe.sh rec.mp4 $D/transcript.json --language en          # needed for fillers and captions
$PY $S/plan_edit.py --source rec.mp4 --analysis $D/analysis.json --transcript $D/transcript.json --out $D/edit.json --style talking-head
bash $S/edit.sh $D/edit.json $V --title "How The Edit Works" --transcript $D/transcript.json     # + --interchange otio --interchange-out FILE
$PY $S/qa_edit.py $D/edit.json $V --srt ${V%.mp4}.srt
$PY $S/review_edit.py $D/edit.json $V $D/review --transcript $D/transcript.json
```

1. Pick the style from what the recording is (`talking-head`, `screen`, `podcast`, `raw`). Ask only if it is unclear; say what you chose.
2. **Read `edit.json` before applying it**: `stats.filler_cuts` is every word it will cut, `segments` is what stays. Adjust the JSON, not the script. If the person re-said lines until they came out right,
   run `python3 $S/find_retakes.py $D/transcript.json` for the earlier takes and false starts a later take repeats (it only lists; approve each, then remove the span from `segments`).
3. After the edit, **read `review/review.md`** (the words removed at every cut) and **look at `review/cuts.jpg`** (before and after each cut). Fix and
   re-apply until nothing real was cut and no cut jumps oddly. `qa_edit.py` must pass: a FAIL means fix, not ship.
4. Deliver the titled mp4 and its `.srt`; say which provider cut it and what that provider does not do. You cannot watch or hear it: say so.

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
| a character that reacts to the narration (Clawd, the Claude Code mascot) | `bash $S/get_mascot.sh` once, then `mascot.sh mascot.json out.mov --sheet` to review and without it to render; `--over picture.mp4 --into out.mp4` lays it over a made video | `examples/mascot/`, `reference/mascot.md` |

Review motion-graphics stills before the full render (`--stills`), keep lower thirds above the bottom 20% when captions are on, and render a whole
video on one backend (GPU or software, not both). A scene that is not deterministic is refused by the preflight (exit 4); a `WARNING` after the run means the same: treat it as a failed render.
Type sizes, colour discipline, easing and spring functions, transitions that carry something across a cut, and the critic rubric: `reference/visual-craft.md`.

## Quality gates (all must hold)

Mode A: the file is named after the title and carries it in its metadata · frames = fps x seconds · LUFS -16 +/- 1 (-14 for a reel), peak <= -1 dBFS · sync 0 to 40 ms · poster is frame 0 · layout lint without an ERROR (html scenes) · no blank picture, every
`qa_frames.py` WARN looked at · the voice read the script (`verify_narration.py`) · every claim in the claims table · sources on the
end card · no text outside its panel in any still · nothing invented that is not labelled EXAMPLE · the voice is not `dryrun` · hosted providers only with consent · a mascot only where it fits, its review sheet looked at.
Mode B: `qa_edit.py` passes (length, size, fps, LUFS, true peak, A/V skew, caption sidecar) · `review.md` read and no real words lost · cuts looked at · no `WARNING` from the renderer.

## If something breaks

| Symptom | Likely cause and fix |
|---|---|
| `provider 'X' is not usable: ...` | the reason is printed; `providers.sh list`; install it, set its env var, or `providers.sh set` another |
| `provider 'X' broke the picture contract: ...` | the exact mismatch (size, fps, frames) is printed: fix the scenes or the provider's size/rate handling |
| `mascot.sh`: "the mascot kit is not installed" | `CRAFTVIDEO_ALLOW_DOWNLOAD=1 bash $S/get_mascot.sh`, or `get_mascot.sh /path/to/ClaudeAnimationBase` after `npm install` there; every file is checked against its pinned SHA-256 |
| `tighten_voice cannot find the sentence breaks` | the voice runs sentences together: call the engine per sentence with a fixed gap (what `openai` does), or pass `--breaks` |
| voicestudio `HTTP 503` | another engine holds VRAM: `voicestudio-backend stop`, start again, retry; close ComfyUI or games |
| narration "too long" | shorten the script (2.6 words/s); or `--speed 1.05` when narrating; never time-stretch afterwards |
| multi-line text on one line, wrong alignment, odd fonts (effectcraft) | `reference/effectcraft-scripting.md` (`\n`, justification, PostScript names) |
| HTML scene never starts or animates on its own clock | `reference/html-scenes.md` (`seek(t)` contract, take over CSS animations with `getAnimations()`) |
| `html: the scene is not a pure function of t` (exit 4) | the preflight visited five times forward and backward and a frame differed: remove the history (a timer, an unseeded random, state built up per frame); `--preflight 0` skips it, and the frames then are not what you previewed |
| `html lint` reports an ERROR | `frame`/`clipped`: text cut off, resize or move it; `overlap`/`occluded`: two texts collide or a panel covers one; opt out per element with `data-cv-*` only when it is meant (`reference/motion-graphics.md`) |
| FilmCraft "no sequence is open" | the headless engine starts empty: use `assemble.sh`, which builds the sequence in the same run |
| `voxcpm` import fails after a VoiceStudio re-setup | `uv pip install --python $VOICESTUDIO_DIR/.venv/bin/python "voxcpm>=2.0.3"` (setup removes it) |
| a word is missing from the captions, or `captions: warning: N word(s) fall in removed spans` | the transcript's times were off; `transcribe.sh` snaps them to the voice, so re-run it on the same file; check `review.md` |
| the edit is shorter than `edit.json` says, or `edit.sh` refuses the output | the contract check names the mismatch (length, size, fps, audio); a provider ignoring part of the EDL is named in a warning |
| `ffmpeg: Unrecognized option 'filter_complex_script'` | ffmpeg 9 removed it; the bundled provider already passes the graph inline, so update the skill |
| a Three.js frame differs from the preview, or `WARNING: the frame at t=0 came out different` | the scene depends on history; use `scene.background`, no clocks, seeded random (`reference/motion-graphics.md`) |
| `no WebGPU adapter` or a white WebGPU frame | request the adapter with `powerPreference` and fall back to `forceFallbackAdapter`; read back to a 2D canvas instead of presenting (`examples/webgpu-shader/`) |
| `scene: 404 /__cv/three/...` | three.js is not installed: `bash $S/get_three.sh <path-to-three>` |
| `narrate.sh` finishes (the file exists) but the command never returns | the backend daemon inherited a captured pipe: run `narrate.sh` from the shell (output to a log file), not through `subprocess.run(capture_output=True)` |
| `no usable transcribe provider` or `whisper model ... is not downloaded` | no faster-whisper model is where it looks: put one in `/mnt/ai/Whisper/faster-whisper-<name>` (or set `WHISPER_DIR`), or in the Hugging Face cache, or set `WHISPER_MODEL`; `providers.sh list` names what is missing (`reference/providers.md`) |
| new MCP tools not visible | servers registered mid-session load only in a new chat; the scripts use CLIs and REST, same engines |

When the `effectcraft`, `filmcraft` or `voicestudio` MCP tools are available in the session they can replace the CLI calls (same commands,
same engines); the scripts remain the reproducible path.
