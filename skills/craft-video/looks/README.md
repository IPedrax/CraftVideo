# Looks: colour, type and motion roles as data

A **look** is one small JSON file that fixes a video's art direction: the colour roles, the type roles with their sizes, the motion and camera feel, the grain, the caption style and the sound
mood. Pick one in step 2 of the workflow, render with `--look NAME`, and every scene that styles itself with the injected variables changes with it.

```bash
bash $S/render.sh work/scene.html work/silent.mp4 --provider html --timeline work/timeline.json --width 1920 --height 1080 --look dark-keynote
bash $S/render.sh work/scene.html work/lint.json  --provider html --lint 1 --look dark-keynote ...     # the layout lint sees the same look
```

The renderer loads `looks/NAME.json` (or a path to your own) and, before the page runs, adds CSS custom properties to `:root` and puts the whole look in `window.__CV_SPEC.look`:

| Variable | From |
|---|---|
| `--cv-ground`, `--cv-surface`, `--cv-ink`, `--cv-muted`, `--cv-accent`, `--cv-signal` (and any other `color` key, such as `--cv-ghost`) | `color` |
| `--cv-ROLE-font`, `--cv-ROLE-weight`, `--cv-ROLE-size` (in `vh`, so it follows the frame height), `--cv-ROLE-transform` (`uppercase` when `caps`) | each role in `type`: `display`, `text`, `label`, and `hero` or `statement` in some looks |

A scene uses them with a fallback so it still renders without a look: `color: var(--cv-ink, #f2f2f0); font-size: var(--cv-display-size, 9vh)`. `examples/looks-demo/scene.html` is a whole scene built
that way. The rest of a look (`motion`, `camera`, `texture`, `caption`, `avoid`, `sound`) is direction for whoever builds the scenes and the music: read it before writing them, and put its
`bpm` and `duck_db` into `cues.json`.

| Look | For | Ground, ink, accent | Type (fonts are OFL) |
|---|---|---|---|
| `signature` | the owner's own videos | `#0a0a0b`, `#f2f2f0`, hot pink `#ff2e88`; cyan `#3ad7ff` for data | Big Shoulders Display caps, IBM Plex Mono |
| `dark-keynote` | product and AI-tool explainers, a hero number | `#0A0B0F`, `#E8EAF0`, lime `#B7F34A` | Inter Tight |
| `dataviz` | proof that is a chart or a number | paper `#F6F3EC`, pencil `#2B2723`, blue `#2F5D8A`, red records | Newsreader, Caveat |
| `iso-infographic` | how a system, a chain or a city works | tan `#F2E6D0`, `#2E2522`, blue in three tones | Jost caps |
| `swiss-motion` | serious, factual topics: law, privacy, finance | `#EAE9E5`, `#111111`, one red `#E30613` | Archivo |
| `whiteboard` | teaching a process stroke by stroke | `#FBFBF9`, `#23262C`, blue `#2A5CB3` | Caveat |
| `blueprint` | how a machine or an architecture is built | `#18336B`, `#E7F0F9`, one orange stamp | Caveat, B612 |
| `hologram-hud` | scanning, tracking, surveillance, security | `#02080A`, `#E2F5F8`, cyan `#70ECFF`, amber `#FFBC47` for locked values | Rajdhani, Share Tech Mono |
| `ascii-crt` | terminals, code, hacker culture | `#090604`, `#FFEBB8`, amber `#FFB000` | VT323 |
| `pixel-art` | games, retro and 8-bit topics, a scene drawn at a small size and shown at an integer scale | PICO-8's sixteen: `#1D2B53`, `#FFF1E8`, red `#FF004D`, yellow `#FFEC27` | Press Start 2P (not installed here; DejaVu Mono bold is the fallback) |

**Fonts.** Each role names a family and a fallback stack; the loader fetches nothing. On the machine this was built on only the owner's two brand fonts (Big Shoulders Display, IBM Plex
Mono), Noto and DejaVu are installed, so the other looks render with their fallbacks until the named OFL family is installed or shipped next to the scene with `@font-face`
(`reference/html-scenes.md`). Colours, sizes and layout are right either way; the typeface is what changes.

**Where the values come from.** `signature` is this suite's own brand. The other eight are adapted from the style notes of [lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar) (MIT,
LemoLab): the colour roles, the ramps and tones, and the caption, label and title sizes follow its notes; `surface`, `muted`, any display or text size its notes do not give, and the choice of
typeface where noted in a file's `source` are ours. Those files are rewritten as data; none of its code or prose is copied, and nothing was run. Contrast was checked: `muted` and `ink` against the
ground clear 4.5:1 and `accent` and `signal` 3:1 (`scripts/check_looks.py`).

**A pixel look** also has a `pixel` block: `{"scale": 6, "palette": "pico8", "fps": 12, "dither": "bayer"}`. `scale` must be even (4:2:0 chroma, `reference/pixel-art.md`), `palette` a name in `pixel/palettes.json`, and every colour of the look must be one of the palette's:
`check_looks.py` checks all three. `pixel/cvpixel.js`'s `screen(spec)` reads `scale` from it and `examples/pixel-art/scene.html` reads the palette; the sizes in `type` are multiples of one logical pixel (8 px = 0.044 of the height at scale 6).

**Adding a look.** Copy a file, change the id to match the file name, then run `python3 $S/check_looks.py` (it checks the keys, the hex values, the sizes and the contrast) and render
`examples/looks-demo/scene.html` with it, with `--lint 1` as well: the first Swiss draft used a 7% statement size as body text and the lint caught the sentence running off the frame.
