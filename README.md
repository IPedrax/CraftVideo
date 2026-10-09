<div align="center">
  <img src="assets/icons/clapperboard.svg" width="56" alt="" />
  <h1>CraftVideo</h1>
  <p><strong>Narrated motion-graphics video from a topic, made on your own machine: research, storyboard, voice, animation, music, mix and export, with measured quality gates. brag's storyboard method, then whatever TTS, renderer and editor you have, behind contracts that make each one swappable.</strong></p>
</div>

Most AI video tools generate pixels and hope. **CraftVideo** is the pipeline around them: the part that decides what is true, what is said, when each thing appears on screen, and whether the file that comes out is actually good. It records the narration first and times every on-screen event to a spoken cue, writes only claims it can source, builds the picture by script so any scene can be re-rolled, makes its own music, and refuses to call a video finished until loudness, peak level, sync and the poster frame have all been measured.

It does not care which tools do the work. Voice, picture and mix are three **stages**, each with a written contract and swappable **providers**: VoiceStudio or any OpenAI-compatible or command-line TTS; EffectCraft, HTML/CSS in headless Chromium, or any renderer; FilmCraft, plain ffmpeg, or any editor. The dispatchers check every provider's output against its contract, so swapping a tool cannot quietly degrade the result, and a tool the skill has never seen is a ten-line adapter or a command template.

The storyboard method is [brag's](https://github.com/latent-spaces/brag): a hook, a reveal, a few sharp highlights and a punchline, under creative laws about readability and specificity. The render pipeline runs locally; only the research step touches the web.

Built for **Claude Code**. Developed and tested on Linux with an NVIDIA GPU (see [Requirements](#requirements)).

---

## <img src="assets/icons/check.svg" width="20" align="absmiddle" alt="" /> Three rules that govern everything

1. **Scenes follow words.** The narration is generated first. `tighten_voice.py` finds where each sentence starts, and every count-up, panel and cut is placed on that cue, not the other way round. Cuts happen only inside pauses, so the speech is never time-stretched.
2. **Only supportable claims.** Each fact is checked at its primary source, the nuance the source states is kept, press-only claims are labelled "reported" on screen, illustrative content is labelled EXAMPLE, and the sources go on the end card. No invented numbers, no invented quotes.
3. **Nothing ships unmeasured.** The finish step gates on loudness (-16 +/- 1 LUFS), true peak, narration sync and the baked poster frame, independently of which tools made the file. A failing gate means fix and re-run.

---

## <img src="assets/icons/layers.svg" width="20" align="absmiddle" alt="" /> The pipeline

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

---

## <img src="assets/icons/settings.svg" width="20" align="absmiddle" alt="" /> Providers: the tools are swappable

Each stage has a contract ([`providers.md`](skills/craft-video/reference/providers.md)) and the dispatcher enforces it on whatever a provider returns.

| Stage | Contract (what must come out) | Bundled providers |
|---|---|---|
| **voice** `narrate.sh` | speech with audible pauses between sentences; normalised to 48 kHz mono | `voicestudio` (VoxCPM2: design, cloning, 30 languages) · `openai` (any OpenAI-compatible server) · `command` (any CLI) · `file` (your recording) · `dryrun` (placeholder) |
| **picture** `render.sh` | silent H.264 mp4 of the exact size, fps and frame count; audio is stripped | `effectcraft` (scripted compositions) · `html` (anything a browser draws) · `command` (any renderer) |
| **mix** `assemble.sh` | mp4 with video and audio, picture length unchanged, loudness near target | `filmcraft` (also writes editor timelines) · `ffmpeg` (no editor needed) · `command` (any editor or mixer) |

```bash
bash scripts/providers.sh list               # every provider, usable here or not, and exactly why
bash scripts/providers.sh set render html    # remember a choice (project, or --global)
bash scripts/conformance.sh all              # prove each usable provider honours its contract
```

Choice order: `--provider`, `CRAFTVIDEO_TTS` / `_RENDER` / `_ASSEMBLE`, `./craftvideo.json`, `~/.config/craftvideo/config.json`, then the first usable provider. `dryrun`, `file` and `command` are never auto-selected, so a fake voice or an unintended command can't slip in silently.

**Adding a tool:** set a template (`TTS_CMD`, `RENDER_CMD`, `ASSEMBLE_CMD`) or copy a provider and implement `--info`, `--check` and the work. `conformance.sh` then fails with the exact mismatch (size, frames, silence, missing pauses). Recipes for Piper, espeak-ng, edge-tts, Kokoro-FastAPI, Speaches, hosted APIs, Remotion, Manim, Blender, Resolve and Kdenlive are in the reference, labelled by whether they were actually run.

---

## <img src="assets/icons/sparkles.svg" width="20" align="absmiddle" alt="" /> What it does

- **Researches before it writes.** It fetches the primary source (the author's own post, the project tracker), records each claim with a link and date, and keeps the nuance. The first video's source said AI helped "at least partially", so the video says AI helped, but so did experts and tooling.
- **Plans with brag's storyboard.** Hook first, then a reveal, two or three sharp highlights, a punchline. Every line the viewer must read stays settled for about 0.3 s per word.
- **Times everything to the voice.** Count-ups land as the number is spoken; panels arrive 0.1 to 0.3 s before the sentence they illustrate.
- **Reviews its own frames.** It renders a contact sheet for every scene and mid-transition, looks at it, fixes overflow and collisions, and looks again before the full render.
- **Makes the music.** A generated score in a real key (pad, sub, arpeggio that thickens with each scene, boom hits on scene changes, a riser into the punchline, quiet ticks under count-ups), ducked under the voice. Nothing is fetched, so nothing gets muted.
- **Adapts to the tools it finds.** It checks what is installed, uses the best usable provider per stage, tells you what it chose, and falls back instead of failing when something is missing.
- **Hands off to a real editor.** FilmCraft can write the edited timeline as OpenTimelineIO, FCPXML, FCP7 XML, EDL, AAF or OMF.
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
| Overlays with transparency (ProRes 4444, WebM alpha), Lottie, GIF, EXR sequences | Possible | EffectCraft export formats, not wired |
| Burned-in captions or SRT/VTT | Possible | FilmCraft export options exist, not wired |

**Mix, export and hand-off**

| What | Status | Notes |
|---|---|---|
| FilmCraft mix and export | Proven | same size to the byte as the first video's export |
| ffmpeg-only mix, no editor | Proven | two-pass loudness normalisation |
| Any editor or mixer (Resolve scripting, melt/Kdenlive, Shotcut, Blender VSE) | Built in | `ASSEMBLE_CMD`; mechanism proven, each tool is a sketch |
| Timeline hand-off (OTIO, FCPXML, FCP7 XML, EDL, AAF, OMF) | Built in | files produced and structurally checked; importing them into other editors is not tested |
| Poster in frame 0, plan with claims table, share copy | Proven | |

**Out of scope:** cutting filmed footage as the main job (use your editor or FilmCraft directly) · generated live-action or photoreal video, avatars, lip-sync, photos of real people · songs with lyrics or vocals · live or real-time output · posting anywhere (it delivers files, you publish).

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
- **Not yet tested:** a second video made from scratch by a fresh agent following only `SKILL.md`; importing the interchange files into other editors; vertical and square formats.

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
| an HTML picture | Node, Playwright and a Chromium (`PLAYWRIGHT_DIR`, `CRAFTVIDEO_CHROMIUM`) |
| the default mix | `filmcraft-cli` from the [storytold/filmcraft](https://github.com/storytold/filmcraft) release tarball, or nothing (the `ffmpeg` provider) |

---

## <img src="assets/icons/chat.svg" width="20" align="absmiddle" alt="" /> How to use it

Describe the video:

- *"make a 30 second video about the new decompilation boom"*
- *"a 20 second launch video for this project, polished tone"*
- *"make it vertical"* · *"re-roll the third scene as deadpan"* · *"use my voice sample, here is the clip and what it says"*
- *"build it with the HTML renderer and the ffmpeg mixer"* · *"give me the timeline as OTIO for Resolve"*

Or go straight in:

```
/craft-video                          asks what the video is about
/craft-video <topic>                  researches, storyboards, and builds it
```

---

## <img src="assets/icons/settings.svg" width="20" align="absmiddle" alt="" /> How it works

**Preflight → research → brag storyboard → script → narrate → tighten (cues) → scenes → review stills → music → render → assemble → finish and QA → deliver.**

`SKILL.md` is the workflow and the house rules; the scripts do the mechanical parts and the references hold what is only needed when a step goes wrong.

```
skills/craft-video/
├── SKILL.md                     workflow, house rules, quality gates, troubleshooting
├── scripts/
│   ├── narrate.sh  render.sh  assemble.sh        the three dispatchers (they enforce the contracts)
│   ├── providers/{tts,render,assemble}/*.sh      the bundled providers (voicestudio, openai, command, file, dryrun, effectcraft, html, filmcraft, ffmpeg ...)
│   ├── providers.sh  conformance.sh  preflight.sh  lib.sh
│   ├── tighten_voice.py  synth_music.py  finish.sh  qa_sync.py
│   └── build.sh  stills.sh  voicestudio-backend  (EffectCraft and VoiceStudio helpers)
├── jsx/                         EffectCraft helper library + the default brand
├── reference/                   providers.md, storyboard.md, html-scenes.md, effectcraft-scripting.md
├── fixtures/                    tiny inputs for the conformance tests
└── examples/                    decomp-30s (full video), html-hello, html-css-animation
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
