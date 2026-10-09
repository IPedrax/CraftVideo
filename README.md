<div align="center">
  <h1>CraftVideo</h1>
  <p><strong>A narrated 30-second motion-graphics video from a topic, on your own machine. brag's storyboard, then VoiceStudio, EffectCraft and FilmCraft for the rest, with measured QA gates.</strong></p>
</div>

A Claude Code skill (`/craft-video`). You give it a topic; it researches at primary sources, storyboards with brag's
hook, reveal, highlights, punchline shape, generates the narration first, then times every on-screen event to a spoken
cue, builds the picture by script, synthesises a soundtrack, mixes and exports, and refuses to call it done until
loudness, peak, sync and poster checks pass.

```
research -> storyboard (brag) -> script -> narrate -> tighten (timeline.json) -> scenes -> review stills
                                                             \-> music cues -> synth -> assemble -> finish + QA -> deliver
```

## What is in it

| Piece | File |
|---|---|
| The skill | `skills/craft-video/SKILL.md` |
| Preflight, narrate, tighten, build, stills, synth, assemble, finish, QA sync | `skills/craft-video/scripts/` (tested against the first video: music bit-exact, export identical) |
| EffectCraft helper library + the default brand | `skills/craft-video/jsx/` |
| Storyboard method, scripting traps, font install | `skills/craft-video/reference/` |
| A complete worked example | `skills/craft-video/examples/decomp-30s/` |

## Requirements

`effectcraft-cli`, `filmcraft-cli` (the storytold release tarballs), VoiceStudio built from source with VoxCPM2
(`voicestudio-backend` helper), `ffmpeg`/`ffprobe`, a Python with numpy, soundfile and PIL (the VoiceStudio venv has them),
an NVIDIA GPU with about 8 GB free for the voice. `scripts/preflight.sh` checks all of it.

## Install

As a user skill (edit in place, instant): `ln -s <repo>/skills/craft-video ~/.claude/skills/craft-video`.
As a plugin: add this repo as a marketplace, then install `craftvideo@craftvideo`.

## Licences and credit

MIT (see `LICENSE`). The storyboard method is from [latent-spaces/brag](https://github.com/latent-spaces/brag) (MIT), read at
runtime from the OmniSkill install when present and summarised in `reference/storyboard.md`. The default
brand fonts (Big Shoulders Display, IBM Plex Mono) are SIL OFL. Model weights keep their own terms: VoxCPM2 is Apache-2.0;
OmniVoice is CC-BY-NC, so it is personal use only.
