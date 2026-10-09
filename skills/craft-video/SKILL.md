---
name: craft-video
description: "Make a short narrated motion-graphics video (15 to 60 s, 16:9, 9:16 or 1:1) end to end with the local suite: brag's hook, reveal, highlights, punchline storyboard; VoiceStudio narration; EffectCraft scripted visuals; a generated soundtrack; FilmCraft mix and export to a loudness-normalised MP4 with a baked poster frame. Use when the user asks for a video, explainer, announcement or launch clip, social video, a 'brag' video, or 'make a video about X' and the picture can be graphics, text, numbers and diagrams rather than filmed footage. Not for cutting existing footage (use FilmCraft directly) or anything that needs real footage, photos of people, or avatars."
---

# craft-video

Narration-first video: the script is spoken first, then every on-screen event is placed on a spoken cue. Everything runs on
this machine (VoiceStudio voice, EffectCraft picture, FilmCraft mix); nothing is uploaded or fetched except research.

```
research -> storyboard (brag) -> script -> narrate -> tighten (timeline.json) -> scenes -> review stills
                                                             \-> music cues -> synth -> assemble (FilmCraft) -> finish + QA -> deliver
```

`S="${CLAUDE_SKILL_DIR}"` below. Work in `./brag-output/work/` (brag's layout; deliverables go in `./brag-output/`).
`PY="${VIDEO_PY:-/mnt/ai/VoiceStudio/.venv/bin/python}"` (numpy, soundfile, PIL live there).
A worked example with every input file is in `$S/examples/decomp-30s/`. Copy it as a starting point.

## House rules

1. **Only supportable claims.** Check the primary source (author's post, tracker, official page), keep the nuance it states,
   label press-only facts "reported" on screen, label illustrative content EXAMPLE, put sources on the end card. No invented
   numbers or testimonials, even when a tone invites a big claim. Details in `reference/storyboard.md`.
2. **Make the music, never fetch it.** `synth_music.py` writes it. A recognisable track pulled from the web gets videos muted.
3. **Voice.** VoxCPM2 (Apache-2.0 weights) is the default and is safe for client work. OmniVoice's weights are CC-BY-NC:
   personal use only. Clone a voice only with the speaker's permission. Say "AI-generated voiceover" in the share copy.
   VoiceStudio puts an invisible AudioSeal watermark on all output; leave it on unless the user asks.
4. **Fonts and assets.** Published work uses open-licensed fonts only (the brand fonts are SIL OFL). Never rip proprietary or
   Adobe fonts for anything published; font rippers are for private testing only.
5. **A client's project is the client's to post.** For client work the video is a draft for their approval.
6. **Never post or upload.** Deliver files and a one-line angle; the user publishes.
7. **One GPU engine at a time** (12 GB card): flush before narrating, stop the backend when done.

## Workflow

**0. Preflight.** `bash $S/scripts/preflight.sh`. Stop and say what is missing if anything FAILs.

**1. Inspect.** Gather the material for the topic (research for a news or explainer topic, the code or site for a product).
Answer first: what is it in one sentence, who is it for, what is the most surprising true thing, what is the one-line caption.
Fetch primary sources; record each claim with its link and date.

**2. Plan (brag).** Read brag's playbook if OmniSkill is installed (path in `reference/storyboard.md`), then write
`brag-output/brag-plan.md` from the template there: angle, tone (default `polished` for factual topics), storyboard table,
claims table. Hook first. Keep it 15 to 30 s unless asked.

**3. Script.** One sentence per line in `work/script.txt`, optional `label | sentence`. About 2.6 words per second: count words
(30 s is 75 to 80). Sentences meant to land together share a line. Spell numbers as they are said ("eighty-four").

**4. Narrate.**
```bash
bash $S/scripts/narrate.sh work/script.txt work/narration_raw.wav --seed 20261009 \
  --instruct "(a confident, measured male narrator in his thirties, documentary tone, clear and natural, studio quality)"
```
First call after a backend start spends ~90 s on one-time compilation. Keep the seed for repeatable takes; change it for a new
take. Cloning instead of designing: add `--ref clip.wav --ref-text "exact words in the clip"` (only with permission).

**5. Tighten and get the cues.**
```bash
$PY $S/scripts/tighten_voice.py --raw work/narration_raw.wav --script work/script.txt --out work/narration.wav \
  --timeline work/timeline.json --target 30
```
Cuts only inside pauses (no time-stretch), finds each sentence start, writes `timeline.json`. Check the printed table: each
sentence should start where you expect. If a break is wrong, pass `--breaks` (raw seconds) or use `--gaps`. If it says the
narration is too long, shorten the script, do not speed it up.

**6. Scenes.** Write `work/scenes.jsx` with the library (`jsx/ec_lib.jsx`: `begin`, `background`, `scanbar`, `footer`, `txt`,
`rect`, `kicker`, `panel`, `chip`, `underscore`, `finish`). Start from `examples/decomp-30s/scenes.jsx`. Time every event from
`timeline.json`. Patterns that worked: slam-in hook with the trailing underscore; two-panel "before and after" diagram;
count-up numbers with bars drawn to scale; progress bar with a big percentage; split panels with a quote; punchline with a
held end card and sources. Different look: pass `--brand mybrand.jsx` (copy `jsx/brand-ipedrax.jsx`).
```bash
bash $S/scripts/build.sh work/scenes.jsx work/video.ecproj
```
Scripting traps (line breaks, justification, fonts, keyframes) are in `reference/effectcraft-scripting.md`; read it before debugging.

**7. Review stills (do not skip).** Look at every scene AND mid-transition, fix overflow, collisions and low contrast, then look again.
```bash
bash $S/scripts/stills.sh work/video.ecproj Main "1.4 3.0 4.6 6.2 8.6 11.2 13.8 16.4" work/sheet.png 3
```
Then read the sheet image. Check against the creative laws: readable for ~0.3 s per word, hook strong in the first 2 s, no text leaving
its panel, every claim supportable.

**8. Music.** Write `work/cues.json` (format in the `synth_music.py` docstring: hits on scene changes, arp density by scene,
risers, count-up ticks, chord progression one triad per bar) from the scene cuts, then:
```bash
$PY $S/scripts/synth_music.py --cues work/cues.json --narration work/narration.wav --out work/music.wav
```

**9. Render and assemble.**
```bash
effectcraft-cli render --comp Main --out work/silent.mp4 --format h264 --bitrate 30000 --audio off work/video.ecproj
bash $S/scripts/assemble.sh --video work/silent.mp4 --voice work/narration.wav --music work/music.wav --out work/final.mp4
```
(1080p30 renders in about 40 s; FilmCraft exports in about 25 s.) Music sits at -9 dB, mix normalised to -16 LUFS.

**10. Finish and QA.**
```bash
bash $S/scripts/finish.sh work/final.mp4 brag-output --poster-time 1.6 --voice work/narration.wav
```
Bakes the poster into frame 0 (`brag.jpg`, `brag.mp4`) and gates loudness (-16 +/- 1 LUFS), peak (<= -1 dBFS), narration sync
(<= 40 ms) and poster-equals-frame-0. A FAIL means fix and re-run, not ship.

**11. Deliver.** Write `brag-output/share-copy.txt` (1 to 3 sentences, specific, postable as-is, includes the AI-voiceover
disclosure; never "excited to share"). Fill the delivery checks in `brag-plan.md`. `voicestudio-backend stop`. Send `brag.mp4`
to the user (SendUserFile), say where everything is, one sentence on the creative angle, and offer to re-roll a scene, try
another tone or make a vertical version. Say plainly what you could not verify (you cannot hear or watch the result).

## Quality gates (all must hold)

Duration exact (frames = fps x seconds) · LUFS -16 +/- 1, peak <= -1 dBFS · sync 0 to 40 ms · poster is frame 0 · every claim in
the claims table · sources on the end card · no text outside its panel in any still · no invented content that is not labelled EXAMPLE.

## If something breaks

| Symptom | Likely cause and fix |
|---|---|
| `generate failed (HTTP 503)` | another engine holds VRAM: `voicestudio-backend stop`, start again, retry; close ComfyUI or games |
| narration "too long" | shorten the script (2.6 words/s), or `--speed 1.05` when narrating; never time-stretch afterwards |
| tighten picks a wrong break | pass `--breaks` with raw-time seconds from `ffmpeg -af silencedetect` |
| multi-line text on one line, wrong alignment, odd fonts | `reference/effectcraft-scripting.md` (`\n`, justification, PostScript names) |
| FilmCraft says "no sequence is open" | the headless engine starts empty: use `assemble.sh`, which builds the sequence in the same run |
| `voxcpm` import fails after a VoiceStudio re-setup | `uv pip install --python /mnt/ai/VoiceStudio/.venv/bin/python "voxcpm>=2.0.3"` (setup removes it) |
| new MCP tools not visible | servers registered mid-session load only in a new chat; the scripts use the CLIs and REST, same engines |

When the `effectcraft`, `filmcraft` or `voicestudio` MCP tools are available in the session they can replace the CLI calls
(same commands, same engines); the scripts remain the reproducible path.
