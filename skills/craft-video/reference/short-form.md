# Short-form vertical video (Reels, Shorts, TikTok)

What five public Reels about AI-made video have in common, measured with this suite's own tools in October 2026 (the videos themselves are not included, and the
creators are not named). Use it when the brief says reel, short, TikTok, 9:16 or "for social". These are numbers about what is out there, not laws: a calm
documentary explainer is still right for a different audience (`reference/storyboard.md`).

## The five, measured

| | A: talking head with inserts | B: all-3D, AI narrator | C: list of five | D: screen recording plus type | E: the same, Portuguese |
|---|---|---|---|---|---|
| length | 54.7 s | 58.0 s | 58.8 s | 38.6 s | 26.8 s |
| size, fps | 1440x2560, 30 | 1080x1920, 30 | 1080x1920, 60 | 1080x1920, 60 | 1080x1920, 30 |
| first spoken word | 0.00 s | 0.12 s | 0.00 s | 0.04 s | 0.18 s |
| speech pace | 298 words/min | 196 | 117 | 177 | 185 |
| hard cuts (scene score 0.2) | 27, a small insert every 1 to 2 s, none in the first 3 s | 0, one continuous camera | 20, its cards swapping | 0 | 0 |
| picture barely changes | 15% of the time | 2% | 69% | 35% | 36% |
| longest such stretch | 1.0 s | 0.8 s | 3.2 s | 4.2 s | 3.2 s |
| music tempo | about 123 BPM | about 123 | about 129 | 161 (probably 80 doubled) | about 123 |
| loudness, loudness range | -14.2 LUFS, 2.3 LU | -14.1, 1.9 | -14.1, 2.2 | -14.3, 3.0 | -14.1, 2.8 |

By the same measures your own two videos are: The Connected City, 87 s, 56% barely changing, longest stretch 6.9 s, 96 BPM, -16.0 LUFS; AI Is Taking Games Apart,
30 s, 66%, longest 4.5 s, -16.0 LUFS. "Barely changes" is `scripts/qa_frames.py`'s test (under 0.5/255 per frame on a 128 px copy), so a slow drift or a caption
changing over a still ground counts as barely changing.

## What they share

1. **Speech starts inside the first 0.2 s, and the first sentence is the claim** (5 of 5). "Nobody filmed this video. Nobody edited it. And this voice isn't a person."
   (B). "Most people don't realize [the thing you see everywhere] is not just one prompt" (A). A claim, question or promise, never a title card or a logo. Our default
   lead-in is 0.4 s (`tighten_voice.py --lead`): use 0.1 for a reel.
2. **Text is on screen by 0.25 s** (5 of 5; A and C from frame 0). A reel can open on a blank frame for a quarter of a second at most.
3. **Captions are large, short and carry one accent.** Four of five light the key word or the word being spoken, in lines of 2 to 6 words: a dark pill with the active
   word in lime (B), words dimming up to white (C), black capitals on a yellow highlighter box (D, E). A keeps a plain two-line serif caption and lights the key words of its
   headline instead. Where they sit (eyeballed from the frames, share of the way down): A 75 to 80%, B 85%, C 76%, D 64%, E the top quarter. Keep to `reference/edit.md`'s
   rule of staying above the app UI unless you have a reason.
4. **Something shows where you are** (B and C): B has a section chip with dots (`01 / RESEARCH` ... `06 / JUDGE`), C a 1 to 5 tracker plus brand and topic chips.
5. **The proof is on screen.** C, D and E show the source page (C boxes the line being read); B turns each claim into an object (waveforms with "61 takes, 8 thrown out",
   a counter, a before and after of its own output). Our `facts.json` and sources card do the same job: show the source while it is read.
6. **No bar wipes.** Motion is carried or continuous: B morphs one object into the next and never cuts, C blurs the outgoing card into the next card's colour, D and E
   scroll and zoom one page. A's cuts sit nearer the beat than chance (median 0.16 of a beat from the nearest beat against 0.25 for random times; C: 0.17; about a
   third within a tenth of a beat), not on it.
7. **Music never stops** (silence under 1% in four of five), 123 to 129 BPM in four, loudness range 2 to 3 LU. All five files measure -14.1 to -14.3 LUFS, which is
   what the platform's loudness normalisation would produce whatever was uploaded, so master a reel at -14 and it will not be re-levelled.
8. **The post offers one thing for a comment** (four of five): "comment KEYWORD and I'll send the guide", spoken in the last 3 to 8 s in A, B and E, in the post text in C.
   C stops on "And remember." (an unfinished sentence that would run into its first line when the reel loops; it looks designed, we could not confirm it). None ends on a logo card.
9. **Pace varies a lot by genre**: 117 to 298 words per minute, median 185 (3.1 words/s) against this suite's documentary default of 156 (2.6). The slow one (C) uses
   short lines of 2 to 7 words with a visual change for each; the fast one (A) is a person talking with the pauses cut out.

## What the reels teach about making them

- A's own recipe, spoken: Claude writes code that paints every frame, a headless browser captures them, ffmpeg stitches them (this is the `html` provider);
  give it a reference and real assets, because unprompted it defaults to all-caps centred text on a gradient ("AI slop"); use closed-form spring physics instead of
  CSS easing; synthesize the sound in code and lock cuts to the beat; **make it watch its own frames, score each scene out of 10, hunt dead frames and re-render until
  every scene is 8**. `reference/visual-craft.md` has the rubric and the spring.
- B's pipeline matches ours (research, script, voice, code, music, judge) with two habits worth copying: the voice is checked word by word and a take with a wrong word
  is thrown away (`scripts/verify_narration.py`), and a second pass judges the finished video so that the fixed version is what ships.

## Making one with this suite today

```bash
# about 3 words/s: --speed 1.15 on the voice, a tighter lead-in, and check the words before anything else
bash $S/narrate.sh work/script.txt work/narration_raw.wav --speed 1.15 --seed 20261013 --instruct "(...)"
$PY $S/verify_narration.py --audio work/narration_raw.wav --script work/script.txt --language en
$PY $S/tighten_voice.py --raw work/narration_raw.wav --script work/script.txt --out work/narration.wav --timeline work/timeline.json --lead 0.1 --target 45
bash $S/render.sh work/scene.html work/silent.mp4 --provider html --timeline work/timeline.json --width 1080 --height 1920 --fps 30
bash $S/assemble.sh --video work/silent.mp4 --voice work/narration.wav --music work/music.wav --out work/final.mp4 --lufs -14      # cues.json: "bpm": 124
bash $S/finish.sh work/final.mp4 . --title "The Title" --lufs -14 --voice work/narration.wav   # also runs qa_frames.py on the picture
```
Captions go on through `edit.sh` with a one-segment EDL (`reference/edit.md`): `"captions": {"style": "karaoke", "max_chars": 22, "max_lines": 2, "accent": "#..."}`.
Not built yet: a 2 to 4 word kinetic-capitals caption style (D and E), the tracker chips as a reusable component, and the word-anchored timeline
(`reference/visual-craft.md`, "Ideas not built yet").

## How this was measured

`ffprobe`/`ebur128` for size, rate and loudness; ffmpeg's scene score (0.20) for cuts; frame differences on a 128 px copy for "barely changes"; librosa's beat tracker
for tempo and cut-to-beat distance (indicative: it runs over speech plus music); Whisper large-v3 for pace and first word; contact sheets read by eye for
everything visual. Five videos from one platform in one month is a sample, not a survey.
