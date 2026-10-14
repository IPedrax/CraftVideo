# vector-svg

`scene.html` is a vector scene written for `seek(t)`: a chart whose axes and curve draw themselves (`stroke-dashoffset` on a `pathLength` 1 path), markers that pop with a spring when the line reaches them, a
packet that rides the curve, a circle that morphs into a square, a star and back (equal arc-length samples, outlines turned the same way round), a ball with squash and stretch, and a caption that types in.
`loader.svg` is an animated SVG written for this suite (a SMIL ring and dots, a CSS pulse) to try `vector.sh` on. Read `reference/vector-animation.md` first.

```bash
S=../../scripts
bash $S/render.sh scene.html out.mp4 --provider html --width 1920 --height 1080 --fps 30 --duration 8 [--look whiteboard]       # colours follow the look
bash $S/render.sh scene.html lint.json --provider html --lint 1 --width 1920 --height 1080 --duration 8                      # 0 errors, 0 warnings
bash $S/vector.sh loader.svg loader.mp4 --width 1920 --height 1080 --duration 4                                              # an animated SVG, moved by the frame's time
bash $S/vector.sh loader.svg overlay.mov --alpha 1 --width 1920 --height 1080 --duration 4 --fit contain                      # transparent, for an overlays clip
```
Measured: 62 ms a frame at 1080p on the CPU; the scene is byte-identical between visits with the renderer's `--disable-partial-raster`, and the loader's SMIL is identical while its CSS pulse differs by a
sub-pixel (so `vector.sh` runs that preflight at 40 dB). A Lottie file was not tried: lottie-web is not shipped.
