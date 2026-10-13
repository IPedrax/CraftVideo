# mascot

Clawd, the Claude Code mascot, walking on, reacting to named words with acted faces and walking off, as a transparent overlay laid over a picture. `timeline.json` carries three
`moments` (the shape `anchors.py` writes), `mascot.json` is the cue file written against them. Read `reference/mascot.md` first: it says when a mascot fits a video and when it does not.

```bash
S=../../scripts
CRAFTVIDEO_ALLOW_DOWNLOAD=1 bash $S/get_mascot.sh            # once: ClaudeAnimationBase at a pinned commit, p5.js and p5.brush, every file checked against its SHA-256

# the review sheet: seconds, one labelled tile per cue once its take has settled
bash $S/mascot.sh mascot.json out.mov --timeline timeline.json --sheet sheet.png

# a plain picture with sound to lay him over, then the clip and the composite in one go (size and fps follow the picture)
ffmpeg -f lavfi -i "color=c=0x14161f:s=1920x1080:r=30:d=24" -f lavfi -i "sine=frequency=220:duration=24" -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac picture.mp4
bash $S/mascot.sh mascot.json clawd.mov --timeline timeline.json --workers auto --over picture.mp4 --into picture-clawd.mp4
```

The cues: he walks on from the right 1.4 s before the claim, is surprised 0.4 s after the claim has landed (looking left, at the picture), has an idea 0.4 s into the number, and leaves 1.8 s after it;
then he walks on again 0.6 s before the wrap, and is proud, in a crown, 0.8 s after it. Each face is held well over 0.6 s and nothing fires while he walks.

## What it proved (measured here)

- The cue file validates with no warnings; the self-test of `mascot.py` covers every error and warning.
- The installer refuses a tampered file and writes nothing; it installs from a local checkout or, with `CRAFTVIDEO_ALLOW_DOWNLOAD=1`, from the pinned files.
- Real alpha: the character is solid (alpha 255), the rest is 0, and the edges are antialiased; the cream edge keeps the dark ink marks readable on a dark picture.
- The frames are deterministic to within the software renderer's own noise: a 72-frame clip rendered with 1 worker was compared with 9 other renders (1 more with one worker, 8 with three): 8 matched frame for frame, and in the 9th one frame
  differed by one level in 6 pixels. The noise sits on the frames with the glowing bulb (one level in one or two pixels, 100 dB PSNR or better), which is why `mascot.sh` runs the provider's preflight with `--preflight-psnr 60`.
- At 1920x1080 and 30 fps the example's 20.9 s of mascot (627 frames) rendered in 149 s and then in 207 s (two runs, other work going on) with 3 workers on a 12-core machine with no GPU, 0.2 to 0.3 s a frame, composite included, into a 66 MB ProRes 4444 clip.
- Laid over a 24 s picture with sound, the composite is 24.0 s at 1920x1080 and 30 fps with the AAC track kept. Frames looked at: he walks on from the right (a sliver at 2.9 s, side view at 3.4 s), turns to the camera, is happy,
  surprised, has the idea, walks off to the right, walks on again, wears the crown and leaves. The same `overlays` entry through `edit.sh` (the ffmpeg provider) puts him in the same places and the edit's loudness pass still runs.
