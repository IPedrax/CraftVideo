# The mascot: Clawd on a video

Clawd, the Claude Code mascot, as a hand-painted character that walks on, reacts to the narration with acted faces, and walks off again. `mascot.sh` renders it as a
transparent overlay and can lay it over the picture, so it works on a made video (mode A) and, through `edit.json`, on an edit (mode B). Use it where it fits, which is
less often than it is tempting: the first section says where.

Clawd and its painting engine are [ClaudeAnimationBase](https://github.com/JohnHeibel/ClaudeAnimationBase) by John Heibel (MIT). `get_mascot.sh` installs them at a pinned commit
with p5.js (LGPL-2.1) and p5.brush (MIT) from npm; none of it is stored in this repository. Clawd is a character of Anthropic: use it in videos about Claude, its tools and
the developer world it lives in, and never in a way that suggests Anthropic endorsed the video.

## Does it fit?

| It fits | Because |
|---|---|
| a video about Claude, Claude Code, agents, AI tooling or developer workflow | it is that world's mascot and the viewer recognises it |
| a surprising number or a reveal | a take after the line lands tells the viewer how to feel about it |
| a step-by-step explanation with something to point at | a character that looks at the thing leads the eye to it |
| an intro or an outro | it walks on with the title and walks off at the end |
| a light joke or a punchline | a face is the cheapest second joke |

| Leave it out | Because |
|---|---|
| grief, harm, a crime, a war, someone's misfortune | a cartoon pulling faces beside it is tone-deaf |
| money, health, legal or safety claims that have to read as serious | the sources are the point, and a mascot undercuts them |
| a dense frame, where the corner is needed for the data | it covers the picture |
| a video about another company's product, or with no link to Claude | Clawd would tie it to Anthropic |
| the user did not ask and the topic does not call for it | a mascot is a choice about the video's identity: ask first |

Rule of thumb: on screen for at most a third of the video and no more than three appearances in a minute. A mascot that never leaves is the subject of the video, not its sidekick.

## Make it

```bash
CRAFTVIDEO_ALLOW_DOWNLOAD=1 bash $S/get_mascot.sh        # once; every file is checked against its pinned SHA-256 (or pass a ClaudeAnimationBase checkout)

# the review sheet first: seconds, shows every cue once its take has settled, labelled with the video time
bash $S/mascot.sh work/mascot.json work/mascot.mov --timeline work/timeline.json --width 1920 --height 1080 --sheet work/mascot-sheet.png

# the clip, then lay it over a made video's picture (its sound is kept); assemble.sh as usual after that
bash $S/mascot.sh work/mascot.json work/mascot.mov --timeline work/timeline.json --width 1920 --height 1080 --fps 30 --workers auto \
     --over work/picture.mp4 --into work/picture-clawd.mp4
```

1. **Storyboard it.** Decide which beats get him and keep his corner free in those beats: he stands about 22% of the width in from the edge he walks on from, with his feet at 80% of the height,
   above the caption band. An appearance needs at least 2.9 s (walk in 0.9 s, a drawn turn, a moment on screen, a turn, walk out 0.9 s); `mascot.py` refuses a shorter one.
2. **Tie the cues to words.** Name the words he reacts to with `anchors.py` and write the cues against those moments, so they follow the speech and not the clock.
3. **Write `work/mascot.json`**, look at the sheet, fix, then render. Render after the scenes are rendered and joined and before `assemble.sh`: the picture gets one more encode at the house
   quality and the voice is untouched. The overlay must match the picture's size and fps.
4. **For an edit** leave out `--over`: `mascot.sh` writes `work/mascot.overlay.json`, the `overlays` entry for `edit.json` (a clip that starts at the first appearance), and the edit step lays it
   over the footage under the captions. The cue times are then the edited video's own seconds (the output's), not the recording's, because that is the clock the overlay sits on; the size and
   fps are the edit's `output`, so pass `--width`, `--height` and `--fps` to match.

The clip covers only the span from his first entrance to his last exit, so a mascot that appears for 20 s of a 60 s video costs 20 s of rendering. Software rendering (no GPU) is the slow
part: see "What it costs" below.

## The cue file

```json
{
  "bpm": 100,
  "outline": 3,
  "on": [
    { "from": "@claim-1.4", "to": "@number.end+1.5", "side": "right", "u": 22, "enter": "happy" },
    { "from": "@wrap-0.5", "to": 41.0, "side": "right" }
  ],
  "cues": [
    ["@claim.end+0.3", "surprised", { "lookX": -0.8 }],
    ["@number+0.4", "idea"],
    ["@wrap", "proud", { "hat": "crown" }]
  ]
}
```

| Field | Meaning | Default |
|---|---|---|
| `bpm`, `offset` | the music bed's tempo and the time of its first downbeat: every idle bounce lands on the beat (`synth_music.py` uses `bpm` 100) | 100, 0 |
| `outline` | a paper-cream die-cut edge in px at 1080 high, 0 for none. Without it the dark ink marks (the thinking dots, the outline) vanish on a dark picture | 3 |
| `walk`, `turn` | seconds to walk on or off, and for each drawn turn | 0.9, 0.16 |
| `on[]` | one entry per appearance: `from`, `to`, `side` (`left`, `right`: the edge he walks on from and stands at), `u`, `margin`, `ground`, `enter` | see below |
| `u` | the body unit in px at 1080 high; he is 10u wide and 8u tall with the legs, and the size follows the short side of the frame, so the same `u` is the same size on a vertical video | 22 (220 px wide) |
| `margin` | how far he stands from his edge, as a share of the width | 0.05 |
| `ground` | where his feet stand, as a share of the height; the caption band starts at 0.82 | 0.80 |
| `enter` | the face he walks on with | `neutral` |
| `cues[]` | `[time, emotion]` or `[time, emotion, overrides]` | |

A time is seconds, or `"@moment"` (a name in `timeline.json`'s `moments`), with `.end` for the end of the moment and `+0.4` or `-0.4` as an offset: `"@claim"`, `"@claim.end"`, `"@claim-0.4"`,
`"@claim.end+0.3"`. `mascot.py` reports every problem in one run (unknown emotion with a "did you mean", overlapping or too-short appearances, a time past the end of the video, an override that is not
one the kit has) and warns about a face held under 0.6 s and a cue that fires while he is walking.

Overrides are the kit's own options: `hat` (party, hard, crown, halo, wizard, hood, top, fedora, band, sweatband, beanie, bow, flower, headphones, cat, masq, mask, bowtie), `emote` (the painted marks:
`!` `?` `!!` `!?` zzz sweat spark heart hearts anger steam bulb dots scribble music swirl stars cloud), `lookX` and `lookY` (-1 to 1: where the eyes aim), `view` (front, q, side, qback, back), `flip`,
`blush`, `gloom`, `lid`, `squint`, `tint`, `rot`, `dx`, `dy`, `sq`, `aL` and `aR` (arm angles). `mascot.py --emotions` lists the faces, the hats and the marks.

## The 31 faces

| Family | Faces | Use for |
|---|---|---|
| joy | happy, excited, laugh, love, proud, starstruck, playful, hopeful, relieved | good news, a win, a thank you |
| sly | smug, cool, mischief, suspicious | a knowing aside, a trick, doubt about a claim |
| low | sad, cry, bored, sleepy, ko | a loss or a failure; use rarely |
| hot | angry, furious, determined, disgusted | a problem that needs fixing, a bad practice |
| alarm | scared, nervous, surprised, confused, dizzy | a risk, a surprise, a muddle |
| mind | neutral, thinking, idea, shy | the resting face, a question, the click of understanding |

Each face is also a way of moving, locked to the beat. A change of face is acted: a squint and a squash first, then a take sized to the new face, then the new idle.

## Acting

These come from the kit's own guide, applied to a sidekick that sits over someone else's picture.

- **Cause, then reaction.** Cue the face 0.3 to 0.5 s after the line that causes it lands, never on the word: the take is the viewer's permission to feel it.
- **One read at a time.** A face is held about 0.6 s at least, and one or two faces in a line is plenty. Six faces in ten seconds is a mascot having a fit.
- **Lead the eye.** `lookX` and `lookY` point his eyes at the thing the narration names; the viewer looks where he looks. Look left from the right edge, right from the left.
- **Marks, not words.** Reactions are painted marks (`!`, a bulb, hearts). Never put lettering on him: the captions do the talking.
- **A hat is a joke.** Once per video, and on a beat that is already funny.
- **Keep him on the beat.** Set `bpm` to the music; a mascot that bobs out of time reads as a bug.

Legibility: his body is terracotta (#D97757), so a terracotta or orange picture swallows him. The cream edge keeps him readable on dark pictures and costs nothing on light ones. A vertical video
has little room for him: the platform's buttons sit on the right and at the bottom, and the kinetic captions are centred at 62% of the height. Use `"side": "left"`, a smaller `u` (about 16) and check a
frame with the captions on, because the marks above his head reach up about 5u.

## How it is built

- `mascot/clawd.html` is the page. It loads the pinned kit from `/__cv/mascot/` (the html provider serves `~/.local/share/craftvideo/mascot`, or `$MASCOT_DIR`), paints Clawd on a small canvas just big
  enough for him, and pastes the result at his place on the frame. One line of the kit's `core.js` is patched at install time so the canvas size comes from the page.
- **Real transparency.** The kit paints on paper with pigment that mixes with whatever is under it, so a transparent canvas gives pale specks and square glows. Each frame is drawn twice, on white and
  on black, and the difference is the coverage: alpha = 1 - (white - black), colour = black / alpha. Only the box around him is read back. The die-cut edge stamps his solid pixels (coverage over one half) in cream
  around a small circle, so faint glow and haze do not get an edge.
- **A pure function of t, to within renderer noise.** The kit reseeds p5.brush's generators per element from the video time, so a frame depends only on `t`. The software renderer is not bit-exact, though: the
  first draw of a mark in a browser process comes out a few pixels different from every later one, so the page draws every distinct face once, unseen, before the first frame is asked for; and frames with
  the glowing bulb differ from one render to the next by one level in one or two pixels (measured: 12 of 19 repeats of such a frame, PSNR 100 dB or more, while three other frames matched in all 19). That is
  invisible, but a byte-exact preflight calls it history, so `mascot.sh` passes `--preflight-psnr 60` (see `reference/motion-graphics.md`). Why the bulb is noisy is not known.
- `mascot.py` checks the cue file and turns it into the spec the page reads; its self-test covers the time syntax, every error and every warning, and compares its emotion list with the installed kit's.
- `conformance.sh render html` renders a short overlay and checks it has real alpha and a small solid character.

## What it costs

Painting is wash fills and ink lines only, no watercolour fills, which is what makes it affordable without a GPU. Every frame is two draws plus the read-back. Measured on a 12-core machine with the software
rasteriser (SwiftShader, no GPU), while other work was running: the example's 20.9 s of mascot at 1920x1080 and 30 fps, 627 frames, took 149 s and then 207 s in two runs with 3 workers (0.2 to 0.3 s a frame, composite included) and wrote a 66 MB
ProRes 4444 clip; one worker was about twice as slow on a 3 s test (1.0 s a frame against 0.5 s), and the review sheet takes about 10 s. Use `--workers auto` for the clip. A real GPU (`--gpu auto`) should be faster still; it was not tried here.
The clip is only as long as the appearances, from the first entrance to the last exit.

## What it does not do

Other characters (the kit's guide invites new characters and costumes, and `get_mascot.sh` could pin a different kit, but only Clawd is wired), lip-sync or speech, 3D rotation (the kit turns through drawn
key views, never a projected box), and anything that needs the character to touch the picture's own elements: it is an overlay, so it can look at the picture but not hold a piece of it.
