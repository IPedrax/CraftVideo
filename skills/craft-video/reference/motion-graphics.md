# 3D and professional motion graphics

Everything here runs through the `html` render provider (headless Chromium + ffmpeg), so it works in both modes: as the picture of a
**made** video (mode A), or as **overlays composited onto an edited recording** (mode B, `overlays[].type = "clip"` in `edit.json`).
Pick the tool by what the shot needs:

| The shot | Use | Status here |
|---|---|---|
| A 3D object, camera moves, lights, particles, bloom | **Three.js** in an HTML scene (`examples/three-3d/`) | Proven: rendered, deterministic, timed on a GPU |
| A 3D model of an object from a photo | **img2threejs** makes the model, Three.js shows it (`examples/img2threejs-bridge/`) | The plumbing is proven with a generator-made blockout; a full reconstruction run was not done |
| A shader or generative background (flow fields, contours, noise) | **WebGPU/WGSL** (`examples/webgpu-shader/`) or a WebGL fragment shader | Proven; GPU and software frames agree to 0.017/255 |
| Typography, UI-style motion, staggers, counters, SVG drawing | **GSAP** on a paused timeline (`examples/gsap-timeline/`), or CSS/WAAPI (`examples/html-css-animation/`) | Proven |
| A lower third, bug, callout or title sting over footage | render with `--alpha 1` (ProRes 4444), place with an `overlays` clip (`examples/overlay-lowerthird/`) | Proven end to end |
| A 3D object floating over footage | the Three.js scene rendered with `--alpha 1` (`examples/three-3d/`), placed the same way | Proven end to end (no bloom in alpha mode) |
| A hand-painted character that reacts to the narration (Clawd, the Claude Code mascot) | `mascot.sh`: a p5.js + p5.brush kit painted on a small canvas, two draws a frame (white and black) for real alpha, a transparent overlay (`reference/mascot.md`, `examples/mascot/`) | Proven: rendered, reproducible to within a level in a pixel or two (software renderer noise), composited over a picture with its sound kept |
| Seeded generative art (p5.js), a logo or its animation | the OmniSkill `algorithmic-art` / `logo-design` skills make the assets, the scene plays them | Possible: not wired or run here (p5.js itself runs in the provider: the mascot page is the proof) |
| After Effects-style compositions with 306 effects | the `effectcraft` provider | Proven (the first video) |
| Interface sound for the shot | OmniSkill `uisfx` (synthesised locally), mixed in with `music` or the editor | Possible: not run here |

OmniSkill's `motion-ui` picks between Framer Motion, GSAP, anime.js and Three.js for an interface; here the decision is the same, only the
output is frames instead of a page. Its `vgpu` skill (Vercel's WebGPU wrapper) is Possible but untried: the raw WebGPU example shows the
rules any WebGPU code must follow here.

## The rule for everything: a frame is a pure function of t

`window.craftvideo.seek(t)` must draw the same pixels every time it is called with the same `t`, whatever was drawn before. No clock, no
`requestAnimationFrame` loop, no `Math.random` (use a seeded generator), no animation left running on its own. The renderer checks this twice: a
**preflight** before encoding visits five times forward and then backward and stops with exit code 4 if any frame differs the second time (so state built up frame
by frame, an unseeded random or a clock fails in seconds, not after the render), and after the last frame it seeks to 0 again and prints a `WARNING` if the first
frame changed.
For any animation library the pattern is the same: build a **paused** timeline once, set its playhead in `seek`.

```js
// GSAP: tween plain state, render from it (tl.time(t) suppresses callbacks, so do not write the DOM from onUpdate)
const tl = gsap.timeline({ paused: true });
cues.forEach((c, i) => tl.from(lines[i], { x: "-8vw", opacity: 0, duration: 0.5, ease: "power4.out" }, c.start));   // cue time = timeline position
window.craftvideo = { seek(t) { tl.time(t); render(state); return document.fonts.ready; } };
// anime.js: anim.seek(t * 1000)   ·   CSS/WAAPI: for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000 }
// three.js: set object transforms from t, then composer.render() or renderer.render(scene, camera)
```

## Three.js

```bash
bash $S/get_three.sh /path/to/node_modules/three       # once; copies build/ and examples/jsm to ~/.local/share/craftvideo/three (CRAFTVIDEO_ALLOW_DOWNLOAD=1 fetches it)
bash $S/render.sh scene.html out.mp4 --provider html --timeline timeline.json --width 1920 --height 1080 --fps 30 --gpu auto
```

In the scene, `import * as THREE from "three"` and `import { ... } from "three/addons/..."` just work: the renderer serves the page from a
private origin (`http://cv.local`), maps those names to the installed package, and serves your scene's folder (`--root DIR` to widen it), so
ES modules, `fetch()`, GLB and texture loading work. A scene with its own import map keeps it. Create the renderer with
`preserveDrawingBuffer: true`, draw inside `seek(t)`, and follow these three.js traps (each was hit while building the examples):

- **Set the background with `scene.background = new THREE.Color(...)`, never `renderer.setClearColor`.** With an `EffectComposer` and
  `OutputPass` the clear colour is encoded twice (`0x0a0a0b` came out as `0x38383b`), and once a PMREM environment has been built the **first
  frame came out different from every later one**. Frame 1 black, frames 2+ grey broke the pure-function rule; the determinism guard exists
  because of this.
- **Tone mapping crushes near-black.** ACES maps `0x0a0a0b` to 1/255 and Neutral to 0. For exact brand colours use no tone mapping and set
  the light levels so highlights do not clip; keep ACES when you want its highlight roll-off and do not need the exact black.
- **Make only the glow bloom.** A white label or code line at full intensity makes bloom veil the whole frame. Use HDR colours above 1 on the
  things that should glow (`color.multiplyScalar(2.2)` on the accent) and a bloom threshold of 1.0, so everything else stays clean.
- Rotate a **pivot group**, not a model whose origin is off-centre (it orbits instead of spinning), and frame the camera from the model's
  bounding box.

### Speed (measured, 1280x720, bloom on, 180 frames)

| Backend | Per frame |
|---|---|
| default: software WebGL (SwiftShader) | 133 ms |
| `--gpu auto` (picked Vulkan on the RTX 3060) | 66 ms |

The GPU is only about 2x faster because capturing and encoding the PNG dominates; a heavier scene or 4K widens the gap. Software is the default
because it runs anywhere and is the same on every machine. `--gpu off|auto|vulkan|egl` (or `CRAFTVIDEO_GPU`); `auto` tries Vulkan, then EGL, and
falls back to software with a message. **Render a whole video on one backend**: GPU and software rasterise antialiasing and floating point a
little differently, so a video mixing the two can shimmer at the join. The VoiceStudio voice engine and a GPU render compete for the same
12 GB card: finish narration first.

## Render options: workers, shutter blur, grain, preflight, layout lint

All on the `html` provider, all optional, none changes what you get by default (the default output is byte-identical to before they existed).

| Flag | What it does | Measured here |
|---|---|---|
| `--workers N` (or `auto`, env `CRAFTVIDEO_WORKERS`) | captures frames on N pages at once and writes them to ffmpeg in order; frames are pure functions of t, so the video is identical | a DOM scene, 640x360: 35 to 9 ms a frame with 4 workers, same frame hashes. A Three.js scene on software WebGL: no gain (162 against 156 ms; SwiftShader already uses every core inside one process), still identical. A real GPU was not tried |
| `--shutter 180 --subframes 8` | motion blur: renders 8 sub-frames across a 180 degree shutter and averages them per frame (ffmpeg `tmix`, 16-bit); a moment where nothing moves costs 2 captures, not 8; not with `--alpha` | a box moving 20 px a frame went from a crisp edge (2 grey levels on the row) to a soft one (16). The same trivial scene took 36 ms a frame without it, 67 with 4 sub-frames and 184 with 8 (a busy machine, so rough). Use it on short scenes with fast type or 3D, not on a whole long video |
| `--grain S` | luma film grain, a fixed seed, so a re-render is identical; not with `--alpha` | luma std is about S/3 of 255 and survives x264 at crf 14: 8 is subtle, 16 clearly visible |
| `--preflight 0` | skips the determinism preflight (five times forward, then backward; it also warns when the picture is identical at all five, which means `seek(t)` may be ignoring `t`) | on a scene that depended on how often `seek` was called it stopped before encoding, exit 4 |
| `--preflight-psnr 60` | keeps the preflight but forgives renderer noise: a revisit within 60 dB PSNR of the first visit passes (byte-exact otherwise) | p5.brush frames on the software renderer differ by a level in a pixel or two, about 100 dB apart (the mascot passes this flag); a moved object is 20 to 40 dB |
| `--lint 1` | no video: audits the layout and writes a JSON report, exit 1 on any error | below |

```bash
bash $S/render.sh work/scene.html work/lint.json --provider html --lint 1 --timeline work/timeline.json --width 1920 --height 1080 [--lint-step 0.5] [--band 0.18] [--min-size 0.025]
```
The audit seeks every `--lint-step` seconds (0.5), reads every text box from the DOM and reports what is **held** for 3 samples in a row (an entrance or an exit is motion, not a
fault):

| Rule | Severity | What it means |
|---|---|---|
| `frame` | error | text cut by the picture's edge |
| `clipped` | error | text cut by an ancestor with `overflow: hidden` |
| `overlap` | error | the text of two different elements on top of each other (over 20% of the smaller box) |
| `occluded` | error | text hidden behind another element with an opaque background (a 5 x 3 grid of hit tests inside the text; a translucent veil does not count) |
| `small` | warn | text under `--min-size` of the height as drawn (scale transforms are counted), default 2.5% |
| `band` | warn | text in the bottom `--band` (18%) that captions will cover |
| `contrast` | warn | text colour against the ground under it, below 3:1 (large text) or 4.5:1; sampled every 2 s by hiding every glyph, taking one screenshot and reading the pixels under each box |

Opt out on any ancestor: `data-cv-ignore` (skip), `data-cv-texture` (small text is meant: sources, footers), `data-cv-caption` (belongs in the caption band), `data-cv-layer` (may overlap).
The occlusion and contrast ideas follow what HyperFrames' `check` does (Apache-2.0; our code is separate and was written from a description of it).
It sees DOM text only: text drawn into a canvas, a WebGL texture or an image is invisible to it, so keep reading the contact sheets. Overlap is measured on the ink area (a line box carries
empty space above the capitals, so a big number directly under a small label would otherwise count as an overlap: the first version raised three false errors on real scenes). Tested: on the
repo's own examples it reports no errors; on a page with every fault planted it found all of them and nothing else (a slide-in during the first 0.4 s was correctly ignored as motion); on four
scenes of an 87 s video (Three.js plus HTML labels) it reported no errors and only true warnings (kickers, labels and a column of source lines at 1.6 to 2.4% of the height, source lines in the
caption band). The fifth scene needs WebGPU, which the test sandbox lacks. Warnings of the same kind in the same time range are printed as one line; the JSON report keeps every box.

## WebGPU / WGSL

Works in every mode (software through SwiftShader when there is no GPU), with three rules this setup taught:

- **Request the adapter explicitly.** On the hybrid-GPU machine this was built on, a bare `requestAdapter()` returned null. Ask for
  `{ powerPreference: "high-performance" }`, fall back to `{ forceFallbackAdapter: true }`.
- **Do not present to a canvas.** Headless Chromium does not give a WebGPU swap chain to the screenshot (the canvas reads back empty). Render into an
  offscreen texture, `copyTextureToBuffer`, map it and put the pixels into a 2D canvas, as `examples/webgpu-shader/scene.html` does.
- **Use an integer hash, not `fract(sin(...))`.** The sin() hash differs between the GPU and software paths (8/255 mean difference, visible tile
  artifacts); with an integer hash the two agree to 0.017/255 and 0 pixels differ by more than 8.

## img2threejs: a model from a picture

[img2threejs](https://github.com/img2threejs/img2threejs) (Apache-2.0) rebuilds the object in an image as a procedural, code-only Three.js model
(`createObjectModel.ts`), in gated passes with screenshot review. It does the modelling; CraftVideo plays the result.

1. In your project, run its pipeline from the checkout (OmniSkill's `img2threejs` skill routes to it; `IMG2THREEJS_HOME`, default `~/tools/img2threejs`).
   Say the cost first: upstream estimates 80k to 180k tokens for an object and 150k to 350k for a character, and a single image cannot show the
   hidden sides, so the result is stylised or guessed there. The TRELLIS reference step sends the image to a hosted Space: ask before using it on private images.
2. Bundle the factory: `bash $S/bundle.sh src/createObjectModel.ts model.js` (bun or esbuild; `three` stays a bare import, which the renderer resolves).
3. In a scene: `import { createXxxModel } from "./model.js"`, add the returned `THREE.Group` to a pivot, set its transforms from `t` in `seek`.

`examples/img2threejs-bridge/` does steps 2 and 3 end to end. **It is a plumbing demo, not a reconstruction**: `make_model.sh` calls the generator as a
Python function, the way upstream's own tests do, which **skips its quality gate** on purpose. The real CLI refuses the toy two-box spec in the
example (strict quality wants colour recipes, lighting, local overrides) and writes a BLOCKED artifact, which is correct behaviour. `model.ts` and
`model.js` are generated and git-ignored (the generated source carries upstream's Apache-2.0 template text); run `make_model.sh` first.

## Overlays on an edited recording

```bash
bash $S/render.sh lowerthird.html lowerthird.mov --provider html --width 1920 --height 1080 --fps 30 --duration 3 --alpha 1
# edit.json:  "overlays": [ { "type": "clip", "file": "/abs/lowerthird.mov", "start": 2.0, "x": 0, "y": 0 } ]
bash $S/edit.sh edit.json the-video-title.mp4 --title "The Video Title"
```

`--alpha 1` makes the page background transparent and encodes ProRes 4444 (so the output must be a `.mov`); the dispatcher refuses it for providers
that cannot do alpha. A scene sees `window.__CV_SPEC.alpha` and should then draw no background. Render the overlay at the **output** size and fps. In the edit it sits above the graded footage and below the captions
(so keep lower thirds out of the bottom 20%), starts playing at `start` (output seconds), and disappears when it ends or at `end`. Tested here:
a card with real alpha (255 on the card, 0 around it) composited over an edited recording, absent before its start and after its end; and the
3D cartridge scene rendered with `--alpha 1` (87% of pixels transparent, solid object, antialiased edges) composited the same way, under the captions.
`examples/three-3d/scene.html` shows the pattern: in alpha mode it skips the background, fog, grid and UI, and **renders directly instead of through the
composer**, because the bloom and output passes write an opaque alpha (the first try came out 100% opaque).

## A longer video from several scenes (lessons from a 90-second one)

A single page is fine for 20 seconds. For a minute or more, make **one HTML file per beat** and join the renders:

- `beats.json` (written from `timeline.json`): each scene's `t0` and length on **whole frames** (`round(start x fps)`), with a short lead-in before the first cue of the beat.
  Scenes read it through a two-line `beat("name")` helper and time everything as `at("cue") - t0`, so a re-timed narration needs no scene edits.
- Keep every on-screen string, number and source in **one `facts.json`** that the scenes load. Wording and sourcing changes then never touch scene code.
- Put the same wipe (a pink bar in the last and first 0.3 s) in every scene; it hides the cut. Join with `ffmpeg -f concat -c copy` and check the frame total.
- Chapter stamps are small **transparent overlays** (ProRes 4444) composited by the edit step, together with the captions and MP4 chapters. Leave the bottom 18% free for captions.
- Share the 3D pieces as modules (a globe, a city, a padlock) with an `update(t, params)` function; a scene only picks camera keyframes and what turns on when.

Things that went wrong, so they need not again:
- **`ShaderMaterial` output is linear and the output pass sRGB-encodes it.** A "dark" `0.045` came out mid-grey; near-black wants about `0.004`. Fade distant geometry to the background in the shader, since scene fog does not reach it.
- **Do not feed an interpolated varying into a `sin()` hash.** A per-building seed that differs by 1e-6 between pixels became visible grain in every window; round it to an integer in the vertex shader.
- **Pixel-wide lines are too thin at 1080p.** `Line2` (from `three/addons/lines`) with a `linewidth` in pixels gives arcs that read; animate them with `geometry.instanceCount`.
- **A dense procedural city hides everything inside it.** For a shot that must show cones, people or a route, lower the towers and clear a plaza along the path, and align the path to real street centres (the walker first went through buildings).
- **Check each scene as a contact sheet at final resolution before the full render.** Four of the five scenes had a layout fault (text overlapping, a card overflowing, a stat colliding with a stamp) that no single frame in the test had shown.

## Which Chromium

The renderer prefers a full system Chromium (`CRAFTVIDEO_CHROMIUM`, `/usr/bin/chromium`, `google-chrome-stable`) and falls back to Playwright's
bundled one. The bundled headless shell has **no WebGPU**; the system one does, and also plays proprietary codecs. `preflight.sh` says which it will use.
