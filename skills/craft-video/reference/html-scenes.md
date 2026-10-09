# HTML scenes (the `html` render provider)

Anything a browser can draw becomes video: HTML, CSS, SVG, canvas, WebGL, a React or Tailwind build. Headless Chromium loads your
page, the renderer calls `seek(t)` for every frame, screenshots it, and ffmpeg encodes the frames. This is brag's own route.

```bash
bash scripts/render.sh scene.html out.mp4 --provider html --timeline timeline.json --width 1920 --height 1080 --fps 30 --duration 30
bash scripts/render.sh scene.html x.png  --provider html --timeline timeline.json --stills "1.4 8.9 17.9" --sheet sheet.png   # review
```

## The whole contract

Your page defines `window.craftvideo.seek(t)` (seconds). It must make the DOM **a pure function of t**, and may return a promise
(the renderer waits for it, and for `document.fonts.ready`).

```html
<script>
  const spec = window.__CV_SPEC;                 // {width, height, fps, duration, timeline} injected before your page loads
  window.craftvideo = { seek(t) { /* set styles from t only */ return document.fonts.ready; } };
</script>
```

`spec.timeline` is the narration's `timeline.json` (`sentences[]` with `label`, `start`, `end` in seconds), so scenes follow words:
read the cues and animate from them (`examples/html-hello/scene.html` does exactly this).

## Rules that make frames correct

- **Nothing may depend on wall-clock time.** No `setTimeout`, `requestAnimationFrame` loops, `Date.now()`, or CSS animations left to
  run on their own. Every frame is drawn after one `seek(t)`; whatever the page was doing in between is irrelevant.
- **CSS animations and transitions are fine if you take them over:** `for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; }`
  (`examples/html-css-animation/scene.html`, tested: the animations report exactly the time you set).
- Individual CSS transform properties (`translate`, `rotate`, `scale`) apply in that order, before `transform`. Mixing `rotate` with a
  `transform: translateX()` slides along the rotated axis: use `translate` for the slide.
- **Size with `vw`/`vh`**, not px, so the same scene renders at 1920x1080, 1080x1920 or 1080x1080. Re-check each aspect ratio in stills.
- **Fonts:** installed system fonts work by family name (`'Big Shoulders Display'`). For anything portable, ship `@font-face` files next to the page.
- **Assets** (images, fonts, scripts) must be local files; the page is opened from `file://`. Wait for images in the promise you return.
- Canvas and WebGL are fine: draw from `t` inside `seek`. Avoid `<video>` elements for footage (seeking is not frame-exact in a headless page);
  pre-extract frames or compose the footage in the editor stage instead.
- Output is PNG screenshots piped to ffmpeg (`libx264`, crf 14, yuv420p). Measured on the simple example scene: about 33 ms per frame at 720p and
  54 ms at 1080p after a ~1.5 s browser start, so a 30 s 1080p video is about a minute. Heavy pages (WebGL, large images, many filters) take longer.

## Provider settings

`PLAYWRIGHT_DIR` (a `node_modules` containing `playwright`, default: the VoiceStudio checkout's), `CRAFTVIDEO_CHROMIUM` (a Chromium or
Chrome binary; falls back to `/usr/bin/chromium` and `google-chrome-stable`). `providers.sh list` shows whether it is usable and why not.
