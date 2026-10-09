# Worked example: "AI decompilation boom", 30 s

The first video made with this skill. Every input is here, so it can be rebuilt end to end:

| File | What it is |
|---|---|
| `script.txt` | the narration, one sentence per line with labels |
| `timeline.json` | sentence start times from `tighten_voice.py` (the cues the scenes are timed to) |
| `scenes.jsx` | all six scenes, written with `jsx/ec_lib.jsx` |
| `cues.json` | the music cues (hits on scene changes, arp density, risers, count-up ticks) |

```bash
S=skills/craft-video; E=$S/examples/decomp-30s
bash $S/scripts/narrate.sh $E/script.txt narration_raw.wav --seed 20261009
$VIDEO_PY $S/scripts/tighten_voice.py --raw narration_raw.wav --script $E/script.txt --out narration.wav --timeline timeline.json
bash $S/scripts/build.sh $E/scenes.jsx video.ecproj
$VIDEO_PY $S/scripts/synth_music.py --cues $E/cues.json --narration narration.wav --out music.wav
effectcraft-cli render --comp Main --out silent.mp4 --format h264 --bitrate 30000 --audio off video.ecproj
bash $S/scripts/assemble.sh --video silent.mp4 --voice narration.wav --music music.wav --out final.mp4
bash $S/scripts/finish.sh final.mp4 out --voice narration.wav
```

Facts on screen come from Chris Lewis's blog post (26 Aug 2026) and decomp.dev; press-only claims are labelled "reported".
The MIPS and C panels are an invented illustrative example, checked for internal consistency.
