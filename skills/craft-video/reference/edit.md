# Editing a recording (mode B)

Take a recording of someone talking (a talking head, a screen capture with narration, a podcast) and cut it the way an editor would:
dead air and filler words out, audio cleaned and levelled, captions burned in, delivered at a measured loudness. The whole edit is **data**
(`edit.json`), so a person or Claude can read it, change it and re-apply it.

```
recording ──analyze.py──▶ analysis.json ──┐
          └─transcribe.sh─▶ transcript.json ─┴─plan_edit.py─▶ edit.json ──(review, adjust)──▶ edit.sh ──▶ the titled mp4 (+ .srt)
                                                                                                │
                                              qa_edit.py (gates) · review_edit.py (what was cut) ◀┘   --interchange otio|edl for another editor
```

`S="${CLAUDE_SKILL_DIR}/scripts"`, `PY="${VIDEO_PY:-${VOICESTUDIO_DIR:-/mnt/ai/VoiceStudio}/.venv/bin/python}"`. Work in one folder named after the video, `./<title-slug>/` (here `D=how-the-edit-works; mkdir -p $D`).

## The steps

```bash
$PY $S/analyze.py rec.mp4 $D/analysis.json                          # speech vs silence, loudness, noise floor, black/frozen spans
bash $S/transcribe.sh rec.mp4 $D/transcript.json --language en       # word timings (optional, but needed for fillers and captions)
$PY $S/plan_edit.py --source rec.mp4 --analysis $D/analysis.json --transcript $D/transcript.json \
    --out $D/edit.json --style talking-head
V=$D/$D.mp4          # name the output after the video's title
bash $S/edit.sh $D/edit.json $V --title "How The Edit Works" --transcript $D/transcript.json
$PY $S/qa_edit.py $D/edit.json $V --srt ${V%.mp4}.srt
$PY $S/review_edit.py $D/edit.json $V $D/review --transcript $D/transcript.json
```

1. **Analyze.** Speech is decided against *this recording's* noise floor (threshold = floor + 35% of the way to the speech level, clamped to
   -50..-30 dB, 3 dB hysteresis). A fixed dB threshold is wrong for most footage. Read the printed summary: speech share, LUFS, noise floor.
2. **Transcribe** (skip for a silent-or-music recording, or if you only want pauses cut). Words get timings. The local default is
   faster-whisper; `--provider openai` or a `command` works too. A hosted provider **uploads the audio**: only with the speaker's consent.
   The transcript step also snaps word times to the voiced audio (see *Traps*).
3. **Plan.** `--style` picks defaults; every number lands in `edit.json`. Flags override: `--keep-pause`, `--fillers um,uh,...`, `--no-fillers`,
   `--punch-in 1.08`, `--lufs`, `--denoise auto|off|N`, `--captions|--no-captions`, `--music FILE --music-db -22`, `--width/--height/--fps`,
   `--reframe none|crop|blur|face` (`face` also takes `--face-track FILE`, see *Following the speaker's face*), `--range S-E` (plan only that span of a long recording, one clip of it:
   `reference/clips.md`), `--stabilize`.
4. **Review the plan before applying it.** Open `edit.json`: `stats.filler_cuts` lists every word it will cut, `segments` is exactly what
   stays. Drop a segment or move a boundary by editing the JSON; there is nothing hidden. For a recording where the person re-said lines until they came out right, run
   `python3 $S/find_retakes.py $D/transcript.json`: it lists earlier takes that a later take repeats, and false starts that were abandoned (takes split at pauses over 0.85 s,
   compared by their first content words), with both texts and times, and **never edits**. Approve each, remove the span from `segments`, and read `review.md` afterwards: the
   later take is not always the better one, and a deliberate repeat is content. (The idea is from the HyperFrames student kit's retake finder, MIT; ours is a separate implementation,
   tested on a synthetic transcript and found nothing in three real transcripts that had no retakes.)
5. **Apply** with `edit.sh`. Name the output after the video and pass `--title`: it is written into the file's metadata by a lossless stream copy
   (chapters kept). It resolves a provider, builds the captions, warns about anything the provider cannot do, runs the edit,
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
  "output":   { "width": 1920, "height": 1080, "fps": 30, "lufs": -16.0, "reframe": "none" },   // reframe: none | crop | blur (blurred fill) | face (follow the speaker)
  "segments": [ { "in": 0.75, "out": 4.32, "zoom": 1.0 }, { "in": 6.30, "out": 7.55, "zoom": 1.08 } ],   // source seconds, back to back in the output; reframe "face" adds "layout" and "crop" to each
  "audio":    { "highpass": 80, "denoise": 12, "compress": true, "presence": true, "fade_ms": 8, "lufs": -16.0 },
  "video":    { "color": "auto", "stabilize": false, "lut": null },     // color: "none" | "auto" | {"saturation":1.2,"contrast":1.1,...}; lut: a .cube path
  "captions": { "enabled": true, "style": "box", "max_chars": 42, "burn": true, "sidecar": "srt" },   // style: box | plain | karaoke | kinetic; optional: font ("IBM Plex Mono"), max_lines, accent ("#ff2e88"); kinetic also max_words (3) and y (0.62 of the height)
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

`"style": "kinetic"` is the vertical-video look (`reference/short-form.md`): 3 words at a time in big capitals (Big Shoulders Display unless `font` says otherwise) with a thick outline,
centred at `y` of the height, the spoken word turning the `accent` colour; `max_words` changes the 3. Tested by burning it onto a portrait clip from a real transcript.

Captions are built from the transcript, **remapped through the cuts**: a word in a removed span disappears, a word cut in half is clipped.
Cues break at sentence ends, long pauses and at the cuts themselves, never overlap, and stay on screen at least 0.6 s. The same cues are
written as a sidecar `.srt` next to the output (same name, `.srt`), so other editors and players can use them. Portrait output gets bigger text,
26-character lines and a margin above the app-UI zone. Place lower thirds above the bottom 20% so they do not sit under the captions.

## Following the speaker's face (`reframe: face`)

`crop` takes the middle of the frame, so a speaker who sits to one side, leans or walks gets cut off at 9:16. `face` finds the face, moves the crop window with it, and shows the whole frame
when there is no face to follow. It is for an output narrower than the source (a 16:9 recording to 9:16); a source that is already vertical needs nothing.

```bash
CRAFTVIDEO_ALLOW_DOWNLOAD=1 bash $S/get_face.sh          # once: OpenCV 4.13 in its own venv (hash-pinned) and the 232 KB YuNet face model (MIT, hash-pinned), into ~/.local/share/craftvideo/face
FACEPY=~/.local/share/craftvideo/face/venv/bin/python
$FACEPY $S/face_track.py analyze rec.mp4 $D/face.json [--ranges "95-126,176-205"]     # about 3 samples a second at 480 px; --ranges limits it to the parts that matter
$PY $S/plan_edit.py ... --width 1080 --height 1920 --reframe face --face-track $D/face.json
#   or onto an edit.json that exists:  $PY $S/face_track.py apply $D/edit.json $D/face.json [--smooth 0.9] [--deadzone 0.05]
bash $S/edit.sh $D/edit.json $V --title "..." --transcript $D/transcript.json
```

Only `analyze` needs OpenCV, and it runs under that venv's python (which reuses the system numpy). `apply`, `plan_edit.py` and `edit.sh` need nothing extra. A track is reusable: it is about the source, not the edit.

What lands in `edit.json`, per segment: `"layout": "face"` with `"crop": {"axis": "x", "w": 606, "h": 1080, "keys": [[0.0, 894], [0.333, 888], ...]}` (seconds from the segment's start, then the window's left
edge in source pixels; at most 60 keys, linear between them), or `"layout": "fit"`: the whole frame over a blurred copy of itself, for a shot with no face (a slide, a screen recording).

- The choice is made per shot, between scene cuts: `face` when a face is found in at least half of the shot's samples. A shot under 1 s takes its neighbour's kind, so a flicker is not a layout change. A segment that crosses
  a change is split there, and the provider keeps the sound continuous across a split that is not a cut (no fade at the join).
- Scene cuts come from ffmpeg's scene score, plus any jump of the face by more than a fifth of the frame width between two samples (a cut the score missed), pinned to its exact frame. The crop jumps at a cut and never pans across one.
- Within a shot the path is: gaps filled from the nearest sample, a median filter against single-sample spikes, a deadzone (5% of the crop width, `--deadzone`: the frame stays still while the head only moves a
  little), then a critically damped spring run forward and backward over the samples (`--smooth` seconds of ease, default 0.9; lower follows tighter). A pan eases in and out, never overshoots, and does not trail a moving
  face. The window's speed is capped at 0.4 of the source's width (or height) a second.
- A punch-in `zoom` is applied after the crop window, so it zooms into the speaker. With more than one face the larger one is followed, with a bias for the one followed a moment ago so two people of similar size do not make the frame flip.
- To change it by hand, edit `keys`, or delete a segment's `crop` and set `"layout": "fit"` to show the whole frame.

Limits: one face at a time (no stacked two-speaker layout), faces under 0.15% of the frame are ignored, and YuNet misses a face turned away or hidden (the shot then falls back to `fit`, which is safe but not pretty).
A face that keeps moving trails the window by the deadzone plus a little of the spring: in the tests the face sat within about 11% of the output width of the middle during a steady slide. A portrait source cropped to landscape follows the face up and down (the `y` axis); that was run once by hand on a synthetic source (the marker stayed within 12% of the middle) and is not in the self-test.
`face_track.py --selftest` needs no OpenCV: it slides a bright marker across a frame, reframes it to 9:16 through the provider and checks that the marker stays near the middle (`conformance.sh edit ffmpeg` runs it).

## Providers (`edit`)

| Provider | Does | Does not | Notes |
|---|---|---|---|
| `ffmpeg` (default) | cuts, jump-cut zoom, audio chain, music ducking, loudness, colour/LUT, stabilise, reframe (centre crop, blurred fill, or following a face), burned captions, titles, overlay clips, chapters | stacked or split-screen layouts | one filter graph, one x264 encode (crf 18); `vidstab` needs a second analysis pass |
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

The face-following crop was run on two sources built from a real talking-head reel (the reel is vertical, so it was placed on a 1920x1080 canvas as a 900 px wide panel that slides sideways, to give a known motion; the reel is
not included). On the 54 s one, a sinusoidal drift of 380 px each way: 162 samples at 3 a second, a face in all 162, 10 scene cuts found, and the speaker is in the middle of the 1080x1920 output in all ten frames looked at, from two clips cut from it
(`reference/clips.md`). On a 24 s one with a 4 s gradient "slide" with no face between two talking shots: 60 of 72 samples had a face, six cuts were found (2.5, 7.3, 9.5, 12.0, 16.0, 19.9 s),
the segments came out as face (0 to 12.0 s), fit (12.0 to 16.0 s, the whole slide over its own blur, nothing cropped off) and face (16.0 to 24.0 s), and at the two joins the audio has no click and no dip (the largest
sample-to-sample step within 1 ms of a join equals the one in a render of the same audio without the split). Analysis of the 54 s source took
3.5 s on the CPU. Findings that changed the code: a causal spring made the frame trail a moving face by about 0.9 s (now run forward and backward); comparing 3 fps thumbnails missed cuts whose size was below the noise
of a moving speaker (now ffmpeg's scene score plus face jumps); and the first clip cut on its final word failed the caption gate, because a cue held for 0.6 s outlasted the video (the last cue now ends with it).

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
- **A cue held for its 0.6 s minimum can outlast a clip cut on its last word.** The last caption ended 0.3 s after the video and `qa_edit.py` failed the sidecar. The last cue now ends with the video.
- **A smoothing spring that only looks backward lags a moving face.** The whole recording is known, so the face path runs through the spring forward and then backward: it eases in and out without trailing.
- **Scene cuts are not a thumbnail difference.** At 3 samples a second the difference between two frames of a moving speaker is as large as many real cuts. ffmpeg's scene score at the source's own frame rate finds them;
  a face that jumps across the frame between two samples is taken as a cut as well.

## Rules for the person's recording

The recording is the person's. Cutting words can change what someone seems to have said: read `review.md`, keep the cut you can defend, and
do not edit a statement into a different meaning. A hosted transcribe provider receives the audio. Add captions only from the real transcript
(the skill never invents words). Deliver files, never post.
