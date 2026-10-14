# Pixel art (scenes, sprites, and footage turned into pixel art)

In a video, pixel art is a picture drawn at a small **logical size**, a fixed palette, motion in whole pixels and time held on whole animation frames, shown at an **integer scale** with nearest
neighbour. It goes wrong one way: something blends (a half-pixel position, a scale that is not a whole number, an odd scale under 4:2:0 chroma, a smooth fade, error-diffusion dither), and the
result is a soft picture that is neither pixel art nor sharp. This skill makes the safe choice the default and measures the rest. Researched 2026-10-13 (sources at the end); every figure marked
"measured" was run on this machine, the rest is sourced.

| Need | Tool |
|---|---|
| a scene with sprites, a palette, stepped time, crisp text | `pixel/cvpixel.js` in an html scene (`examples/pixel-art/`), `--look pixel-art` |
| footage, a made video or an image turned into pixel art | `python3 $S/pixelate.py in.mp4 out.mp4 --scale 6 --palette pico8` (a `.png` out is a lossless still) |
| proof that a video is pixel-exact | `python3 $S/qa_pixels.py out.mp4 --scale 6 --palette pico8` |
| sprites from Aseprite | `loadSheet()` and `frameAt()` read its `json-array` and `json-hash` exports: four directions, durations, trimmed frames, tag `repeat` |

## The scale (measured)

Draw at `frame / S` and show it at `S`. **S must divide the frame and should be even.** The renderer encodes 4:2:0, where one chroma sample covers 2 x 2 pixels, so an odd S lets colour bleed into the
next pixel. A 16-colour scene upscaled with nearest neighbour and encoded with the renderer's own settings (x264 crf 14, yuv420p), 40 frames, share of S x S blocks that stayed one colour:

| S (1080p) | logical | blocks that stayed one colour | pixels more than 16 levels wrong |
|---|---|---|---|
| 1 | 1920x1080 | the 1-pixel detail is gone | 70% |
| 2, 4, 6, 8 | 960x540, 480x270, 320x180, 240x135 | **100%** | 0% |
| 3 | 640x360 | 50% (4:4:4: 99.9%) | 18% |
| 5 | 384x216 | 44% (4:4:4: 98.9%) | 12% |

So: **use 4, 6 or 8** (320x180 at 6 is the classic: Celeste's canvas; 480x270 at 4 for finer art; 240x135 at 8 for chunky). The others that divide 1920x1080 are 10 (192x108), 12 (160x90), 15, 20, 24;
only the even ones are safe. 1080x1920 is the same list turned round. 1280x720 divides by 2, 4, 5, 8, 10 and 16 (not 3 or 6, which do not divide 1280); 4K by 2, 3, 4, 5, 6, 8, 10, 12, 15 and more (the even ones again are the safe ones).
`yuv444p` fixes odd scales but YouTube specifies H.264 High 4:2:0 and Firefox and many hardware decoders refuse 4:4:4, so keep 4:4:4 and ProRes 4444 for masters and overlays. Non-integer factors
give uneven pixel widths (Godot's docs warn of it at 2.133x) and are never right here. The grid must also start at the frame's corner (at an even offset): shifted by 3 pixels, a good 6x video kept 34% of its blocks.
Classic sizes need bars (PICO-8's 128x128 at 8x is 1024x1024; a Game Boy's 160x144 at 7x is 1120x1008): draw them inside a 1080p logical canvas instead.

`qa_pixels.py` runs this check on a finished video: the share of S x S blocks that are one colour (PASS from 99%), the colours used against the palette, and on a FAIL it says what happened: the grid
fits from an offset, the pixels sit on another grid (the scale is wrong), an odd scale, or a blend. It passes the example scene at 99.95% and `pixelate.py` output at 100%.

## Time

- **On twos.** One drawing held for 2 frames: 12 drawings a second at 24 fps. A pan may run on ones while a character runs on twos. Choose the output rate first, then rates that **divide** it: 24 fps holds
  12 (x2), 8 (x3), 6 (x4); 30 fps holds 15, 10, 6; 60 fps holds 30, 20, 15, 12, 10, 6. 12 drawings in a 30 fps video alternate 2 and 3 frames and judder. `tick(t, rate)` holds the time.
- **Numbers from practitioners** (Slynyrd, Saint11): a run is 8 poses at 80 ms or 4 at 160 ms; a walk is 8 frames at best, 6 or 4 acceptable, the bob a triangle wave; an idle of 600 ms moves in 1 px
  steps; Aseprite's default frame is 100 ms. One smear frame for a swing, a longer hold on follow-through; too much anticipation reads as lag.
- **Hit-stop and shake.** Fighting games freeze 9, 11 and 13 frames at 60 fps (light, medium, hard), Street Fighter II about 14: **0.15 to 0.25 s**, then a shake of 2 to 4 pixels with a fast decay (a
  trauma model uses trauma squared or cubed with linear decay). Whole-pixel offsets, no roll. `hitstop(t, at, dur)` and `shake(t, amp, fps)` do it; the example decays 3, 2, 1.
- **Whole pixels.** Positions are integers (`Math.round`). A layer may slide at screen resolution while it moves but should snap when it stops. Never scale a finished sprite down; rotate by 90 degrees (45
  sometimes) or redraw; mix pixel sizes only on separate canvases at integer ratios, at most two. A sub-pixel move is one extra in-between frame where pixels stretch across both positions, for large sprites.
- **Palette cycling** (Mark Ferrari): one image of palette indices, no layers, the pixels never move and the colours of a range rotate, neighbours out of phase, for water, fire and sky. `paintIndexed()`
  does the whole-step version; its blended variant adds colours outside the palette. His artwork is copyrighted: generate your own indices.
- **The look of the art.** Hue shifts warmer as a ramp gets lighter (about 20 degrees a swatch at most); anti-alias inside a sprite and not on its outer edge over an unknown background; use a coloured
  outline ("selout") instead of black; a cluster is 2 or more same-colour pixels; dither sparingly.

## Dither (measured)

Pixelating footage has to keep the same pixel the same colour from frame to frame. Real footage, 5 s, 180x320, PICO-8, share of logical pixels that changed colour between consecutive frames:

| `paletteuse` dither | changing per frame | extra over no dither |
|---|---|---|
| none | 14.2% (the real motion and noise) | 0 |
| bayer, bayer_scale 1 / 3 / 5 | 14.5% / 14.4% / 14.2% | 0.3 / 0.2 / 0.0 |
| atkinson | 33.2% | +19.0 |
| floyd_steinberg | 46.0% | +31.8 |
| **sierra2_4a (ffmpeg's default)** | 47.1% | +32.8 |

Ordered (Bayer) dither depends only on position and value, so it cannot shimmer; error diffusion carries one pixel's rounding into its neighbours and the next frame rounds differently. `pixelate.py`
offers only `bayer` (default, `--bayer 3`) and `none`, one fixed palette for the whole clip, and never per-frame palettes (`paletteuse=new=1` blinks). `cvpixel.js`'s `ditherV` and `ditherFade` use the same 4 x 4 Bayer.

## Footage to pixel art: `pixelate.py`

```bash
python3 $S/pixelate.py in.mp4 out.mp4 --scale 6 --palette pico8 --fps 12      # 1080p in, 320x180 art, 12 drawings a second held to the output rate (24 fps: x2)
python3 $S/pixelate.py in.mp4 out.mp4 --scale 6 --palette auto:16             # the clip's own best 16 colours, found once for the whole clip
python3 $S/pixelate.py photo.jpg avatar.png --scale 8 --palette gameboy       # a lossless still
python3 $S/qa_pixels.py out.mp4 --scale 6 --palette pico8
```
The chain: `fps`, `scale=lw:lh:flags=area` (a box average, so moving footage does not crawl), `crop`, `eq` (contrast 1.1, saturation 1.2: a palette flattens), `paletteuse` with a 256-pixel palette image and Bayer
dither, `scale=flags=neighbor` by the integer S, `format=yuv420p`, x264 crf 14 slow. Audio is copied. An odd scale is refused unless `--yuv444` or `--allow-odd`.
- **A fixed palette is a style, `auto:N` is a likeness.** PICO-8's oranges and pinks make skin garish; `auto:16` keeps it natural and is still one palette for every frame. Use a named palette for a
  consistent look across several clips.
- **Order with an edit.** `edit.sh` first, then `pixelate.py` on the result: its punch-in zoom, stabiliser and face-following crop all resample the picture and would blur a pixel grid made before them.
  Burned-in captions are pixelated with the rest (a pixel-art look); to keep them sharp, caption after pixelating through a vector overlay.
- **Hold it.** `--fps` is the drawing rate and must divide the output rate (12 does not divide 30: it is refused; use 10 or 15). The conformance suite runs it on a test pattern and the gate must pass.
- **Small text does not survive.** At 320x180 a letter needs about 8 px (4.4% of the height) to read. Run on The Connected City (a 3D explainer with 1.2% body text), the headline and the big number stayed
  legible and every paragraph dissolved. Pixelate footage that has no small text, or use a smaller scale (4 gives 480x270), or add the text afterwards in pixel type (`screen().text()`).
- **It is heavy.** Bayer dither is high-frequency detail at 1080p: 20 s of a 3D scene was 17 to 23 MB at the default crf 14 (7 to 9 Mbps). `--crf 18` made the auto-palette one 23% lighter (18 MB) and the gate still passed, at 99.2% with the worst frame 97.8% instead of 99.9%.

## Palettes

`pixel/palettes.json` ships three, each with its terms: **pico8** (CC0, per Lexaloffle's FAQ: 000000 1D2B53 7E2553 008751 AB5236 5F574F C2C3C7 FFF1E8 FF004D FFA300 FFEC27 00E436 29ADFF 83769C FF77A8 FFCCAA),
**cga16** (the hardware's fixed levels) and **gameboy** (four greens, no author known). Anything else loads from a `.hex` file (one `#rrggbb` a line) or a PNG: `--palette my.hex`. Lospec lists thousands,
but its pages show no licence. DawnBringer 16 and 32's author says in the original forum thread that they are free to use (an informal permission); Sweetie 16, Endesga 32, Resurrect 64, Apollo and AAP-64
state no terms. They are not shipped: fetch the list and keep the credit. NES has no canonical RGB (it depends on composite decoding); C64 has competing derivations.
A look names its palette (`"pixel": {"palette": "pico8", "scale": 6}`) and `check_looks.py` checks that every colour of the look is in it.
ffmpeg's `paletteuse` wants **exactly 256 pixels** in the palette image: `pixelate.py` repeats the colours to fill it (a repeat is the same colour, the mapping is unchanged).

## Text

A canvas cannot turn text anti-aliasing off. `screen().text()` draws the text with any font, then keeps only the pixels that are at least half covered and recolours them: whole pixels from whatever is
installed. Bold at 8 px or more reads well (DejaVu Sans Mono Bold at 8 px is legible; regular weight at 8 px breaks letters apart); a pixel font at its native size or a multiple is crisper still.
**None is installed here**, so the look names Press Start 2P with a fallback and the example uses DejaVu. Native sizes and licences: Press Start 2P (OFL, CodeMan38, 8 px and multiples), Silkscreen (OFL,
8 and multiples, anti-aliasing off), m5x7 (CC0, 16, 32, 48), Monogram (CC0), Pixel Operator (CC0 per its author, 16 px), Kenney Fonts (CC0), VT323, Pixelify Sans, Tiny5 and Departure Mono (OFL; Departure Mono
works in steps of 11 px). Install one and put its family in the font string; ship its licence text with it.

## Sprites from Aseprite

`aseprite -b robot.aseprite --sheet sheet.png --data sheet.json --format json-array --list-tags` (File > Export Sprite Sheet in the editor). `frames[]` holds `filename`, `frame{x,y,w,h}`, `rotated` (always
false), `trimmed`, `spriteSourceSize`, `sourceSize` and `duration` in ms; `meta` holds `image`, `size`, `scale` and `frameTags[]` of `name`, `from`, `to`, `direction` (`forward`, `reverse`, `pingpong`,
`pingpong_reverse`) and, above 0, `repeat` as a quoted string. A ping-pong shows each end once (0 1 2 3 2 1). `from` and `to` are sprite frame numbers and `frameTags` ignores `--tag` and `--frame-range`;
prefer json-array (object order is unspecified). `loadSheet()` reads both, `frameAt(sheet, tag, t)` is a pure function of t, `drawFrame()` places a frame at whole pixels and flips it inside its own box.
`examples/pixel-art/make_sprites.py` writes a stand-in sheet in this shape so the example needs no Aseprite. **Licence (not legal advice):** Aseprite's source and binaries are under an EULA you may compile for
personal use but not redistribute; its FAQ lets you use your own output anywhere; the EULA says nothing about the exported data format. Reading the documented JSON with our own code is fine; do not copy its
source or bundle the program. Piskel (Apache-2.0), Pixelorama (MIT) and LibreSprite (GPL-2.0) export other shapes, not read here.

## Delivery

YouTube asks for H.264 High, 4:2:0, BT.709, and suggests 8 Mbps at 1080p30 and 35 to 45 Mbps at 2160p30; Meta and TikTok transcode into several bitstreams and no measured study of what they deliver was found.
Platforms re-encode, so give them bitrate and a big integer scale (the renderer's crf 14 keeps even scales exact). A 2021 test of ten videos found YouTube serves 1080p and below as H.264 and above as VP9 only,
so a 4K upload (480x270 at S = 8, or 320x180 at S = 12) is the cheap way to a codec that keeps flat colour, **reported once, not verified here**. A pixel overlay is a ProRes 4444 `.mov` as ever (binary alpha:
`screen()` leaves the outer edge unblended).

## Traps found and measured

- **`crop` rounds an odd height down on yuv420p** (135 became 134), after which the integer upscale is gone and 3% of the blocks split. `pixelate.py` crops with `exact=1`; found because the conformance
  test used a 240x135 logical size.
- **ffmpeg's default dither shimmers** (47% of the pixels change every frame); see above.
- **`paletteuse` needs a 256-pixel palette image**, and `palettegen` reserves a transparent entry unless `reserve_transparent=0`.
- **Odd scales and a shifted grid** fail the gate, with the numbers above.
- **A held frame is not a still.** The picture gate (`qa_frames.py`) does not mistake animation on twos for a frozen picture (the example passes it).
- **CSS `image-rendering: pixelated`** is nearest neighbour to an integer multiple and then smooth: it gives uneven pixels at a non-integer DPR or zoom. The example draws at the logical size and scales a
  canvas by a whole CSS size on a device scale factor of 1, which the gate confirms.

## Not tested

A real Aseprite export (the stand-in has the same fields); the 4K and VP9 route; palette-swap and palette-cycling videos beyond the example's water; blue-noise dither (CC0 textures exist) and per-pixel
hysteresis against threshold flicker; `-tune animation` (on the synthetic scene it cost 6% more bytes for a 3% lower mean error and the same 100% grid, so it is not used); hit-stop on a real fight; a pixel font installed.

## Sources

- Timing and craft: https://www.slynyrd.com/blog/2018/8/19/pixelblog-8-intro-to-animation · .../2024/5/24/pixelblog-50-human-walk-cycle · .../2024/9/26/pixelblog-52-idle-fighting-stance · .../2018/9/8/pixelblog-9-melee-attacks · .../2018/1/10/pixelblog-1-color-palettes · https://saint11.art/blog/consistency/ · https://saint11.art/blog/scaling/ · https://derekyu.com/makegames/pixelart.html · http://www.effectgames.com/effect/article-Old_School_Color_Cycling_with_HTML5.html · https://sonichurricane.com/?p=1043 (hit-stop) · https://infovore.org/?p=5275 (Nuclear Throne shake) · https://kidscancode.org/godot_recipes/3.x/2d/screen_shake/
- Aseprite: https://www.aseprite.org/docs/cli/ · exporter source https://raw.githubusercontent.com/aseprite/aseprite/main/src/app/doc_exporter.cpp · https://raw.githubusercontent.com/aseprite/aseprite/main/src/doc/playback.cpp · EULA https://github.com/aseprite/aseprite/blob/main/EULA.txt · https://www.aseprite.org/faq
- Video: https://tasvideos.org/EncodingGuide/Legacy/HighDefinition (even integer ratios and chroma) · https://support.google.com/youtube/answer/1722171 · https://streaminglearningcenter.com/?p=16297 · https://ai.meta.com/blog/meta-scalable-video-processor-MSVP/ · https://docs.godotengine.org/en/stable/tutorials/rendering/multiple_resolutions.html · https://developer.mozilla.org/en-US/docs/Games/Techniques/Crisp_pixel_art_look
- Dither: http://blog.pkh.me/p/21-high-quality-gif-with-ffmpeg.html · https://surma.dev/things/ditherpunk/ · https://en.wikipedia.org/wiki/Ordered_dithering · ffmpeg's `vf_paletteuse.c` and `vf_palettegen.c`
- Palettes and fonts: https://www.lexaloffle.com/pico-8.php?page=faq (CC0) · https://lospec.com/palette-list · http://pixeljoint.com/forum/forum_posts.asp?TID=12795 (DawnBringer) · https://github.com/google/fonts/tree/main/ofl/pressstart2p · https://kottke.org/plus/type/silkscreen/ · https://managore.itch.io/m5x7 · https://datagoblin.itch.io/monogram · https://kenney.nl/assets/kenney-fonts
