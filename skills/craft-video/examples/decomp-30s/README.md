# Worked example: "AI decompilation boom", 30 s (EffectCraft + VoiceStudio + FilmCraft)

The first video made with this skill. Every input is here, so it can be rebuilt end to end:

| File | What it is |
|---|---|
| `script.txt` | the narration, one sentence per line with labels |
| `timeline.json` | sentence start times from `tighten_voice.py` (the cues the scenes are timed to) |
| `scenes.jsx` | all six scenes, written with `jsx/ec_lib.jsx` |
| `cues.json` | the music cues (hits on scene changes, arp density, risers, count-up ticks) |

```bash
S=skills/craft-video/scripts; E=skills/craft-video/examples/decomp-30s
bash $S/narrate.sh $E/script.txt narration_raw.wav --seed 20261009
$VIDEO_PY $S/tighten_voice.py --raw narration_raw.wav --script $E/script.txt --out narration.wav --timeline timeline.json
bash $S/render.sh $E/scenes.jsx silent.mp4 --timeline timeline.json
$VIDEO_PY $S/synth_music.py --cues $E/cues.json --narration narration.wav --out music.wav
bash $S/assemble.sh --video silent.mp4 --voice narration.wav --music music.wav --out final.mp4
bash $S/finish.sh final.mp4 out --voice narration.wav
```

Same video with different tools: `CRAFTVIDEO_TTS=openai ...`, `CRAFTVIDEO_ASSEMBLE=ffmpeg ...` (see `reference/providers.md`).
The scenes file is EffectCraft-specific; the HTML equivalent of the pattern is `../html-hello/`.

Facts on screen come from Chris Lewis's blog post (26 Aug 2026) and decomp.dev; press-only claims are labelled "reported".
The MIPS and C panels are an invented illustrative example, checked for internal consistency.
