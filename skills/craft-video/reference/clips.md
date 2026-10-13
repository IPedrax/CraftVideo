# Clips from a long recording (mode B, long to short)

Take one long recording (a podcast, a talk, a stream, a webinar, an interview) and cut the few moments worth posting as vertical shorts: each one a clean start and end, a
title, the speaker kept in frame, kinetic captions, loudness at -14. The recording is still the person's: the same rules as `reference/edit.md` apply, and nothing is posted.

The work is split on purpose:

| Who | Does | Because |
|---|---|---|
| a script (`find_clips.py candidates`) | proposes 6 to 12 sentence-aligned windows from the transcript and the audio, each with the signals that scored it | cheap, repeatable, and it never loses a sentence boundary |
| **you** (Claude), reading the text | picks, titles and scores the clips, and writes `PICKS.json` | "would someone who sees only this clip understand it and care?" is a judgement about meaning, and no regex has it |
| a script (`validate`, then `edl`) | refuses a pick that starts mid-sentence or runs too long, then writes one `edit.json` per clip | a checked pick turns into the same data every other edit uses |

```
rec.mp4 -transcribe.sh-> transcript.json --+
        -analyze.py-----> analysis.json ---+-> find_clips.py candidates -> candidates.json -> (read, pick) -> PICKS.json
        -face_track.py analyze (ranges)-> face.json                                                              |
                                          find_clips.py validate <------------------------------------------------+
                                          find_clips.py edl --reframe face --face-track face.json -> clips/NN-title.edit.json
                                          edit.sh -> clips/NN-title.mp4 (+ .srt)      qa_edit.py, review_edit.py as in edit.md
```

## The steps

`S="${CLAUDE_SKILL_DIR}/scripts"`, `PY` as in `reference/edit.md`, `D=<title-slug>` (a folder named after the recording or the series), `FACEPY=~/.local/share/craftvideo/face/venv/bin/python`.

```bash
$PY $S/analyze.py rec.mp4 $D/analysis.json
bash $S/transcribe.sh rec.mp4 $D/transcript.json --language en          # sentences need the real transcript; a hosted provider uploads the audio
python3 $S/find_clips.py candidates --transcript $D/transcript.json --audio rec.mp4 --min 20 --max 55 --top 12 --out $D/candidates.json
# read $D/candidates.json (the text of every window and its signals) and, for anything promising, the transcript around it; write $D/picks.json (format below)
python3 $S/find_clips.py validate $D/picks.json --transcript $D/transcript.json [--snap]      # exit 1 lists every problem; --snap moves a bound onto the nearest sentence edge
CRAFTVIDEO_ALLOW_DOWNLOAD=1 bash $S/get_face.sh                         # once, for the face-following crop (reference/edit.md, "Following the speaker")
$FACEPY $S/face_track.py analyze rec.mp4 $D/face.json --ranges "95-126,176-205"    # only the picked spans: the same seconds the picks use
python3 $S/find_clips.py edl $D/picks.json --source rec.mp4 --transcript $D/transcript.json --analysis $D/analysis.json \
        --out-dir $D/clips --reframe face --face-track $D/face.json      # prints one edit.sh command per clip
bash $S/edit.sh $D/clips/01-<title>.edit.json $D/clips/01-<title>.mp4 --transcript $D/transcript.json --title "<the title>"
```

`--reframe` is `face` (follow the speaker, needs the track), `crop` (the middle; the default), `blur` (the whole frame over a blurred copy) or `none`. A recording that is already vertical
needs no reframing: a crop to the same shape changes nothing, so leave the default. `edl` writes the captions as `kinetic` with a yellow accent, the output at 1080x1920 and the loudness at -14
(`--width`, `--height`, `--lufs`, `--style` change them). Each clip's pauses and fillers are cut as in any edit (`plan_edit.py --range`), so the clip is shorter than its `end - start` when the speaker paused.
Then read `review/review.md` and look at the clip as in `reference/edit.md`; the "words removed" check matters more here because a short is judged on every word.

### PICKS.json

```json
{ "picks": [ { "start": 95.0, "end": 125.38, "title": "Why we threw away a working system",
               "scores": { "hook": 20, "engagement": 17, "value": 20, "shareability": 15 },
               "why": "opens on the question, then one number that explains it, and ends on the point" } ] }
```

`start` and `end` are source seconds. Take them from the candidate. When you move a bound (to add the sentence that lands the point, or to drop a weak opening), read the new time off the transcript's
word times and let `validate --snap` move it onto the nearest sentence edge. `validate` checks that

- both bounds are inside the recording, the clip is 15 to 60 s (`--min`, `--max`), it starts within 0.25 s of a sentence start and ends within 0.35 s of a sentence end, and neither bound falls inside a word (`--snap` moves a bound onto the sentence edge for any of these);
- the title is 3 to 9 plain words (no hashtag, emoji or quotation marks);
- each score is one of `hook`, `engagement`, `value`, `shareability`, from 0 to 25;
- no two picks overlap by more than 15%.

## The rubric for the pick

Score each candidate you consider on four things, 0 to 25 each (the sum is only for ordering your own picks). Write one line of `why` that a person could argue with.

| | The question | A low score looks like |
|---|---|---|
| hook | does the first line make a stranger stay? A claim, a question, a number, a contradiction, a story turn | "So, um, as I was saying", a greeting, a lead-in |
| engagement | does it keep going: pace, turns, a change of emotion, a laugh, a pause that lands | a flat stretch of context with no turn in it |
| value | does the viewer leave knowing or feeling something specific | a point that needs the previous ten minutes |
| shareability | would someone send it to one person, and say what? | true and dull, or a quote with no context |

Rules that outrank the scores:

1. **Standalone.** "Would a viewer who sees only this clip understand it and care?" If a line starts with "and", "so that", "this" or "they" and the antecedent is outside the clip, move the start or drop the pick.
2. **Skip** the intro, sponsor reads, calls to action ("like and subscribe"), housekeeping, and any quote that needs its context. The scorer penalises these, but it only knows the phrases it knows.
3. **Length.** 25 to 50 s is where a short holds; 15 to 20 s is fine for one sharp point. A clip is as long as its point, never padded to a number.
4. **Accuracy over virality.** The title must be what the clip says, and an edit must never make the speaker mean something else: do not cut inside a sentence to join two halves into a claim they did not make, and do not title a hedge as a certainty.
5. **End on the payoff,** not on a trailing "and". A clip that ends on a question the answer to which is cut off is a bad clip.
6. Pick fewer, better. Three that you would post beat eight that you would not; say so when the recording does not hold more.

## What `candidates` scores

Windows are runs of whole sentences (a sentence ends at final punctuation or after a pause of 0.7 s) between `--min` and `--max` seconds, scored on deterministic signals and kept non-overlapping:

| Signal | Points |
|---|---|
| hook, from the first sentence | a question +2, a number or a unit +1.5, a trigger word (wait, why, how, never, secret, mistake, wrong, truth, ...) +1.5, a story turn ("I thought", "we realized", "I decided") +1, a short first line (12 words or fewer) +1 |
| standalone | the first sentence opens with and, so, because, which, that, it, this, they, then, also, or, but: -2 (-0.5 when it is a question, since "So how do you..." stands alone) |
| pace | 2.2 to 3.6 words a second +1; under 1.6 -1.5 |
| energy | each audio peak inside the window (1 s of voice 5 dB above the median of the 40 s around it, at least 4 s apart), up to two, +1.25 each |
| payoff | it ends on a full stop or an exclamation mark and a breath +1; it ends on a question -1 |
| question | a question inside the window, up to two, +0.5 each |
| length | 25 to 50 s +1; outside 20 to 55 s -0.5 |
| junk | a sponsor, call to action, "welcome back to" or "thanks for watching" phrase -3; a filler share above 6% -1 |

Each candidate prints the signals that fired, so a score is never a mystery.

### Honest limits

- **It cannot tell a window is empty.** On the made-up talk in `examples/clips/`, the two real stories are candidates 3 and 6; the other four are windows of filler chatter, scored by structure only. Reading the text is the step that catches that.
- **English words only.** The hook, story, junk and filler lists are English. Pace, length, question marks, numbers and the loudness peaks work in any language, but for another language translate the lists at the top of `find_clips.py` or lean harder on your own reading.
- **Text and loudness only.** It does not see the picture: a demo, a slide or a reaction that makes a moment is invisible to it. Look at the recording's contact sheet (`review_edit.py` on a draft) when the picture matters.
- **No topic model.** It does not group moments by subject or find the best of several takes of the same idea; `find_retakes.py` (reference/edit.md) lists repeated takes.
- **One transcript, one voice assumed.** The sentence splitter uses the transcript's punctuation (faster-whisper gives it) and falls back to 0.7 s pauses; speaker labels are not used.

## Measured

On a real talking-head reel (54 s, placed as a 900 px wide portrait panel drifting side to side across a 1920x1080 canvas so that a centred crop would lose the speaker; the reel is not included):
`transcribe.sh` and `analyze.py` ran first; `candidates --audio` returned six windows (`--min 10 --max 28`, because the whole reel is under a minute); two picks of 23.6 s and 14.0 s passed `validate`
(`--min 10 --max 30` for the same reason); face analysis of the two spans took 2.9 s (3.5 s for the whole file, 3 samples a second); `edl` wrote two `edit.json` files and `edit.sh` rendered them in 17 s and
11 s on the CPU (no GPU is used). Both clips are 1080x1920 at 30 fps, loudness -14.0 LUFS, true peak -1.5 dBFS, with the speaker in the middle of the frame while the panel slides and kinetic captions
burned in, and both pass every `qa_edit.py` gate. The dark bands at the edge of a few frames are the test canvas around the panel, not the crop.
The gate found a real fault on the second clip: a clip cut on its last word has no tail, `captions.py` held the last cue for its 0.6 s minimum, and that cue ended 0.28 s after the video, so the caption check
failed (it ended about 0.3 s after the 14.0 s video). The last cue now ends with the video, and `find_clips.py --selftest` plants a fast ending (three words in 0.3 s) to keep it that way.
Two self-tests run in `conformance.sh edit ffmpeg`: `find_clips.py --selftest` (on the made-up talk the sponsor read and the call to action never become candidates, the two stories rank first, every kind of
bad pick is refused, `edl` writes a vertical clip EDL, and the captions stay inside the clip) and `face_track.py --selftest` (footage with a marker that slides across the frame stays within about 11% of
the middle of the vertical output).

Not tested: a recording of an hour, several speakers or a two-person interview (the crop follows the larger face and does not stack two people), a language other than English, a real GPU,
and whether the picks go well with an audience (the rubric is a method, not a forecast).

## Where the ideas come from

The shape of the workflow (a transcript-first shortlist, a rubric of hook, engagement, value and shareability, a hard check on the picks, then a vertical edit that follows the face) comes from
reading SupoClip (FujiwaraChoki/supoclip, AGPL-3.0), which asks a language model to pick and score and downloads from YouTube. Nothing here is its code or its prompts: `find_clips.py` and `face_track.py`
are our own, written from a description of those ideas, with no language-model call, no download and no key. SupoClip's licence is AGPL-3.0, so its code stays out of this repository.
