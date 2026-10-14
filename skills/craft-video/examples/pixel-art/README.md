# pixel-art

A 16-colour scene drawn at 320 x 180 and shown at scale 6: a Bayer-dithered sunset, a robot read from an Aseprite-style sprite sheet (idle, walk, hurt), a world that steps 8, 6 and 3 times a second, a hit-stop
and a decaying shake on a cue, a palette-cycled water strip, crisp 1-bit text typed in, and a dissolve at the end. Read `reference/pixel-art.md` first: it says why the scale is even, why the frame rate is 24, and
what the gate measures.

```bash
S=../../scripts
python3 make_sprites.py                    # once: writes sheet.png and sheet.json here (git-ignored); an export from Aseprite goes in their place (--format json-array)
bash $S/render.sh scene.html out.mp4 --provider html --width 1920 --height 1080 --fps 24 --duration 8
python3 $S/qa_pixels.py out.mp4 --scale 6 --palette pico8        # PASS: the blocks are one colour and the colours are PICO-8's
bash $S/render.sh scene.html out.mp4 --provider html --width 1080 --height 1920 --fps 24 --duration 8                  # the same scene at 180 x 320
bash $S/render.sh scene.html out.mp4 --provider html --width 1920 --height 1080 --fps 24 --look pixel-art              # the look supplies the scale and the palette name
```
The hit can be a spoken word: write `hit | the word` in `work/anchors.txt`, run `anchors.py`, and the scene reads `spec.timeline.moments.hit.start`. Without a timeline it falls at 5 s.

What was measured (1920x1080, 24 fps, 8 s, CPU): 57 ms a frame; byte-exact preflight; `qa_pixels.py` 99.95% of the 6 x 6 blocks one colour and 100% of them within 24 levels of a PICO-8 colour;
`qa_frames.py` passes (animation on twos is not a frozen picture). The robot and every drawing here are original (MIT). A real Aseprite export, a pixel font and a spoken hit were not tried.
