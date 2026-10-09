# overlay-lowerthird

A transparent lower third rendered as ProRes 4444, to lay over an edited recording.

```bash
bash $S/render.sh scene.html lowerthird.mov --provider html --width 1280 --height 720 --fps 30 --duration 3 --alpha 1
```

Then put `edit-snippet.json`'s `overlays` entries into an `edit.json` (use the absolute path of the `.mov`) and run `edit.sh`. Render the overlay at
the output's size and fps. The card sits at 24% from the bottom so it clears the captions.
