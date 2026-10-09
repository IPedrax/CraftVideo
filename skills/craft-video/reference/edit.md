# Editing a recording (mode B)

Take a recording of someone talking (a talking head, a screen capture with narration, a podcast) and cut it the way an editor would:
dead air and filler words out, audio cleaned and levelled, captions burned in, delivered at a measured loudness. The whole edit is **data**
(`edit.json`), so a person or Claude can read it, change it and re-apply it.

```
recording ──analyze.py──▶ analysis.json ──┐
          └─transcribe.sh─▶ transcript.json ─┴─plan_edit.py─▶ edit.json ──(review, adjust)──▶ edit.sh ──▶ edited.mp4 (+ .srt)
                                                                                                │
                                              qa_edit.py (gates) · review_edit.py (what was cut) ◀┘   --interchange otio|edl for another editor
```

`S="${CLAUDE_SKILL_DIR}/scripts"`, `PY="${VIDEO_PY:-${VOICESTUDIO_DIR:-/mnt/ai/VoiceStudio}/.venv/bin/python}"`. Work in `./edit-output/`.

## The steps

```bash
$PY $S/analyze.py rec.mp4 edit-output/analysis.json                          # speech vs silence, loudness, noise floor, black/frozen spans
bash $S/transcribe.sh rec.mp4 edit-output/transcript.json --language en       # word timings (optional, but needed for fillers and captions)
$PY $S/plan_edit.py --source rec.mp4 --analysis edit-output/analysis.json --transcript edit-output/transcript.json \
    --out edit-output/edit.json --style talking-head
bash $S/edit.sh edit-output/edit.json edit-output/edited.mp4 --transcript edit-output/transcript.json
$PY $S/qa_edit.py edit-output/edit.json edit-output/edited.mp4 --srt edit-output/edited.srt
$PY $S/review_edit.py edit-output/edit.json edit-output/edited.mp4 edit-output/review --transcript edit-output/transcript.json
```

1. **Analyze.** Speech is decided against *this recording's* noise floor (threshold = floor + 35% of the way to the speech level, clamped to
   -50..-30 dB, 3 dB hysteresis). A fixed dB threshold is wrong for most footage. Read the printed summary: speech share, LUFS, noise floor.
2. **Transcribe** (skip for a silent-or-music recording, or if you only want pauses cut). Words get timings. The local default is
   faster-whisper; `--provider openai` or a `command` works too. A hosted provider **uploads the audio**: only with the speaker's consent.
   The transcript step also snaps word times to the voiced audio (see *Traps*).
3. **Plan.** `--style` picks defaults; every number lands in `edit.json`. Flags override: `--keep-pause`, `--fillers um,uh,...`, `--no-fillers`,
   `--punch-in 1.08`, `--lufs`, `--denoise auto|off|N`, `--captions|--no-captions`, `--music FILE --music-db -22`, `--width/--height/--fps`,
   `--reframe none|crop|blur`, `--stabilize`.
4. **Review the plan before applying it.** Open `edit.json`: `stats.filler_cuts` lists every word it will cut, `segments` is exactly what
   stays. Drop a segment or move a boundary by editing the JSON; there is nothing hidden.
5. **Apply** with `edit.sh`. It resolves a provider, builds the captions, warns about anything the provider cannot do, runs the edit,
   then enforces the output contract (length = kept segments within 2 frames, size, fps, audio present).
6. **Gate and look.** `qa_edit.py` fails the edit on length, size, fps, loudness (EDL target +/- 1 LU), true peak above -1 dBFS, A/V length
   skew over 40 ms, and a broken caption sidecar; it warns on a click at a cut or a black stretch. `review_edit.py` writes `review.md`
   (every cut with the **words removed**) and `cuts.jpg` (the frame before and after each cut). Read both. A cut that removed real words is
   the failure that no measurement catches.

## Styles

| `--style` | keeps pauses at | zoom | captions | audio chain | colour | for |
|---|---|---|---|---|---|---|
| `talking-head` | 0.30 s | alternating 1.08 punch-in to hide jump cuts | on | voice | auto-level | a person to camera |
| `screen` | 0.55 s | none | on | voice | none | a screen recording with narration (slower pace, no jump zoom) |
| `podcast` | 0.45 s | none | off | voice | none | two people talking, picture secondary |
| `raw` | no cutting | none | off | light | none | clean audio and loudness only, keep every second |

A pause is cut down to the keep length **only if that saves at least 0.2 s**. A 70 ms trim buys a visible jump cut for nothing, so shorter
pauses stay whole. Fillers: um, umm, uh, uhh, uhm, er, erm, ah, hmm, mm, mmm, and immediate word repeats ("the the"), and only when the word
really overlaps voiced audio. "like" and "you know" are not touched: they are usually content.

## edit.json

```jsonc
{
  "version": 1,
  "source": "/abs/path/rec.mp4",
  "style": "talking-head",
  "output":   { "width": 1920, "height": 1080, "fps": 30, "lufs": -16.0, "reframe": "none" },   // reframe: none | crop | blur (blurred fill)
  "segments": [ { "in": 0.75, "out": 4.32, "zoom": 1.0 }, { "in": 6.30, "out": 7.55, "zoom": 1.08 } ],   // source seconds, back to back in the output
  "audio":    { "highpass": 80, "denoise": 12, "compress": true, "presence": true, "fade_ms": 8, "lufs": -16.0 },
  "video":    { "color": "auto", "stabilize": false, "lut": null },     // color: "none" | "auto" | {"saturation":1.2,"contrast":1.1,...}; lut: a .cube path
  "captions": { "enabled": true, "style": "box", "max_chars": 42, "burn": true, "sidecar": "srt" },   // style: box | plain | karaoke
  "music":    null,                                                      // or {"file": "...", "db": -22, "duck": true}
  "overlays": [                                                          // output-time seconds
    { "type": "title", "text": "Any text, 100% safe", "start": 9, "end": 11, "pos": "lower" },
    { "type": "clip",  "file": "/abs/lowerthird.mov", "start": 2.0, "end": 5.0, "x": 0, "y": 0, "width": 640 }   // rendered graphics, alpha works
  ],
  "chapters": [ { "at": 0, "title": "Intro" } ],                         // output seconds; written as MP4 chapters
  "stats": { "...": "filled in by the planner" }
}
```

What the audio fields do, in order: `highpass` cuts rumble below that frequency; `denoise` is `afftdn` noise reduction in dB; `presence` is a
gentle +2 dB lift at 3.2 kHz; `compress` is a 3:1 compressor from -20 dB; music (if any) is ducked under the voice by sidechain compression;
the whole mix is then normalised in **two passes** to `lufs` with a true-peak limit of -1.5 dB. Every cut gets an 8 ms fade (`fade_ms`) so
nothing clicks.

Captions are built from the transcript, **remapped through the cuts**: a word in a removed span disappears, a word cut in half is clipped.
Cues break at sentence ends, long pauses and at the cuts themselves, never overlap, and stay on screen at least 0.6 s. The same cues are
written as a sidecar `.srt` next to the output (`edited.srt`), so other editors and players can use them. Portrait output gets bigger text,
26-character lines and a margin above the app-UI zone. Place lower thirds above the bottom 20% so they do not sit under the captions.

## Providers (`edit`)

| Provider | Does | Does not | Notes |
|---|---|---|---|
| `ffmpeg` (default) | cuts, jump-cut zoom, audio chain, music ducking, loudness, colour/LUT, stabilise, reframe, burned captions, titles, overlay clips, chapters | face-aware reframing (crop is centred) | one filter graph, one x264 encode (crf 18); `vidstab` needs a second analysis pass |
| `filmcraft` | frame-accurate cuts on a real timeline, loudness-normalised export, leaves `OUT.fcproj` for hand finishing | zoom, audio chain, colour, captions, titles, music | `edit.sh` warns about each thing it skips |
| `command` | whatever `EDIT_CMD` does (`{edl} {source} {out} {ass} {chapters} {lufs} {width} {height} {fps}`) | declare `EDIT_FEATURES=zoom,audio,...` to silence the warnings | the dispatcher still checks length, size, fps and audio |

`edit.sh --interchange otio|edl --interchange-out FILE` also writes **the cut** as a timeline for another editor (OpenTimelineIO in FilmCraft's
dialect, or CMX 3600 EDL), one clip per kept segment pointing at the source recording (the EDL carries the absolute path in a `* SOURCE FILE:`
comment; a bare CMX 3600 file only has the clip name, which is why some importers ask you to relink). Zoom, the audio chain, colour and captions
are not part of either format; zoomed segments are listed in the clip metadata or an EDL comment so you can re-apply them.

## What was measured, and what was not

On synthetic footage with ground truth (speech-shaped bursts, two filler sounds, long dead air, hiss and hum, and a marker that is on exactly
while speech plays), for both the `ffmpeg` and `filmcraft` providers: 100% of every speech run kept, both fillers gone, dead air trimmed, picture
and sound within one frame of each other after the cuts, loudness -16.0 to -16.1 LUFS, no click at any cut. The `ffmpeg` provider also lifted
the speech-to-noise-floor gap from 37 dB to 48 dB. These checks are `conformance.sh edit`, so they run on any provider you add.

On real speech (the narration of the first video with 1.5 to 3 s of room tone inserted between sentences): 49.1 s became 29.4 s, all 80 words
survived into the captions, and **transcribing the edited video gave exactly the same 79 words as the original** (similarity 1.000).

The interchange files were checked against a real importer: FilmCraft takes the OTIO and the EDL with the media linked, and exporting the imported
OTIO back to EDL gives video and audio events whose source in and out equal the planned cuts, on a contiguous timeline from zero (this is part of
`conformance.sh edit` when FilmCraft is installed). The caption sidecar imports into FilmCraft with all 7 captions and no warnings. Finding: the first
version rounded the end of a cut differently in the OTIO and the EDL, one frame apart; both now round the same way.

Not tested: a long recording (tens of minutes), several speakers, noisy rooms or music under speech, variable-frame-rate phone footage beyond
what ffmpeg's `fps` filter does by default, stabilising real handheld footage (the vidstab path ran and passed QA on test footage, but there
was no shaky camera to improve), importing the OTIO/EDL files into DaVinci Resolve, Premiere, Final Cut or Kdenlive, the depth of music ducking, and the
`openai` transcribe provider and a real STT CLI against real services.

## Traps found while building it

- **Speech models place the first word of a sentence early.** On real speech faster-whisper started sentence-opening words up to 0.7 s before
  the voice, inside the silence. A cut or caption built on those times drops the word: three of 80 words vanished from the captions. The
  transcribe step now snaps word times onto the voiced audio (`transcript_norm.py --audio`, done for you by `transcribe.sh`), and captions
  warn when a word falls in a removed span that no planned cut explains. Cuts are also snapped to the quietest point within 40 ms, so they land
  in a breath even when a time is off.
- **`acompressor`'s `makeup` is a linear factor, not dB.** `makeup=3` is +9.5 dB on everything including the noise, which undid the denoise.
  The chain has no makeup stage: the final loudness pass sets the level.
- **ffmpeg 9 removed `-filter_complex_script`.** The provider passes the graph inline and falls back to `-/filter_complex FILE` (ffmpeg 7+) for
  graphs too long for one argument.
- **`drawtext` mangles `%`.** Titles go through `textfile=` with expansion off, so any text is safe.
- **Judge noise on the 3rd percentile, not the 10th.** An edit keeps few pauses, so the quietest tenth of frames is already speech.

## Rules for the person's recording

The recording is the person's. Cutting words can change what someone seems to have said: read `review.md`, keep the cut you can defend, and
do not edit a statement into a different meaning. A hosted transcribe provider receives the audio. Add captions only from the real transcript
(the skill never invents words). Deliver files, never post.
