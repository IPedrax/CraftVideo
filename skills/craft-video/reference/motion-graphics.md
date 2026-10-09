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
| Seeded generative art (p5.js), a logo or its animation | the OmniSkill `algorithmic-art` / `logo-design` skills make the assets, the scene plays them | Possible: not wired or run here |
| After Effects-style compositions with 306 effects | the `effectcraft` provider | Proven (the first video) |
| Interface sound for the shot | OmniSkill `uisfx` (synthesised locally), mixed in with `music` or the editor | Possible: not run here |

OmniSkill's `motion-ui` picks between Framer Motion, GSAP, anime.js and Three.js for an interface; here the decision is the same, only the
output is frames instead of a page. Its `vgpu` skill (Vercel's WebGPU wrapper) is Possible but untried: the raw WebGPU example shows the
rules any WebGPU code must follow here.

## The rule for everything: a frame is a pure function of t

`window.craftvideo.seek(t)` must draw the same pixels every time it is called with the same `t`, whatever was drawn before. No clock, no
`requestAnimationFrame` loop, no `Math.random` (use a seeded generator), no animation left running on its own. The renderer checks this:
after the last frame it seeks to 0 again and compares with the first frame, and prints a `WARNING` if they differ.
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
bash $S/edit.sh edit.json edited.mp4
```

`--alpha 1` makes the page background transparent and encodes ProRes 4444 (so the output must be a `.mov`); the dispatcher refuses it for providers
that cannot do alpha. A scene sees `window.__CV_SPEC.alpha` and should then draw no background. Render the overlay at the **output** size and fps. In the edit it sits above the graded footage and below the captions
(so keep lower thirds out of the bottom 20%), starts playing at `start` (output seconds), and disappears when it ends or at `end`. Tested here:
a card with real alpha (255 on the card, 0 around it) composited over an edited recording, absent before its start and after its end; and the
3D cartridge scene rendered with `--alpha 1` (87% of pixels transparent, solid object, antialiased edges) composited the same way, under the captions.
`examples/three-3d/scene.html` shows the pattern: in alpha mode it skips the background, fog, grid and UI, and **renders directly instead of through the
composer**, because the bloom and output passes write an opaque alpha (the first try came out 100% opaque).

## Which Chromium

The renderer prefers a full system Chromium (`CRAFTVIDEO_CHROMIUM`, `/usr/bin/chromium`, `google-chrome-stable`) and falls back to Playwright's
bundled one. The bundled headless shell has **no WebGPU**; the system one does, and also plays proprietary codecs. `preflight.sh` says which it will use.
