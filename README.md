<div align="center">
  <img src="assets/icons/clapperboard.svg" width="56" alt="" />
  <h1>CraftVideo</h1>
  <p><strong>Video made or edited on your own machine, with measured quality gates. <em>Make</em> a narrated motion-graphics video from a topic (brag's storyboard, then whatever TTS, renderer and editor you have), or <em>edit</em> a recording professionally: dead air and filler words out, clean levelled audio, captions, vertical reframing. 3D and motion graphics for both. Every tool sits behind a contract that makes it swappable.</strong></p>
</div>

Most AI video tools generate pixels and hope. **CraftVideo** is the pipeline around them: the part that decides what is true, what is said, when each thing appears on screen, and whether the file that comes out is actually good. It records the narration first and times every on-screen event to a spoken cue, writes only claims it can source, builds the picture by script so any scene can be re-rolled, makes its own music, and refuses to call a video finished until loudness, peak level, sync and the poster frame have all been measured.

It does not care which tools do the work. Voice, picture and mix are three **stages**, each with a written contract and swappable **providers**: VoiceStudio or any OpenAI-compatible or command-line TTS; EffectCraft, HTML/CSS in headless Chromium, or any renderer; FilmCraft, plain ffmpeg, or any editor. The dispatchers check every provider's output against its contract, so swapping a tool cannot quietly degrade the result, and a tool the skill has never seen is a ten-line adapter or a command template.

The same discipline applies to **editing**. Point it at a talking-head, screen recording or podcast and it measures the audio, finds the speech, cuts the dead air and the ums, cleans and levels the sound to a target loudness, burns in captions built from the real transcript, and writes the whole edit as a readable `edit.json` before applying it. Afterwards it reports every cut with the words that were removed and shows the frames either side, because a cut that dropped a real sentence is the one failure no measurement catches.

Both modes can use the **motion layer**: Three.js 3D scenes (with models built by [img2threejs](https://github.com/img2threejs/img2threejs)), WebGPU shaders, GSAP typography, and transparent overlays composited onto footage, rendered deterministically on the GPU or in software.

The storyboard method is [brag's](https://github.com/latent-spaces/brag): a hook, a reveal, a few sharp highlights and a punchline, under creative laws about readability and specificity. The render pipeline runs locally; only the research step touches the web.

Built for **Claude Code**. Developed and tested on Linux with an NVIDIA GPU (see [Requirements](#requirements)).

---

## <img src="assets/icons/check.svg" width="20" align="absmiddle" alt="" /> Four rules that govern everything

1. **Scenes follow words.** The narration is generated first. `tighten_voice.py` finds where each sentence starts, and every count-up, panel and cut is placed on that cue, not the other way round. Cuts happen only inside pauses, so the speech is never time-stretched.
2. **Only supportable claims.** Each fact is checked at its primary source, the nuance the source states is kept, press-only claims are labelled "reported" on screen, illustrative content is labelled EXAMPLE, and the sources go on the end card. No invented numbers, no invented quotes.
3. **Nothing ships unmeasured.** The finish step gates on loudness (-16 +/- 1 LUFS), true peak, narration sync and the baked poster frame, independently of which tools made the file. An edit is gated on length, size, fps, loudness, peak and A/V skew. A failing gate means fix and re-run.
4. **A frame is a function of time, and an edit is data.** Every scene draws the same pixels every time it is asked for the same instant (the renderer checks), and every cut lives in an `edit.json` you can read and change, with the words it removes listed in a review report.

---

## <img src="assets/icons/layers.svg" width="20" align="absmiddle" alt="" /> The pipelines

### Make a video from a topic

| Stage | What happens | Script |
|---|---|---|
| Preflight | check the core tools, resolve a provider per stage, check extras for what was chosen | [`preflight.sh`](skills/craft-video/scripts/preflight.sh) |
| Plan | primary-source research, brag storyboard, claims table | [`storyboard.md`](skills/craft-video/reference/storyboard.md) |
| Narrate | script (one sentence per line) to speech, any TTS provider, normalised to 48 kHz mono | [`narrate.sh`](skills/craft-video/scripts/narrate.sh) |
| Tighten | land on an exact length, find every sentence start, write the cues | [`tighten_voice.py`](skills/craft-video/scripts/tighten_voice.py) |
| Scenes | scripted picture timed to the cues, any render provider, exact size, fps and frame count | [`render.sh`](skills/craft-video/scripts/render.sh) |
| Review | contact sheet of stills for every scene and mid-transition, before the full render | `render.sh --stills` |
| Score | generated music that follows the scene cuts and ducks under the voice | [`synth_music.py`](skills/craft-video/scripts/synth_music.py) |
| Mix | picture + voice + music to one mp4 at the target loudness, optional editor timeline | [`assemble.sh`](skills/craft-video/scripts/assemble.sh) |
| Finish | poster baked into frame 0, then the QA gates | [`finish.sh`](skills/craft-video/scripts/finish.sh) |

### Edit a recording

| Stage | What happens | Script |
|---|---|---|
| Analyze | find speech against the recording's own noise floor; loudness, noise, black and frozen spans | [`analyze.py`](skills/craft-video/scripts/analyze.py) |
| Transcribe | word timings from any speech-to-text, snapped onto the voiced audio | [`transcribe.sh`](skills/craft-video/scripts/transcribe.sh) |
| Plan | segments, filler cuts, zoom, audio chain, captions, loudness as an `edit.json` you can read and change | [`plan_edit.py`](skills/craft-video/scripts/plan_edit.py) |
| Apply | cuts with 8 ms fades, denoise, EQ, compression, music ducking, two-pass loudness, zoom, colour, captions, overlays, chapters | [`edit.sh`](skills/craft-video/scripts/edit.sh) |
| Gate | length, size, fps, loudness, true peak, A/V skew, caption sidecar; click and black-frame warnings | [`qa_edit.py`](skills/craft-video/scripts/qa_edit.py) |
| Review | every cut with the words removed, plus the frames before and after each cut | [`review_edit.py`](skills/craft-video/scripts/review_edit.py) |
| Hand off | the cut as OpenTimelineIO or a CMX 3600 EDL for Resolve, Premiere, Final Cut, Kdenlive | `edit.sh --interchange` |

---

## <img src="assets/icons/settings.svg" width="20" align="absmiddle" alt="" /> Providers: the tools are swappable

Each stage has a contract ([`providers.md`](skills/craft-video/reference/providers.md)) and the dispatcher enforces it on whatever a provider returns. Five stages: three make a video, two cut a recording.

| Stage | Contract (what must come out) | Bundled providers |
|---|---|---|
| **voice** `narrate.sh` | speech with audible pauses between sentences; normalised to 48 kHz mono | `voicestudio` (VoxCPM2: design, cloning, 30 languages) · `openai` (any OpenAI-compatible server) · `command` (any CLI) · `file` (your recording) · `dryrun` (placeholder) |
| **picture** `render.sh` | silent H.264 mp4 of the exact size, fps and frame count; audio is stripped | `effectcraft` (scripted compositions) · `html` (anything a browser draws) · `command` (any renderer) |
| **mix** `assemble.sh` | mp4 with video and audio, picture length unchanged, loudness near target | `filmcraft` (also writes editor timelines) · `ffmpeg` (no editor needed) · `command` (any editor or mixer) |
| **transcribe** `transcribe.sh` | word timings, in order and inside the recording, from JSON, OpenAI verbose_json, faster-whisper segments, SRT or VTT | `faster-whisper` (local) · `openai` (any OpenAI-compatible server) · `command` (any STT CLI) · `file` (a transcript you have) |
| **edit** `edit.sh` | an mp4 as long as the kept segments, at the asked size and fps, with audio; unsupported EDL parts are named in a warning | `ffmpeg` (everything) · `filmcraft` (cuts and loudness) · `command` (any editor or script) |

```bash
bash scripts/providers.sh list               # every provider, usable here or not, and exactly why
bash scripts/providers.sh set render html    # remember a choice (project, or --global)
bash scripts/conformance.sh all              # prove each usable provider honours its contract
```

Choice order: `--provider`, `CRAFTVIDEO_TTS` / `_RENDER` / `_ASSEMBLE` / `_TRANSCRIBE` / `_EDIT`, `./craftvideo.json`, `~/.config/craftvideo/config.json`, then the first usable provider. `dryrun`, `file` and `command` are never auto-selected, so a fake voice or an unintended command can't slip in silently.

**Adding a tool:** set a template (`TTS_CMD`, `RENDER_CMD`, `ASSEMBLE_CMD`, `STT_CMD`, `EDIT_CMD`) or copy a provider and implement `--info`, `--check` and the work. `conformance.sh` then fails with the exact mismatch (size, frames, silence, missing pauses, a lost word, a lost sync). Recipes for Piper, espeak-ng, edge-tts, Kokoro-FastAPI, Speaches, hosted APIs, Remotion, Manim, Blender, Resolve and Kdenlive are in the reference, labelled by whether they were actually run.

---

## <img src="assets/icons/sparkles.svg" width="20" align="absmiddle" alt="" /> What it does

- **Researches before it writes.** It fetches the primary source (the author's own post, the project tracker), records each claim with a link and date, and keeps the nuance. The first video's source said AI helped "at least partially", so the video says AI helped, but so did experts and tooling.
- **Plans with brag's storyboard.** Hook first, then a reveal, two or three sharp highlights, a punchline. Every line the viewer must read stays settled for about 0.3 s per word.
- **Times everything to the voice.** Count-ups land as the number is spoken; panels arrive 0.1 to 0.3 s before the sentence they illustrate.
- **Reviews its own frames.** It renders a contact sheet for every scene and mid-transition, looks at it, fixes overflow and collisions, and looks again before the full render.
- **Makes the music.** A generated score in a real key (pad, sub, arpeggio that thickens with each scene, boom hits on scene changes, a riser into the punchline, quiet ticks under count-ups), ducked under the voice. Nothing is fetched, so nothing gets muted.
- **Adapts to the tools it finds.** It checks what is installed, uses the best usable provider per stage, tells you what it chose, and falls back instead of failing when something is missing.
- **Edits from measurements, not guesses.** Speech is found against each recording's own noise floor; cuts snap to the quietest point within 40 ms so they land in a breath; a pause is only cut when that saves at least 0.2 s, because a smaller trim buys a visible jump cut for nothing.
- **Shows its work.** `edit.json` is the edit; `review.md` lists the words removed at every cut; `cuts.jpg` shows the frames either side.
- **Lays 3D and motion graphics over anything.** Three.js, WebGPU, GSAP and CSS scenes render to frames or to transparent ProRes overlays that composite onto the footage under the captions.
- **Hands off to a real editor.** FilmCraft can write a made video's timeline as OpenTimelineIO, FCPXML, FCP7 XML, EDL, AAF or OMF; an edit can be written as OTIO or EDL.
- **Discloses and asks.** The share copy states the voiceover is AI-generated; cloning needs the speaker's permission; a hosted provider is used only when you have agreed the text may leave the machine; nothing is posted anywhere.

---

## <img src="assets/icons/globe.svg" width="20" align="absmiddle" alt="" /> What you can make

Status is honest. **Proven**: made and measured in this repo's tests. **Built in**: the code path and flags exist and the contract is tested, but no real video has exercised that exact case. **Possible**: the underlying apps can do it and the skill does not wire it up yet.

**Subjects**

| What | Status | Notes |
|---|---|---|
| Narrated explainer on a news or technical topic | Proven | the first video: facts, count-ups, bars to scale, a diagram, a quote, a sourced end card |
| Data story: a few numbers with count-ups, bars, progress | Proven | the same building blocks |
| Launch or announcement clip, release notes, one highlight per change | Built in | from copy and facts you supply; brag's own "render the product's live UI from its code or URL" is not part of this skill |
| How-it-works or tutorial overview over diagrams | Built in | |
| Stat or quote card for social, 10 to 15 s | Built in | |
| Title, intro, outro or bumper | Built in | |
| Narration over waveform visuals (audiogram) | Possible | EffectCraft has an Audio Spectrum effect |

**Formats and length**

| What | Status | Notes |
|---|---|---|
| 1920x1080 at 30 fps, 30 s | Proven | |
| Other sizes and rates (1280x720, 24 fps) and lengths from 1 to 30 s | Proven | through the render and assemble conformance tests and the all-alternative-providers run |
| 15 to 60 s | Built in | any duration flows through the dispatchers |
| Vertical 9:16 and square 1:1 | Built in | width and height are parameters; you re-lay each scene (HTML scenes in `vw`/`vh` adapt easily); no automatic reflow |
| One script in several formats | Built in | reuse the voice and music, re-lay the scenes |
| Over 60 s, or 4K | Possible | nothing caps it; untested |

**Voice**

| What | Status | Notes |
|---|---|---|
| Designed narrator from a text description, fixed seed for repeatable takes | Proven | `voicestudio` |
| Any OpenAI-compatible TTS server | Proven | against VoiceStudio's own `/v1`; Kokoro-FastAPI, Speaches, LocalAI and hosted endpoints are Built in |
| Any CLI TTS (Piper, espeak-ng, edge-tts, your script) | Built in | the template mechanism is proven with a stand-in; each engine is a recipe |
| Your own recording or a voice actor's take | Built in | `file` provider |
| Cloned narrator from a short clip (with permission) | Built in | cloning verified at VoiceStudio's API; refused by providers that cannot clone |
| Another language | Built in | `--language`; English is the proven case |
| Preview with no model | Proven | `dryrun`: the whole pipeline in about 20 s |
| Multi-speaker dialogue | Possible | two narration passes on separate tracks, not wired |

**Sound**

| What | Status | Notes |
|---|---|---|
| Generated score cued to scenes, ducked under the voice | Proven | A minor, 100 BPM |
| Other keys, tempos, chord progressions | Built in | `cues.json` (triads) |
| Your own music file; voice only; music only | Built in | |
| Sound effects beyond booms, risers and ticks | Possible | extend `synth_music.py` |

**Picture**

| What | Status | Notes |
|---|---|---|
| EffectCraft scenes (After Effects-style scripting, 306 effects, expressions, 3D) | Proven | |
| HTML, CSS, SVG, canvas, WebGL or React scenes | Proven | two example scenes, including CSS keyframes driven by `seek(t)` |
| Any other renderer (Remotion, Manim, Blender) | Built in | `RENDER_CMD`; mechanism proven with a stand-in, each tool is a sketch |
| Your brand: palette and fonts | Built in | brand file for EffectCraft, CSS for HTML |
| Photos, screenshots, screen recordings in the picture | Possible | both renderers can; no helper yet |
| Transparent overlays (ProRes 4444) | Proven | `render.sh --alpha 1` with the `html` provider; real alpha measured |
| Lottie, GIF or EXR sequences | Possible | EffectCraft export formats, not wired |
| Burned-in captions or SRT for a made video | Possible | captions for **edited recordings** are Proven (below); a made video's script could feed the same builder, not wired |

**Mix, export and hand-off**

| What | Status | Notes |
|---|---|---|
| FilmCraft mix and export | Proven | same size to the byte as the first video's export |
| ffmpeg-only mix, no editor | Proven | two-pass loudness normalisation |
| Any editor or mixer (Resolve scripting, melt/Kdenlive, Shotcut, Blender VSE) | Built in | `ASSEMBLE_CMD`; mechanism proven, each tool is a sketch |
| Timeline hand-off (OTIO, FCPXML, FCP7 XML, EDL, AAF, OMF) | Built in | files produced and structurally checked; importing them into other editors is not tested |
| Poster in frame 0, plan with claims table, share copy | Proven | |

**Editing a recording**

| What | Status | Notes |
|---|---|---|
| Cut dead air and filler words (um, uh, er, repeats) from speech | Proven | synthetic footage with ground truth, for the `ffmpeg` and `filmcraft` providers; and real speech (49.1 s to 29.4 s, the edited video re-transcribes to the same words) |
| Denoise, EQ, compress, normalise to a target loudness | Proven | speech-to-noise gap 37 to 48 dB; loudness within 0.1 LU of -16 |
| Burned-in captions (`box`, `plain`, `karaoke`), sidecar SRT | Proven | all three styles rendered and inspected; words remapped through the cuts |
| Jump-cut punch-in zoom | Proven | alternating 1.08 on talking-head |
| Reframe to 9:16 (blurred fill or centre crop) | Proven | both rendered; face-aware reframing is Possible |
| Titles, chapters, overlay clips | Proven | rendered and inspected |
| Music bed ducked under the voice | Built in | runs and passes QA; the ducking depth was not measured |
| Colour: auto-level, saturation/contrast | Proven | a `.cube` LUT is Built in |
| Stabilise shaky footage | Built in | the vidstab path runs and passes QA; no shaky footage was tested |
| Cut hand-off to another editor (OTIO, EDL) and the caption sidecar (SRT) | Proven in FilmCraft | FilmCraft's importer takes the OTIO and EDL with media linked and the cuts survive a round trip, and takes the SRT with every caption; not tried in Resolve, Premiere, Final Cut or Kdenlive |
| Recordings of tens of minutes, several speakers, noisy rooms | Possible | untested; speaker-aware cuts, multi-camera and B-roll are not part of it |

**3D and motion graphics** (either mode)

| What | Status | Notes |
|---|---|---|
| Three.js scene: procedural 3D, particles, bloom, camera keyed to narration cues | Proven | 133 ms per frame in software, 66 ms on the GPU (1280x720); frames deterministic |
| GPU-accelerated rendering | Proven | `--gpu auto` picks Vulkan or EGL, falls back to software with a message |
| WebGPU/WGSL shader backgrounds | Proven | GPU and software frames agree to 0.017/255 |
| GSAP, CSS and WAAPI timelines driven by `seek(t)` | Proven | |
| Transparent lower thirds, stings and 3D objects over footage | Proven | composited under the captions; present only between start and end; the 3D overlay renders without bloom |
| 3D models from a photo with img2threejs | Built in | the generator, bundler and scene playback are proven with a toy spec; a real reconstruction (80k to 180k tokens) was not run |
| vgpu, p5.js generative art, logo animation, interface sounds (other OmniSkill skills) | Possible | not wired or run here |
| 4K, or 3D scenes over a minute | Possible | nothing caps them; untested |

**Out of scope:** generated live-action or photoreal video, avatars, lip-sync, photos of real people · creative editing judgement (it cuts speech and silence from measurements; it does not choose shots, build a story from hours of footage or grade by eye) · songs with lyrics or vocals · live or real-time output · posting anywhere (it delivers files, you publish).

---

## <img src="assets/icons/check.svg" width="20" align="absmiddle" alt="" /> What the testing found

Built and tested against a real 30-second video, then generalised:

- **Cues.** All 8 sentence boundaries of the real narration were recovered automatically, within 12 ms of a hand-built timeline; the same step finds the breaks in the placeholder voice too.
- **Music.** The generalised synth reproduces the original soundtrack bit-exactly.
- **Picture.** The refactored library and the render dispatcher reproduce the delivered video's frames (mean pixel difference 0.02 to 0.05 out of 255).
- **Mix.** FilmCraft reproduces the original export at the identical size to the byte (14,095,482). The ffmpeg mixer needs no editor, takes about 2.4 s for 30 s of video, and landed within 0.5 LU of the target in every test (0.1 on the real video).
- **Every provider.** Each bundled provider that can run here passes `conformance.sh` (`file` was checked through `narrate.sh` with a real recording); deliberately broken adapters fail with the specific reason (wrong size, wrong frame count, silent audio, no sentence pauses, no `seek()`).
- **The adapter that taught the lesson.** The generic OpenAI adapter first sent the whole script in one request. VoiceStudio's endpoint returned run-on speech, and conformance failed on missing pauses. The adapter now synthesises per sentence with a fixed gap, which also gives exact boundaries on any server.
- **A full video with none of the original stack:** placeholder voice, an HTML scene and an ffmpeg mix, through the same dispatchers: about 20 s, every QA gate passed.
- **Editing, against ground truth.** A synthetic recording with known speech runs, two filler sounds and a marker that is on exactly while speech plays: 100% of every speech run kept, both fillers removed, picture and sound within one frame after the cuts, loudness -16.0 to -16.1 LUFS, hiss gap up from 37 to 48 dB. `conformance.sh edit` runs the same checks on any provider.
- **Editing, on real speech.** The first video's narration with 1.5 to 3 s of room tone between sentences: 49.1 s to 29.4 s, all 80 words in the captions, and re-transcribing the edited video gave exactly the original words.
- **The bug real speech found.** Whisper stretched the first word of a sentence up to 0.7 s back into the silence, so three sentence openers fell inside "removed" spans and vanished from the captions. Word times are now snapped onto the voiced audio, and captions warn about any word the cuts drop without a planned reason.
- **The Three.js bug that broke determinism.** With a composer and output pass, setting the background through the clear colour double-encoded it (`0x0a0a0b` rendered as `0x38383b`) and made the first frame differ from every later one. `scene.background` fixes it, and the renderer now seeks back to 0 after a run and warns if the frame changed. Also found: ffmpeg 9 removed `-filter_complex_script`; `acompressor`'s `makeup` is linear, not dB (it silently undid the denoise); `drawtext` mangles `%`; a bare `requestAdapter()` returns null on a hybrid-GPU machine; a headless WebGPU canvas reads back empty (render to a texture and read it back); the `sin()` hash differs between GPU and software.
- **Not yet tested:** a second video made from scratch by a fresh agent following only `SKILL.md`; importing the interchange files into other editors; vertical and square formats for made videos; long recordings; a real img2threejs reconstruction.

---

## <img src="assets/icons/download.svg" width="20" align="absmiddle" alt="" /> Install

### <img src="assets/icons/terminal.svg" width="17" align="absmiddle" alt="" /> Claude Code

```bash
claude plugin marketplace add IPedrax/CraftVideo
```

```bash
claude plugin install craftvideo@craftvideo
```

### <img src="assets/icons/monitor.svg" width="17" align="absmiddle" alt="" /> From a local clone

```bash
claude plugin marketplace add ./CraftVideo && claude plugin install craftvideo@craftvideo
```

> **Restart Claude Code after installing**, then `/craft-video` is available and the skill auto-triggers on video requests.

> **Prefer to let Claude install it?** Paste this into a new chat:
> *"Install this Claude Code plugin for me from https://github.com/IPedrax/CraftVideo and walk me through anything you need."*

### Requirements

The skill needs one usable provider per stage; `scripts/preflight.sh` reports what you have and `providers.sh list` shows every option.

| You want | You need |
|---|---|
| anything | `ffmpeg`/`ffprobe`, `python3` with numpy, soundfile and Pillow (`VIDEO_PY` points at one) |
| the default voice | [VoiceStudio](https://github.com/debpalash/VoiceStudio) built from source with VoxCPM2 (`VOICESTUDIO_DIR`), an NVIDIA GPU with about 8 GB free |
| another voice | an OpenAI-compatible TTS server (`OPENAI_BASE_URL`), or any CLI through `TTS_CMD`, or your own recording |
| the default picture | `effectcraft-cli` from the [storytold/effectcraft](https://github.com/storytold/effectcraft) release tarball |
| an HTML picture | Node, Playwright and a Chromium (`PLAYWRIGHT_DIR`, `CRAFTVIDEO_CHROMIUM`); a full system Chromium is preferred (the bundled headless shell has no WebGPU) |
| 3D scenes | three.js (`scripts/get_three.sh <path>` copies it; `CRAFTVIDEO_ALLOW_DOWNLOAD=1` fetches it); `bun` or `esbuild` to bundle TypeScript models; a Vulkan or EGL GPU is optional (`--gpu auto`) |
| img2threejs models | a checkout of [img2threejs](https://github.com/img2threejs/img2threejs) (`IMG2THREEJS_HOME`) |
| transcription | `faster-whisper` in the python `VIDEO_PY` points at, with a model already cached (or `CRAFTVIDEO_ALLOW_DOWNLOAD=1`); or an OpenAI-compatible STT server; or any STT CLI |
| editing | `ffmpeg` with `loudnorm`, `afftdn`, `sidechaincompress`, `ass` (libass) and `drawtext`; `vidstab` and `prores_ks` are optional (`preflight.sh` checks) |
| the default mix | `filmcraft-cli` from the [storytold/filmcraft](https://github.com/storytold/filmcraft) release tarball, or nothing (the `ffmpeg` provider) |

---

## <img src="assets/icons/chat.svg" width="20" align="absmiddle" alt="" /> How to use it

Describe the video:

- *"make a 30 second video about the new decompilation boom"*
- *"a 20 second launch video for this project, polished tone"*
- *"make it vertical"* · *"re-roll the third scene as deadpan"* · *"use my voice sample, here is the clip and what it says"*
- *"build it with the HTML renderer and the ffmpeg mixer"* · *"give me the timeline as OTIO for Resolve"*
- *"edit this recording: cut the dead air and ums, clean up the audio, add captions"* · *"make a vertical version with burned-in captions"*
- *"add a 3D intro"* · *"put a lower third over this clip"* · *"turn this product photo into a 3D model and spin it in the video"*

Or go straight in:

```
/craft-video                          asks what the video is about
/craft-video <topic>                  researches, storyboards, and builds it
```

---

## <img src="assets/icons/settings.svg" width="20" align="absmiddle" alt="" /> How it works

**Make:** preflight → research → brag storyboard → script → narrate → tighten (cues) → scenes → review stills → music → render → assemble → finish and QA → deliver.
**Edit:** preflight → analyze → transcribe → plan (`edit.json`) → review the plan → apply → gate → review cuts → deliver.

`SKILL.md` is the mode router, the workflows and the house rules; the scripts do the mechanical parts and the references hold what is only needed when a step goes wrong.

```
skills/craft-video/
├── SKILL.md                     mode router (make / edit / motion layer), house rules, quality gates, troubleshooting
├── scripts/
│   ├── narrate.sh  render.sh  assemble.sh        make-mode dispatchers (they enforce the contracts)
│   ├── transcribe.sh  edit.sh                    edit-mode dispatchers
│   ├── providers/{tts,render,assemble,transcribe,edit}/*.sh      the bundled providers
│   ├── analyze.py  plan_edit.py  captions.py  qa_edit.py  review_edit.py  interchange.py  transcript_norm.py     the editing core
│   ├── get_three.sh  bundle.sh                   the 3D toolchain (three.js, TypeScript bundling)
│   ├── providers.sh  conformance.sh  preflight.sh  lib.sh
│   ├── tighten_voice.py  synth_music.py  finish.sh  qa_sync.py
│   └── build.sh  stills.sh  voicestudio-backend  (EffectCraft and VoiceStudio helpers)
├── jsx/                         EffectCraft helper library + the default brand
├── reference/                   providers.md, edit.md, motion-graphics.md, storyboard.md, html-scenes.md, effectcraft-scripting.md
├── fixtures/                    tiny inputs for the conformance tests (script, real speech, synthetic footage and its ground-truth check)
└── examples/                    decomp-30s, html-hello, html-css-animation, three-3d, img2threejs-bridge, webgpu-shader, gsap-timeline, overlay-lowerthird
```

---

## <img src="assets/icons/check.svg" width="20" align="absmiddle" alt="" /> Verify

```bash
claude plugin validate .
```

```bash
bash skills/craft-video/scripts/preflight.sh && bash skills/craft-video/scripts/conformance.sh all
```

---

## <img src="assets/icons/file.svg" width="20" align="absmiddle" alt="" /> A note on what this is for

CraftVideo makes videos out of graphics, text, numbers, diagrams and a voice. It is not a way to produce footage of people or events, and it cannot hear or watch its own result: it checks frames and measurements, and a person should still play the file before it goes out. Its claim discipline is only as good as the sources it can reach, so read the claims table in the plan. Clone a voice only with the speaker's permission, say the voiceover is AI-generated, check the licence of any speech model before client work (VoiceStudio's default VoxCPM2 is Apache-2.0; its OmniVoice weights are non-commercial), and remember that a hosted TTS provider receives the script text.

---

## <img src="assets/icons/file.svg" width="20" align="absmiddle" alt="" /> License

CraftVideo is [MIT](LICENSE).

The storyboard method is from [latent-spaces/brag](https://github.com/latent-spaces/brag) (MIT), read at runtime from an OmniSkill install when present and condensed in `reference/storyboard.md`. The default brand fonts (Big Shoulders Display, IBM Plex Mono) are SIL OFL. VoiceStudio (AGPL-3.0), EffectCraft and FilmCraft (MIT or Apache-2.0) and every speech model keep their own licences and are not redistributed here.
