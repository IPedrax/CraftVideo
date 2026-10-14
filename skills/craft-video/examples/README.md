# Examples

Each folder renders with the commands shown (`S` is `skills/craft-video/scripts`). All of them were rendered and looked at.

| Folder | What it shows | Needs |
|---|---|---|
| `decomp-30s/` | the first full video: script, cues, EffectCraft scenes, FilmCraft mix | EffectCraft, FilmCraft, VoiceStudio (see its README) |
| `html-hello/` | the smallest HTML scene driven by narration cues | the `html` provider |
| `html-css-animation/` | CSS keyframes taken over and driven by `seek(t)` | the `html` provider |
| `three-3d/` | a procedural 3D cartridge, particles that sort into source lines on a cue, bloom, a camera keyed to the cues | three.js (`get_three.sh`) |
| `img2threejs-bridge/` | an img2threejs-generated model played in a scene (a **plumbing demo**: its quality gate is skipped on purpose) | three.js, bun or esbuild, an img2threejs checkout |
| `webgpu-shader/` | a WGSL shader as a background, read back to a 2D canvas | the `html` provider with a system Chromium |
| `gsap-timeline/` | a GSAP timeline on cues: staggered type, a counter, an SVG rule drawing | GSAP (`gsap.min.js` next to the scene, not shipped) |
| `overlay-lowerthird/` | a transparent lower third (ProRes 4444) to composite onto an edited recording | the `html` provider |
| `looks-demo/` | one scene styled only by the variables a look injects (`--look NAME`): the same frame in nine art directions | the `html` provider |
| `mascot/` | Clawd, the Claude Code mascot, walking on, reacting to named words with acted faces and walking off: a cue file against `moments`, rendered as a transparent overlay and laid over a picture | the mascot kit (`get_mascot.sh`), the `html` provider |
| `clips/` | long recording to shorts: a made-up talk's transcript, the candidates the script proposes, and the picks a person wrote from them; runs with no recording | python3 (numpy for `--audio`) |
| `vector-svg/` | a vector scene as pure functions of t (draw-on, spring pops, a morph between any two outlines, a packet on a path, squash and stretch) and `loader.svg` to play with `vector.sh` | the `html` provider |
| `pixel-art/` | a 16-colour pixel-art scene: a robot from an Aseprite-style sheet, stepped time, hit-stop and shake, palette cycling, crisp text, a Bayer dissolve; `qa_pixels.py` proves it pixel-exact | the `html` provider, Pillow (`make_sprites.py`) |
| `continuous-camera/` | a one-take video: four beats are stations in one world, one camera travels between them keyed from the cues (log zoom, parallax, a carrier dot and a drawn route instead of a wipe) | the `html` provider |

## Commands

```bash
# 3D (once: bash $S/get_three.sh /path/to/node_modules/three)
bash $S/render.sh three-3d/scene.html out.mp4 --provider html --timeline three-3d/timeline.json --width 1280 --height 720 --fps 30 --duration 6 --gpu auto

# img2threejs bridge (make_model.sh generates and bundles the model; model.ts and model.js are git-ignored)
bash img2threejs-bridge/make_model.sh
bash $S/render.sh img2threejs-bridge/scene.html out.mp4 --provider html --timeline img2threejs-bridge/timeline.json --width 1280 --height 720 --fps 30 --duration 6

# WebGPU shader (works on the GPU or in software)
bash $S/render.sh webgpu-shader/scene.html out.mp4 --provider html --timeline webgpu-shader/timeline.json --width 1280 --height 720 --fps 30 --duration 6 --gpu auto

# GSAP (npm i gsap, copy node_modules/gsap/dist/gsap.min.js into gsap-timeline/)
bash $S/render.sh gsap-timeline/scene.html out.mp4 --provider html --timeline gsap-timeline/timeline.json --width 1280 --height 720 --fps 30 --duration 6

# a transparent overlay, then use it in an edit (see edit-snippet.json for the overlays entry)
bash $S/render.sh overlay-lowerthird/scene.html lowerthird.mov --provider html --width 1280 --height 720 --fps 30 --duration 3 --alpha 1
# the 3D cartridge on a transparent background, to float over footage (960x540 here, placed with x and y in the overlay entry)
bash $S/render.sh three-3d/scene.html cart.mov --provider html --timeline three-3d/timeline.json --width 960 --height 540 --fps 30 --duration 3 --alpha 1
```

# the same scene in a look (ten in ../looks), then the layout lint under that look
bash $S/render.sh looks-demo/scene.html out.mp4 --provider html --width 1920 --height 1080 --fps 30 --duration 4 --look dark-keynote
bash $S/render.sh looks-demo/scene.html lint.json --provider html --width 1920 --height 1080 --duration 4 --look dark-keynote --lint 1

# one camera through four beats (a DOM scene: --workers 3 renders it about three times as fast; the identical video)
bash $S/render.sh continuous-camera/scene.html out.mp4 --provider html --timeline continuous-camera/timeline.json --width 1920 --height 1080 --fps 30 --duration 14 --workers 3
```

# the mascot (once: CRAFTVIDEO_ALLOW_DOWNLOAD=1 bash $S/get_mascot.sh): a labelled review sheet first, then the clip laid over a picture that has sound
bash $S/mascot.sh mascot/mascot.json out.mov --timeline mascot/timeline.json --sheet sheet.png
bash $S/mascot.sh mascot/mascot.json clawd.mov --timeline mascot/timeline.json --width 1920 --height 1080 --fps 30 --workers auto --over picture.mp4 --into picture-clawd.mp4
```

Review stills first, as always: add `--stills "0.3 1.5 3.0 4.8" --sheet sheet.png` instead of a duration to get a contact sheet.

## What they proved (measured here)

- `three-3d`: renders on the software rasteriser at 133 ms per frame and on the GPU at 66 ms (1280x720, bloom on); frames pass the determinism check.
- `webgpu-shader`: GPU and software WebGPU frames agree to 0.017/255 mean difference (no pixel differs by more than 8).
- `overlay-lowerthird`: alpha is real (255 on the card, 0 around it), and composited over an edited recording it appears at its start time and is gone after its end.
- `three-3d` with `--alpha 1`: 87% of pixels transparent, composited over an edited recording under the captions.
- `img2threejs-bridge`: the generator's TypeScript bundles in 30 ms and plays in a scene. It does not show a real reconstruction.
- `gsap-timeline`: tested with GSAP 3.15.0 from a local copy; GSAP's licence is its own, so the library is not bundled.
- `looks-demo`: rendered in all nine looks and tiled; the lint found, in the first draft of the Swiss look, a sentence running off the frame (a 7% statement size used as body text), which is why that look now has a separate `statement` role. Lints clean under all nine.
- `continuous-camera`: 420 frames, deterministic across 3 workers, lint clean. The picture gate still lists the holds as "barely changing": the push-in during a hold is 5% of zoom over about 3 s, which is below its 0.5/255 per-frame threshold by definition (a slow push is a living camera to the eye and a still one to that gate).
