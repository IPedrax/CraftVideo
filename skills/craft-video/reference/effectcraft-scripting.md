# EffectCraft scripting notes (verified on effectcraft-cli 0.6.0)

EffectCraft runs After Effects-style JavaScript: `effectcraft-cli script file.jsx` (or `run_script` over MCP). Errors report
`file:line:col` of the script it was given, which is why `build.sh` keeps the concatenated `<name>.build.jsx`.

## Traps (each one cost time on the first video)

| Symptom | Cause | Fix |
|---|---|---|
| Multi-line text renders on one line | `\r` is not a line break here | use `\n` |
| Text clipped at the left edge or in the wrong place | default justification is CENTER | always set `justification` (`txt()` does) |
| Font looks wrong or falls back | fonts resolve by PostScript name | `BigShouldersDisplay-Black`, `IBMPlexMono-Medium`; list with `effectcraft-cli exec text.fonts '{"rescan":true}'` |
| Underscore or decoration lands in the wrong place | guessed text width | `layer.sourceRectAtTime(0,false)` works: `underscore()` uses it |
| Last scene fades slowly over its whole hold | two keyframes at the same time (a zero-length fade-out) | skip the fade-out (`out: 0`) |
| Grid background too bright | default effect colour is light grey | `Size From`=3, `Width`/`Height`=40, `Border`=1, `Color`=brand grid colour |
| A bar should grow from its left edge | shape rect is centred on its anchor | rect position `[w/2,h/2]`, animate Scale X (`rect()` with `grow:` does) |
| Count-up numbers | no typewriter keyframes needed | Source Text expression: `Math.round(linear(time,a,b,0,84)).toString()` |
| Text blocks overflow their panel | condensed display fonts are ~0.43 em per glyph, mono is 0.6 em | measure with `sourceRectAtTime`, size down, check a still |

## API subset that is known to work

`app.project.items.addComp(name,w,h,1,dur,fps)`, `comp.layers.addSolid/addText/addShape`, `layer.inPoint/outPoint`,
`property("ADBE Transform Group").property("ADBE Position"|"ADBE Opacity"|"ADBE Scale")`, `setValue`, `setValueAtTime`,
`numKeys`, text documents (`fontSize`, `font`, `fillColor`, `applyFill`, `justification`, `tracking`, `leading`,
`autoLeading`), `property.expression`, shape groups (`ADBE Vector Group`, `ADBE Vector Shape - Rect`,
`ADBE Vector Graphic - Fill` / `- Stroke`), effects via `property("ADBE Effect Parade").addProperty("ADBE Grid")`,
`app.project.save(new File(path))`, `writeLn`.

Rendering: `effectcraft-cli render --comp Main --out x.mp4 --format h264 --bitrate 30000 --audio off project.ecproj`
(1080p30, 900 frames in about 40 s on CPU). Frames: `effectcraft-cli render-frame --comp Main --time 1.4 --scale 0.4 --out f.png project.ecproj`
(about 30 ms each). `effectcraft-cli commands --filter text` lists engine commands; every one is also reachable over MCP.

## Easing

Keyframes are linear, so `animIn` samples an ease-out-quart curve at 8 points. `easeOut(f) = 1 - (1-f)^4`. Entry slides are
40 px up over 0.45 s by default; the brand's own motion token is cubic-bezier(.16,1,.3,1), which this approximates.

## Layout reference at 1920x1080 (scale proportionally for other formats)

Margin 120. Kicker pill at y=108 (46 px tall). Display headlines 190 to 330 px, baseline-anchored. Panels 780 to 800 wide,
labels 24 px mono at 240 tracking. Footer baseline at H-48. Vertical 1080x1920: `begin({w:1080,h:1920})`, margin 72, display sizes
around 60% of the landscape values, one idea per screen; there is no automatic reflow, so re-lay each scene.

## Fonts

The default brand uses Big Shoulders Display and IBM Plex Mono, both SIL OFL, so they are fine in published work. Install
from the google/fonts repo, not from a font ripper:

```bash
F=~/.local/share/fonts/ipedrax-brand; mkdir -p $F; cd $F
gh api "repos/google/fonts/contents/ofl/bigshouldersdisplay/BigShouldersDisplay[wght].ttf" -H "Accept: application/vnd.github.raw" > BSD-VF.ttf
for w in Regular Medium Bold; do gh api repos/google/fonts/contents/ofl/ibmplexmono/IBMPlexMono-$w.ttf -H "Accept: application/vnd.github.raw" > IBMPlexMono-$w.ttf; done
# the variable font registers as Thin by default, so cut static instances (fontTools is in the VoiceStudio venv)
PY=/mnt/ai/VoiceStudio/.venv/bin/python
$PY -m fontTools.varLib.instancer BSD-VF.ttf wght=900 --update-name-table -o BigShouldersDisplay-Black.ttf
$PY -m fontTools.varLib.instancer BSD-VF.ttf wght=700 --update-name-table -o BigShouldersDisplay-Bold.ttf
rm BSD-VF.ttf; fc-cache -f ~/.local/share/fonts
```

Do NOT use a font ripper (a tool that saves fonts from a subscription service such as Adobe Fonts) for anything that gets
published: a saved copy is not a licence. Stick to open-licensed fonts (OFL or similar) or fonts you have bought.
