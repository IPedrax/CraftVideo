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

## Finish

- **Shutter blur**: average 8 sub-frame renders across a 180 degree shutter so fast type and 3D stop looking computer-sharp (R: Motionmaxxing). 8x the render time; smooth scenes
  only; never with `--alpha`. Not in the `html` provider yet.
- Grain 0.03 to 0.06 of full scale over the finished frame, and dither dark gradients. R: Motionmaxxing.
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

## Ideas not built yet, in the order the sources agree on them

1. **Layout lint before rendering**: seek 9 sample times, read every text box from the DOM, flag overflow, overlap, text under 2.5% of the height and anything in the caption band
   (Motionmaxxing and HyperFrames each ship a version of it; it automates what the contact-sheet review finds by eye). Effort M, in `scripts/providers/render/html-render.mjs`.
2. **Shutter blur and grain** as render flags (`--shutter 8`, `--grain 0.04`). S to M.
3. **Fail-fast determinism**: seek mid, seek 0 and compare, before the encode; ours runs after it and only warns. S.
4. **Parallel page workers** striped by frame (frames are pure functions of time). M.
5. **Word anchors**: markers in the script tied to transcript word times, so scenes follow words and a new voice re-times everything. M.
6. **A carried-seam helper** (`cut.js`) and a continuous-camera example. S to M.
7. **A kinetic-capitals caption style** for 9:16 (2 to 4 words, key word highlighted). M.
8. **Look presets** (`looks.json`: colour roles, type roles, grain, easing, banned moves, duck level). S to M.
