# Visual craft: type, colour, motion, cuts, finish, and the critic pass

Defaults for videos that look designed instead of generated. Each number is tagged: **M** measured by us, **R** reported by a public tool's docs and not verified here
(the tool is named). Treat them as defaults to break on purpose, not laws. Where one of our own rules differs, ours wins for anything a person has to read: text stays
settled for about 0.3 s per word (`reference/storyboard.md`), and a sources card keeps its 3 to 4 s.

Where they come from: Motionmaxxing (Apache-2.0; its numbers are aggregates over 53 SaaS launch clips it re-created privately, so they describe that genre) and HyperFrames
(Apache-2.0), both read through their public repositories and not run; ideas from onetake (PolyForm Noncommercial) and Hypit (source-available, commercial use restricted) only, with nothing copied;
Lemo-Opuscar (MIT) for the idea of looks as presets. No code or prose was taken from any of them. The five reels are in `reference/short-form.md`.

## Type and layout (sizes as a share of frame height; 1080p in brackets)

- Headline 7 to 11% (75 to 120 px), hero number 22 to 29%, body 28 to 42 px, labels 18 to 24 px, padding 60 to 140 px. R: Motionmaxxing, HyperFrames.
- Nothing that must be read under 2.5% of the height (27 px at 1080p). R: Motionmaxxing.
- One display family and one text family, never two sans; weight contrast (300 against 900, or 400 against 700); display tracking -0.02 to -0.05 em. R: both.
- Three layers at most, two focal points, one hero per frame, the hero 60 to 80% of the width. R: HyperFrames.
- **Cover the text: a picture must remain.** A frame that is only words on a flat ground is a slide. R: Motionmaxxing.
- The default to avoid is all-caps centred text on a gradient, what a model produces when it is not given a reference (reel A calls it "AI slop"). Give the scene a
  reference and real assets (a screenshot of the product, the source page, the object) and build from them.
- Keep content in the top 83% so captions have room. R: HyperFrames; `reference/edit.md` says the same for lower thirds.

## Colour

- One saturated hue plus at most one signal colour; charcoal rather than #000 and off-white rather than #fff. R: both.
- No full-screen linear gradient on a dark ground: H.264 bands it. Add grain (below) or dither. R: HyperFrames. (Shader output traps are in `reference/motion-graphics.md`.)
- The five reels: cream, black, terracotta and one lime (B); a dark ground with a new accent per item (C); white page with a yellow highlighter (D, E). M, by eye.

## Motion grammar (30 fps, frames in brackets)

| What | Default | Note |
|---|---|---|
| a move or scale in | 0.4 s (12 f) | the median move anywhere is 0.33 s (10 f), middle half 6 to 22 f. R: Motionmaxxing |
| a move or scale out | 0.43 s (13 f) | opacity 6 f in and 7 f out; blur 7 f |
| landing curve | ease-out (58% of moves) | exits ease-in (37%) or ease-out (35%); linear only for fades and drift |
| stagger | 1 to 3 f between siblings | words: 2 to 4 f in a hook, 4 to 6 f in a headline, 8 to 12 f when the voice leads; tails overlap |
| overshoot | under 10% of moves | one visible spring per film. HyperFrames: no back or elastic eases at all |
| arrival | nothing grows from zero | start at 1.4 to 5x and settle; text enters offset 3 to 7% of the height |
| holds | a payoff 0.5 to 1.2 s (a number), 0.8 s (a list) | a designed breath is 0.6 to 1.5 s; a launch film's end hold is 0.6 to 1.4 s, ours is longer because sources are read |
| camera | push 1.46x in 10 f, pull 1.32x in 13 f (medians) | whip 8 f; a one-frame snap then a 0.3 to 0.6 s settle |

More defaults from HyperFrames' creative skills (R; Apache-2.0, its numbers, our words):
- Durations by weight: 0.15 to 0.3 s urgent, 0.3 to 0.5 s normal, 0.5 to 0.8 s weighty, 0.8 to 2 s cinematic.
- A scene builds in its first 30%, breathes from 30 to 70% (one ambient move at most) and resolves in the last 30%. The exit (about 0.25 s) is shorter than the entry (about 0.4 s).
- A group's whole stagger finishes in under 0.5 s, ordered by importance; at most two tweens in a scene share an ease; vary the entry direction; the first motion starts 0.1 to 0.3 s in.
- Reveal each piece on its spoken cue across the back half of the scene, not all in the first quarter.
- Settle: cubic-out to about 93% by 78% of the time, then glide the last 7%; no overshoot by default.
- Count-up: sine in-out over about 1.7 s, the exact final integer, a 1.07 pulse over 0.33 s, tabular figures. Title card: scale 0.96 to 1 over 0.85 s, then a dead hold.
- Light text on dark: weight about 350, line-height +0.05 to 0.1, tracking +0.01 em. Decoratives at 12 to 25% opacity (3 to 8% disappears), borders 2 to 4 px; a line or beam must name its start, its end and its job, or go.
- Captions: in at the first word minus 0.08 s, out at the smaller of the next cue's start minus 0.05 s and the last word plus 0.6 s, at most 6 words or 2.5 s.
- Fonts a model reaches for first (Inter, Roboto, Open Sans, Lato, Poppins) mark a default; choose a face on purpose, as `looks/` does.

```js
// every curve takes t in 0..1 and returns progress 0..1; the percentages are checked (done at 10/25/50/75% of the time)
const ease = {
  softLand:  t => (1 - Math.exp(-3.41 * t)) / (1 - Math.exp(-3.41)),   // 30/59/85/95: fast start, long soft tail, for entries
  glide:     t => 1 - Math.pow(1 - t, 1.7),                            // 16/39/69/91
  whip:      t => 1 - Math.pow(1 - t, 2.52),                           // 23/52/83/97: 7 f moves that stop hard
  accelExit: t => Math.pow(t, 2.6),                                    // 0/3/16/47: slow start, leaves fast, for exits
};
// closed-form damped spring (zeta < 1), t in SECONDS: 0 to 1, overshoots, settles. Reel A: zeta 0.42, omega 17 = a 23% overshoot at 0.20 s, within 2% from 0.49 s
const spring = (t, zeta = 0.42, omega = 17) => { const wd = omega * Math.sqrt(1 - zeta * zeta);
  return 1 - Math.exp(-zeta * omega * t) * (Math.cos(wd * t) + (zeta * omega / wd) * Math.sin(wd * t)); };
```
Inside `seek(t)` these are pure functions of time, so they fit the contract with no timeline library (`reference/motion-graphics.md`). Use the spring once, on the hero.

## Cuts and transitions

- **Do not hide a cut under a wipe; carry something across it.** One element survives the boundary and keeps changing (a pressed bar becomes the window, a card grows until
  it fills the frame), or one camera moves through every beat (reel B). Our pink bar between scenes hides a cut and carries nothing across it, which is what these sources say to avoid.
- Scenes that must stay separate pages (the `beats.json` pattern): cut at peak velocity. The outgoing scene leaves in 0.2 to 0.3 s on an ease-in with about 10 px of blur,
  the next arrives in 0.5 s on an ease-out from the same direction and opens mid-move; no more than 3 empty frames at the seam. R: HyperFrames launches, Motionmaxxing.
- Inside a beat something changes every 0.3 to 2.3 s. R: Motionmaxxing. The longest stretches where the picture barely changes in our two videos are 4.5 s and 6.9 s (M, `qa_frames.py`).
- Vary the shot lengths: the slowest scene at least 3x the fastest (R: HyperFrames), and a coefficient of variation of the lengths of at least 0.25 (idea from onetake's checker).
- A continuous camera: key a camera in the log of its zoom so equal steps feel equal, give layers a parallax factor of 1/(1+depth), and keep a far field of dots so empty ground has
  something to slide against. It needs the camera to arrive 0.1 to 0.3 s before each sentence and 0.6 to 1.2 s of travel between beats that speech does not give for free. (idea from onetake)
  `examples/continuous-camera/` is a working one: four stations in one world, the camera keyed from `timeline.json` (arrive 0.15 s before a sentence, hold to its end, travel in the gap, at
  least 0.7 s), a pull-back in the middle of each trip, a slow push through every hold, and a carrier dot and a route line in place of a wipe. Risks it respects: no state between frames (every
  value is a function of t), and the bottom 18% kept free. Ask `tighten_voice.py --gaps` for 0.7 s at the big moves, or the camera has to whip.

## Finish

- **Shutter blur**: average 8 sub-frame renders across a 180 degree shutter so fast type and 3D stop looking computer-sharp (R: Motionmaxxing). Built:
  `render.sh ... --shutter 180 --subframes 8` (about 5x the render time at 8, 2x at 4; use it on short scenes; never with `--alpha`; numbers in `reference/motion-graphics.md`).
- **Grain** over the finished frame, and dither on dark gradients (R: Motionmaxxing, in its own units). Built: `--grain 8` (subtle) to `--grain 16` (clearly visible), luma std = the value / 3.
- A real subject needs real texture: crop, blur and light a screenshot instead of filling a swatch. R: Motionmaxxing.

## Dead frames and the critic pass

Reel A's loop and reel B's judge round do the same thing: look at your own frames, score them, send them back. Do it before the full render, scene by scene.

1. **Hook**: a claim or motion in the first 0.5 s, text by 0.3 s.
2. **Hierarchy**: one hero; the cover-the-text test passes.
3. **Readable**: every line settled for 0.3 s per word, nothing outside its panel, nothing under 2.5% of the height.
4. **Alive**: no stretch where the picture barely changes unless it is a deliberate hold (`scripts/qa_frames.py` lists them, with times).
5. **Sound**: hits land on a spoken word or a beat, the voice was verified (`scripts/verify_narration.py`), the duck is audible.
6. **Truth**: every claim is in the claims table, sources are on the end card.

Render contact sheets at every scene start, middle and the frame before the cut (`render.sh --stills`), look at them at full size, write a score out of 10 per scene in
`plan.md`, fix anything under 8 and re-render only those scenes. Change the weakest thing first; a scene that scores 8 stays as it is.

**The review, two passes and then stop** (a procedure from Motionmaxxing's skill, in our words and with our tools):
1. The file decodes, the picture moves, the length matches the plan, audio is present (`finish.sh` and `qa_frames.py` say so with numbers).
2. Name the hero frame, the one a person would screenshot. If there is none, there is no hero.
3. A contact sheet of 16 even frames plus the first and last: write one sentence per frame (what is on screen, which thing is the hero, would it pass for a slide) and keep the sentences in `plan.md`.
4. Thumbnail test: shrink the sheet. Can you still read the claim?
5. Cover test: hide the text. Does every frame still show a picture?
6. Mid-change frames (2 frames before each cut, the frame before it, the cut, the frame after): hunt half-states, flat frames, broken glyphs, overflow. Run `--lint 1` as well.
7. Real-speed reading: step each text scene at playback speed; every line settled for 0.3 s per word.
8. Fix in this order: what is untrue or broken, what the viewer must grasp, the links between beats, hierarchy, timing, surface and finish, sound.
9. Report what you checked and the numbers the scripts printed. Never write "verified": you cannot watch or hear the result.

## AI default against a better decision (condensed from Motionmaxxing's decision table; R, with its caveat that it was measured on launch films)

| Default | Better | Why |
|---|---|---|
| the picture illustrates each sentence | the picture has its own job: it shows what the sentence only names | illustration turns into slides |
| every fact gets equal weight | give each beat an importance of 1 to 3; at most a quarter are 3 | if everything arrives, nothing does |
| a stat slide: one big centred number | draw the quantity to scale and show where it comes from | a number that is shown is believed |
| a count-up tween to a round value | 15 to 23 decaying per-frame steps in 0.5 to 0.9 s; round for a claim, specific for data | tweens read as presets |
| an opacity fade-in | offset plus 3 to 6 px of blur clearing in 4 to 8 frames, or a hard step | fades read as slideware |
| even gaps between words | the longest gap before the key word; authored builds shrink (about 6, 6, 4, 4 f) | the gap is the emphasis |
| a held frame that does not move | one living thing in every hold (a drift of about 2% of the width a second); a 0.6 to 1.5 s breath only before a payoff | locked frames read as slides |
| a crossfade between scenes | a hard cut mid-motion, a carried element, or a feathered wipe, and the next scene's first frame already moving | the join is a decision |
| one accent used on many things | one hue, one meaning | colour is meaning |
| two equal panels | one object per frame; two only if one has twice the other's area, or the camera moves between them | each ends up too small |
| a new effect every beat | only effects the idea needs | range is not quality |
| a glow under every scene | a halo only at an event | repeated glow reads as a template |
| a boom on every cut | 1 to 3 hand-placed hits, the bed pulled down while a card is read (`dips`) | many hits hide the real ones |
| an end card: logo, tagline, button, address | one small mark, held for exactly the reading time, quieter than the climax | the ending should be smaller than the middle |
| script phrases like "Not just X, it's Y", runs of one-word sentences, "Meet X" | say the specific thing in the subject's own words | they mark text as generated |

Pace ceiling from the same source: on average no more than one new element per 0.3 s and one major event per 0.8 s; the strongest frame sits at 60 to 75% of the length, beats shorten toward
it and the last one lingers; the last beat is at most 25% of the video, smaller than the climax, ending in motion or a designed stillness.

## Sound

- **Hits**: 1 to 3, hand-placed, with no swell under a real result. The Connected City fired 15 booms in 87 s plus a pulse, which is the pattern this rule calls a tell.
- **Reading dips**: pull the bed down 6 to 10 dB while a card or number is read in silence, and 8 to 15 dB for 0.2 to 0.5 s just before the biggest move so the move brings it back:
  `"dips": [[start, end, dB]]` in `cues.json` (our ducking follows narration only, so a silent sources card got the full bed). R: Motionmaxxing.
- A word tied to speech lands 0 to 2 frames before it is said; only a scene's entrance leads by 0.1 to 0.3 s.
- Duck under the voice by about 9 dB with a short attack that ends at the word's onset and a 300 ms release (ours: about 10 dB, 30 ms attack, 280 ms release). Loudness -14 LUFS for a reel, -16 otherwise, true peak under -1.

## Ideas not built yet, in the order the sources agree on them

1. **A carried-seam helper for scenes that must stay separate pages** (the continuous camera is the other route, and is built: `examples/continuous-camera/`). S.
2. **A voice carve** in the music bed (a static 3 to 4 dB dip at 1 to 3 kHz before the duck, and HyperFrames' voice chain: 80 Hz high-pass, 250 Hz -3 dB, 3 kHz +2.5 dB, limiter last), so the
   voice does not fight the bed. Not measured here, so not built. S.
3. **Tracker chips** (the 1 to 5 or section dots of reels B and C) as a reusable component for scenes. S.
4. **Procedural looks** that need drawing code, not only colour and type: a halftone-collage look (rotated dot grid, misregistered plates) and a painted look (wobbled strokes redrawn at 12 Hz). M each.
5. **A `hyperframes` render provider** (wrap `npx hyperframes render` behind our contract): feasible but needs the pinned Chrome or a Chromium path and was not tried; our own `html` provider already
   covers the same ground. M.

Built since this list was first written: the layout lint, shutter blur and grain, the fail-fast determinism preflight, parallel page workers (`reference/motion-graphics.md`), word anchors
(`reference/html-scenes.md`), the kinetic caption style and the retake finder (`reference/edit.md`), nine looks (`looks/README.md`), reading dips for the music bed, and a continuous-camera example.
