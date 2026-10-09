# Example: an HTML scene (`html` render provider)

`scene.html` draws itself from the narration cues: each line enters on its own sentence. It defines `window.craftvideo.seek(t)` and
reads `window.__CV_SPEC.timeline`. `script.txt` and `timeline.json` are the matching inputs (three short sentences, 6 s).

```bash
S=skills/craft-video/scripts; E=skills/craft-video/examples/html-hello
bash $S/render.sh $E/scene.html hello.mp4 --provider html --timeline $E/timeline.json --width 1280 --height 720 --fps 30
bash $S/render.sh $E/scene.html sheet.png --provider html --timeline $E/timeline.json --stills "0.2 1.0 3.0 5.0" --sheet sheet.png
```

Rules for writing your own: `reference/html-scenes.md`. A second scene, `../html-css-animation/`, shows CSS keyframes driven by `seek(t)`.
