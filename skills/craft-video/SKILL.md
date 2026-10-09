---
name: craft-video
description: "Make a short narrated motion-graphics video (15 to 60 s, 16:9, 9:16 or 1:1) end to end with brag's hook, reveal, highlights, punchline storyboard, then whatever TTS, renderer and editor are available: VoiceStudio or any OpenAI-compatible or command-line TTS; EffectCraft, HTML/CSS in headless Chromium, or any renderer; FilmCraft, plain ffmpeg, or any editor. Generated soundtrack, loudness-normalised mp4, baked poster, measured QA gates, optional timeline hand-off (OTIO, FCPXML, EDL, AAF) to Resolve, Premiere, Final Cut or Kdenlive. Use when the user asks for a video, explainer, announcement or launch clip, social video, a 'brag' video, or 'make a video about X' and the picture can be graphics, text, numbers and diagrams rather than filmed footage. Not for cutting existing footage, or anything that needs real footage, photos of people, or avatars."
---

# craft-video

Narration-first video: the script is spoken first, then every on-screen event is placed on a spoken cue. The tools are **providers**
behind three **contracts** (voice, picture, mix), so the same workflow runs on whatever is installed and a new tool is one small adapter.

```
research -> storyboard (brag) -> script -> narrate -> tighten (timeline.json) -> scenes -> review stills
                                                             \-> music cues -> synth -> assemble -> finish + QA -> deliver
              narrate.sh = tts provider · render.sh = render provider · assemble.sh = assemble provider
```

`S="${CLAUDE_SKILL_DIR}/scripts"` below. Work in `./brag-output/work/` (brag's layout; deliverables go in `./brag-output/`).
`PY="${VIDEO_PY:-${VOICESTUDIO_DIR:-/mnt/ai/VoiceStudio}/.venv/bin/python}"` (any python with numpy, soundfile, PIL works).
Worked examples with every input file: `examples/decomp-30s/` (EffectCraft + VoiceStudio + FilmCraft), `examples/html-hello/` (HTML scene).

## Adapting to the tools that exist

| Stage | Dispatcher | Bundled providers | Falls back to |
|---|---|---|---|
| voice | `narrate.sh` | `voicestudio`, `openai` (any OpenAI-compatible server), `command` (any CLI), `file` (your recording), `dryrun` (placeholder) | first usable of voicestudio, openai |
| picture | `render.sh` | `effectcraft` (.jsx), `html` (.html), `command` (any renderer) | first usable of effectcraft, html |
| mix | `assemble.sh` | `filmcraft`, `ffmpeg` (no editor), `command` (any editor or mixer) | first usable of filmcraft, ffmpeg |

`bash $S/providers.sh list` shows what works here and why a missing one is missing; `which` shows what will be used; `set <kind> <name>`
remembers a choice (`--global` for all projects); `--provider` or `CRAFTVIDEO_TTS|RENDER|ASSEMBLE` overrides per call. The dispatchers
**enforce the contract on every provider** (48 kHz mono voice, exact picture size/fps/frames and no audio, video+audio at the right
length), so a provider swap cannot silently degrade the result. To use a tool the skill has never seen: set a command template
(`TTS_CMD`, `RENDER_CMD`, `ASSEMBLE_CMD`) or write a small adapter, then run `bash $S/conformance.sh <kind> <name>`.
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

## Workflow

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

## Quality gates (all must hold)

Frames = fps x seconds · LUFS -16 +/- 1, peak <= -1 dBFS · sync 0 to 40 ms · poster is frame 0 · every claim in the claims table · sources on the
end card · no text outside its panel in any still · nothing invented that is not labelled EXAMPLE · the voice is not `dryrun` · hosted providers only with consent.

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
| new MCP tools not visible | servers registered mid-session load only in a new chat; the scripts use CLIs and REST, same engines |

When the `effectcraft`, `filmcraft` or `voicestudio` MCP tools are available in the session they can replace the CLI calls (same commands,
same engines); the scripts remain the reproducible path.
