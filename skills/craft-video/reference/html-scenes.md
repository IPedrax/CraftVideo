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

## Rules that make frames correct

- **The renderer checks this rule.** After the last frame it seeks to 0 again and compares with the first frame; a `WARNING` means the scene
  depends on history (a timer, an unseeded random, an animation clock, or renderer state), and the frames are not what you previewed.
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

## Provider settings

`PLAYWRIGHT_DIR` (a `node_modules` containing `playwright`, default: the VoiceStudio checkout's), `CRAFTVIDEO_CHROMIUM` (a Chromium or
Chrome binary; tried first, then `/usr/bin/chromium`, `google-chrome-stable`, and last Playwright's bundled browser, which has no WebGPU),
`CRAFTVIDEO_GPU` (`off` default, `auto`, `vulkan`, `egl`; same as `--gpu`), `THREE_DIR` (where three.js is installed, default
`~/.local/share/craftvideo/three`). `providers.sh list` shows whether the provider is usable and why not.
