# Vector animation (SVG and friends)

Vector motion graphics are the `html` provider's home ground: an SVG in a page that `seek(t)` sets from t, rendered at any size with no loss. This file is what to write and what to
trust. Two routes: **write a scene** (you control every frame, the best way) and **play an asset** somebody else animated (`vector.sh`). Eases and the closed-form spring are in
`reference/visual-craft.md`; the `seek(t)` contract and the lint are in `reference/html-scenes.md` and `reference/motion-graphics.md`. Researched 2026-10-13 (sources at the end); every
number marked "measured" was run on this machine.

| Format | Here | Notes |
|---|---|---|
| a scene written for `seek(t)` (SVG in HTML) | **Proven**: `examples/vector-svg/scene.html` | draw-on, spring pops, a morph between any two outlines, a packet on a path, squash and stretch, typed text: 0 lint errors, byte-exact preflight |
| animated SVG with SMIL (`<animate>`, `<animateTransform>`) | **Proven**: `vector.sh asset.svg out.mp4` | `setCurrentTime()` moves it; measured byte-identical between visits (0 differing pixels in 6 runs) |
| animated SVG with CSS animations or Web Animations | **Proven with a tolerance**: same command | the page sets every animation to the frame's time; a transform animation can differ by a sub-pixel between visits (measured 679 edge pixels, 49 dB), so `vector.sh` runs the preflight at 40 dB for it |
| Lottie / Bodymovin JSON | not built (needs a download) | lottie-web (MIT, 168 to 243 KB in one file) seeks with `goToAndStop(frame, true)`; see "Lottie" below |
| dotLottie (.lottie), Rive (.riv), Skottie | not built | each needs a WASM runtime and its own seek; the research says how, nothing was run |

## Write a scene

Everything below is in `examples/vector-svg/scene.html` (render it: `bash $S/render.sh scene.html out.mp4 --provider html --width 1920 --height 1080 --duration 8`; it takes `--look NAME`).
Inside `seek(t)` set attributes from t and nothing else. The recipes, with the traps each one hit:

- **Draw-on.** `pathLength="1"`, `stroke-dasharray: 1 1.001`, `stroke-dashoffset: 1 - p`. Hide the path while p is 0: a round cap can leave a dot there (engines differ). Do not combine it with
  `vector-effect: non-scaling-stroke` (how dashes behave under it is an open SVG working-group question).
- **Pops with a spring.** `scale(spring(t - t_i))` on a marker that has `transform` set, where t_i is the time the line reaches it. Measure the reach once at load: build each cubic
  segment's prefix as its own path, take `getTotalLength()`, divide by the total. One spring per film (visual-craft).
- **Morph between any two closed outlines.** Sample both at N equal arc-length steps with `getPointAtLength` (N = 120 is smooth), **make both run the same way round** (flip a path whose signed
  area is negative), rotate B's start to the offset that minimises the squared distance to A, then blend point by point and write `d` as a polyline. Skip the orientation step and the shape
  twists halfway (it did: a star turning into a circle came out as a ribbon). Chain the shapes, aligning each to the one before it. For equal command lists the browser can interpolate
  `d: path()` itself (Chrome 52+), but the sampling route is pure and accepts arcs, lines and curves mixed. Holes and several sub-paths are not handled.
- **Ride a path.** `getPointAtLength(p * total)` for the position and a second sample 1 unit ahead for the heading. (`offset-path` with `offset-rotate: auto` does the same in CSS.)
- **Squash and stretch.** `scale(1/s, s)` keeps the volume; squash only within about 70 ms of a contact, stretch with speed; put the shadow's width on the height. Set `transform-box: fill-box;
  transform-origin: center` on anything scaled in CSS: an SVG element's origin is the viewBox corner otherwise.
- **Stagger and loops.** `local = clamp((t - i * step) / dur, 0, 1)`. A loop is a periodic function of `(t mod T) / T`, so render `T * fps` frames and the seam is never doubled.
- **Text.** SVG `<text>` works (set `color` as well as `fill: currentColor`, because the layout lint reads `color` and SVG paints `fill`). For a stroke write-on, or to be independent of the installed font,
  turn the text into outlines first (opentype.js, MIT: `font.getPath(...).toPathData()`).
- **Lines and edges.** Keep strokes 2 px or more at 1080p: a hairline under one device pixel flickers as it moves. Leave `shape-rendering` at its default: `crispEdges` snaps and shimmers.
  Filters (blur, turbulence) are deterministic but slow on the CPU: bake a blur as a few translucent shapes where you can.

## Play an asset: `vector.sh`

```bash
bash $S/vector.sh loader.svg out.mp4 --width 1920 --height 1080 --fps 30 --duration 4            # on its own background
bash $S/vector.sh loader.svg overlay.mov --alpha 1 --duration 4 --width 1920 --height 1080     # transparent, ProRes 4444: an `overlays` clip in edit.json, or edit.sh's overlay graph
bash $S/vector.sh loader.svg out.mp4 --period 2 --duration 8 --speed 1.5 --fit cover           # loop every 2 s of the asset, play it at 1.5x, fill the frame
```
The SVG is inlined in `vector/player.html` (after removing `<script>`, `on*` handlers and http(s) links, so nothing loads from the network and nothing keeps its own clock). SMIL goes through
`svg.pauseAnimations(); svg.setCurrentTime(t)`; CSS and Web Animations are paused and set to `t * 1000` ms. The animation list is taken once at load, because a finished animation without a fill leaves
`document.getAnimations()` and a later visit to an earlier time would miss it. The page reports it when the asset has no animation at all (the video would be a still) or SMIL did not move to t.
`examples/vector-svg/loader.svg` is a test asset written for this suite (SMIL ring and dots, a CSS pulse).

## Traps found and measured

- **Partial raster.** Chromium re-rasterises only the invalidated part of a tile, and a path drawn that way can differ from a full raster of the same DOM by a few anti-aliasing levels: the vector
  scene failed its own byte-exact preflight (33 pixels up to 69 levels on a circle's edge, the same DOM, two visits). The renderer now launches Chromium with `--disable-partial-raster`, and every
  revisit of the scene is byte-identical at the same speed (62 ms a frame at 1080p).
- **CSS and Web Animations on transforms are not byte-exact between visits** even with that flag, with compositor animations off, or with GPU compositing off: the computed transform was identical and
  the circle's coverage differed in 679 pixels (0.05 px sub-pixel shift, 49 dB). SMIL and attribute-driven scenes do not have this. Prefer writing the animation in `seek(t)`; when an asset
  carries CSS animations, `vector.sh` accepts a revisit within 40 dB.
- **GSAP and anime.js** seek fine (`tl.time(t)`; anime.js 4.5+ `seek(ms)` on a paused timeline, because seeking a running timer resumes it). Set `gsap.defaults({ lazy: false })`, and give random values a seed:
  parallel workers visit frames in different orders, so a random drawn at first render would differ per worker.
- **A script inside an asset** (an exporter's embedded player, a `requestAnimationFrame` loop) keeps its own clock; the preflight refuses it (exit 4).

## Design numbers

From the sources below; where a number is mine it says so. Durations: 100 to 500 ms is the UI range (NN/g), entrances a little longer than exits (300 against 200 to 250); Material 3 uses 250 to 300 ms
for transitions and 75 to 150 for fades. Video has no rewind, so sit in the upper half of that range. Easing (Material 3): standard `cubic-bezier(0.2, 0, 0, 1)`, emphasized decelerate
`(0.05, 0.7, 0.1, 1)` for entrances, emphasized accelerate `(0.3, 0, 0.8, 0.15)` for exits; linear only for spinners and endless loops. Springs: Apple's mapping from (duration, bounce) is mass 1,
stiffness `(2 pi / duration)^2`, damping `4 pi (1 - bounce) / duration`, so the damping ratio is `1 - bounce`; bounce 0.15 is brisk and overshoots 0.6% (my calculation), 0.3 is noticeable
(4.6%), above 0.4 is too much for UI. Overshoot position, scale and rotation, never opacity or colour. Stagger: 50 to 100 ms between siblings in UI (Adobe XD), 3 to 5 frames in motion graphics
(`reference/visual-craft.md` has the film numbers). Cheap-looking vector motion is: linear easing everywhere, the wrong ease direction, everything moving at once, nothing settling, dead holds
(keep a slight drift), hairlines, mixed caps and joins.

## Lottie

Not shipped, because lottie-web is a download and animation files are other people's work. What the research found, for when it is added: lottie-web 5.13.0 (MIT, last release 2024-11-19, still
maintained) in one file (`lottie_svg.min.js` 243 KB, `lottie_light.min.js` 168 KB: SVG only, no expressions or effects); `loadAnimation({ container, renderer: "svg", autoplay: false, loop: false, animationData })`
then `goToAndStop(frame, true)` (frames, not milliseconds, which are scaled by the play speed); load fonts first; expressions can be non-deterministic (Remotion says so), so lint a file for expressions,
3D layers, unsupported effects, missing fonts and images before rendering it. dotLottie (a zip with `manifest.json`) would be unzipped first.

## Licences of animation files (not legal advice)

Fetch, never commit: LottieFiles (Simple License: no standalone redistribution, derivatives under the same terms), Lordicon (CC BY-ND 4.0 base, attribution), IconScout (no redistribution, even free),
Rive Marketplace (CC BY, embedded fonts and images may differ). Committable with a notice: SVG Spinners (MIT). Code: lottie-web, dotlottie-web, ThorVG, rive-wasm, anime.js, Flubber and opentype.js
are MIT; GSAP is free including MorphSVG since 3.13 but under its own licence (it bars building a competing visual animation builder), so it is installed, not shipped.

## Not tested

A Lottie file, dotLottie, Rive, Skottie; GSAP MorphSVG; very large SMIL files; SVG filters at length; a real GPU; assets exported by commercial tools with their own players.

## Sources

- Durations and easing: https://www.nngroup.com/articles/animation-duration/ · Material 3 tokens https://raw.githubusercontent.com/material-components/material-components-android/master/docs/theming/Motion.md · Apple springs https://developer.apple.com/videos/play/wwdc2023/10158/ and https://developer.apple.com/documentation/swiftui/spring
- Seeking: https://developer.mozilla.org/en-US/docs/Web/API/SVGSVGElement/setCurrentTime · https://developer.mozilla.org/en-US/docs/Web/API/Document/getAnimations · Blink's SMIL clock https://chromium.googlesource.com/chromium/src/+/refs/heads/main/third_party/blink/renderer/core/svg/animation/smil_time_container.cc
- Lottie: https://raw.githubusercontent.com/airbnb/lottie-web/master/player/js/animation/AnimationItem.js · https://www.remotion.dev/docs/lottie · flicker and seeking in parallel renders https://www.remotion.dev/docs/flickering · a seek-adapter design for the same problem, https://github.com/heygen-com/hyperframes (Apache-2.0)
- Dashes under non-scaling-stroke: https://github.com/w3c/svgwg/issues/323 · morphing https://github.com/veltman/flubber (MIT) · text as outlines https://github.com/opentypejs/opentype.js (MIT)
- Licences: https://lottiefiles.com/page/license · https://lordicon.com/licenses · https://iconscout.com/licenses · https://rive.app/docs/community/marketplace-overview.md
