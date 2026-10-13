# HTML scenes (the `html` render provider)

Anything a browser can draw becomes video: HTML, CSS, SVG, canvas, WebGL, WebGPU, Three.js, GSAP, a React or Tailwind build. Headless Chromium
loads your page, the renderer calls `seek(t)` for every frame, screenshots it, and ffmpeg encodes the frames. This is brag's own route.
3D, shaders, GPU rendering and transparent overlays are in `motion-graphics.md`.

```bash
bash scripts/render.sh scene.html out.mp4 --provider html --timeline timeline.json --width 1920 --height 1080 --fps 30 --duration 30
bash scripts/render.sh scene.html x.png  --provider html --timeline timeline.json --stills "1.4 8.9 17.9" --sheet sheet.png   # review
bash scripts/render.sh scene.html out.mov --provider html --width 1920 --height 1080 --fps 30 --duration 3 --alpha 1            # transparent overlay
```

## The whole contract

Your page defines `window.craftvideo.seek(t)` (seconds). It must make the DOM **a pure function of t**, and may return a promise
(the renderer waits for it, and for `document.fonts.ready`).

```html
<script>
  const spec = window.__CV_SPEC;                 // {width, height, fps, duration, timeline, alpha} injected before your page loads; alpha = draw no background
  window.craftvideo = { seek(t) { /* set styles from t only */ return document.fonts.ready; } };
</script>
```

`spec.timeline` is the narration's `timeline.json` (`sentences[]` with `label`, `start`, `end` in seconds), so scenes follow words:
read the cues and animate from them (`examples/html-hello/scene.html` does exactly this).

**Land on a word inside a sentence** (a count-up that finishes on "45%", a reveal on "padlock") with anchors. List them in `work/anchors.txt`, one per line, written the way the transcript
spells the words (`name | 6 billion people`, or a range `name | the padlock .. closes`, with `#2` after a phrase heard twice), then:
```bash
bash $S/transcribe.sh work/narration.wav work/narration_transcript.json --language en       # the FINAL narration, so the times match the video
python3 $S/anchors.py --anchors work/anchors.txt --transcript work/narration_transcript.json --timeline work/timeline.json     # --words prints the transcript to write against
```
`timeline.json` gains `"moments": {"people": {"start": 5.36, "end": 6.28}}`, and a scene reads `spec.timeline.moments.people.start` (a count-up can finish at `.end`) and adds its own 0.1 to 0.3 s lead.
A phrase that is heard twice, or not at all, stops the script with the times or the nearest words, and nothing is written. A new voice means transcribing and running it again: every moment moves,
no scene is edited. (The idea of anchoring to words is Hypit's, source-available, ideas only; this is our own, tested on a hand-made transcript and on The Connected City's real one.)

**Looks.** `--look NAME` (`looks/*.json`, `looks/README.md`) injects the colour and type roles as CSS variables (`var(--cv-ink, #f2f2f0)`, `var(--cv-display-size, 9vh)`) and as `spec.look`, so one scene can
take nine art directions; `examples/looks-demo/scene.html` is built that way and `scripts/check_looks.py` validates a look.

## Rules that make frames correct

- **The renderer checks this rule.** Before encoding, a preflight visits five times forward and then backward and exits with code 4 if any frame differs
  the second time; after the last frame it seeks to 0 again and prints a `WARNING` if the first frame changed. Either means the scene
  depends on history (a timer, an unseeded random, an animation clock, state built up frame by frame, or renderer state), and the frames are not what you previewed.
- **Lay text out so the layout lint passes** (`render.sh scene.html report.json --provider html --lint 1`, `reference/motion-graphics.md`): no text cut by the frame or by an
  `overflow:hidden` box, no two elements' text on top of each other, nothing meant to be read under 2.5% of the height, nothing in the bottom 18% when captions will be burned,
  contrast of at least 3:1. Mark exceptions on the element: `data-cv-texture` (a source line, small on purpose), `data-cv-caption`, `data-cv-layer` (may overlap), `data-cv-ignore`.
- **Nothing may depend on wall-clock time.** No `setTimeout`, `requestAnimationFrame` loops, `Date.now()`, or CSS animations left to
  run on their own. Every frame is drawn after one `seek(t)`; whatever the page was doing in between is irrelevant.
- **CSS animations and transitions are fine if you take them over:** `for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; }`
  (`examples/html-css-animation/scene.html`, tested: the animations report exactly the time you set).
- Individual CSS transform properties (`translate`, `rotate`, `scale`) apply in that order, before `transform`. Mixing `rotate` with a
  `transform: translateX()` slides along the rotated axis: use `translate` for the slide.
- **Size with `vw`/`vh`**, not px, so the same scene renders at 1920x1080, 1080x1920 or 1080x1080. Re-check each aspect ratio in stills.
- **Fonts:** installed system fonts work by family name (`'Big Shoulders Display'`). For anything portable, ship `@font-face` files next to the page.
- **Assets** (images, fonts, scripts, GLB models) are served from your scene's folder (`--root DIR` widens it) on a private origin,
  `http://cv.local`, so ES modules, import maps and `fetch()` work, and `three` resolves when `scripts/get_three.sh` has installed it. Keep assets
  local: a page that loads from the internet is not reproducible. Wait for images in the promise you return.
- Canvas, WebGL and WebGPU are fine: draw from `t` inside `seek` (see `motion-graphics.md` for the traps). Avoid `<video>` elements for footage (seeking is not frame-exact in a headless page);
  pre-extract frames or compose the footage in the editor stage instead.
- Output is PNG screenshots piped to ffmpeg (`libx264`, crf 14, yuv420p). Measured on the two simple example scenes: about 37 ms per frame at 720p and
  67 to 76 ms at 1080p after a ~1.5 s browser start, so a 30 s 1080p video is 1 to 1.5 minutes. Heavy pages (WebGL, large images, many filters) take longer.
  `--workers 4` captures on four pages at once and cut a DOM scene from 35 to 9 ms a frame with identical output; `--shutter` and `--grain` are in `motion-graphics.md`.

## Provider settings

`PLAYWRIGHT_DIR` (a `node_modules` containing `playwright`, default: the VoiceStudio checkout's), `CRAFTVIDEO_CHROMIUM` (a Chromium or
Chrome binary; tried first, then `/usr/bin/chromium`, `google-chrome-stable`, and last Playwright's bundled browser, which has no WebGPU),
`CRAFTVIDEO_GPU` (`off` default, `auto`, `vulkan`, `egl`; same as `--gpu`), `THREE_DIR` (where three.js is installed, default
`~/.local/share/craftvideo/three`). `providers.sh list` shows whether the provider is usable and why not.
