# Storyboard: brag's method, narration first

The storyboard method is brag's (latent-spaces/brag, MIT, vendored by OmniSkill). **Read the full playbook before planning**
when OmniSkill is installed: the newest `~/.claude/plugins/cache/omniskill/omniskill/*/skills/brag/vendor/SKILL.md`
(sections: Plan, Creative laws, Tones, Sound, Deliver). What follows is a condensed version in our own words, plus what this
suite changes. If OmniSkill is missing, this file is enough to work from.

## The shape

Hook (2 to 3 s) -> Reveal (2 to 4 s) -> 2 or 3 sharp highlights -> Punchline/outro (2 to 4 s). A starting shape, not a template.
Total length 15 to 30 s is the sweet spot (this suite handles up to about 60 s; keep every extra second earning its place).

## Creative laws (brag's, kept)

- **Short.** If it can be said in 20 s it should not take 30.
- **Clear to a stranger.** After one viewing someone who has never heard of the topic knows what it is, why it matters, what to do.
- **The hook is everything.** The first 2 s decide whether anyone stays. Plan it first.
- **Show the thing.** Real material over abstract filler. For a topic with no UI to film, the "thing" is the numbers, the
  mechanism (a small honest diagram), or the quote. Never decorative loops.
- **Specific.** No generic claims. Use the subject's own words and verified numbers.
- **Readable.** Any line the viewer is meant to read stays fully visible and settled for about 0.3 s per word, counted from
  when the whole line is on screen. Texture text (sources, footers) is exempt.
- **Alive.** Things appear one by one, numbers count up, bars grow. No static slides.
- **Every frame postable.** Any frozen frame is worth sharing.
- **Only supportable claims.** No invented numbers or testimonials. See the claims table below.

## Tones (pick one, or write your own direction)

`default` punchy and clean (4 to 5 scenes) · `polished` serious, long holds (3 to 4 scenes) · `deadpan` calm and dry ·
`cinematic` trailer-scale big type · `chaotic` fast and loud · `app-store` clean feature cards · `yc-parody` straight-faced.
Humour comes from the subject's own absurdity, never from a fake metric.

## What this suite changes: narration-first timing

brag draws frames as a pure function of time and plans scene durations on paper. Here the voice is generated first, so
**scenes follow words**: write the script one sentence per line, generate and tighten the narration, read `timeline.json`
(each sentence's start in seconds), then place every on-screen event on a spoken cue. Rules of thumb:

- A number counts up so it lands as the word is said (finish the count 0.2 to 0.5 s after the word starts).
- The visual for a sentence appears 0.1 to 0.3 s before its first word, not after.
- Leave the last 0.8 to 1 s as a held end card, and give the narration 0.4 s of lead-in.
- 2.6 words per second is VoxCPM2's natural pace: 75 to 80 words is about 30 s. Count before you generate.

## brag-plan.md template (write it to `brag-output/brag-plan.md`)

```
# brag plan: <topic> (<length> s)
**Angle.** one paragraph: what is true, what is surprising, what the nuance is.
**Tone.** preset or freeform. **Visual identity.** the brand file used (colours, fonts, signature marks).

## Storyboard
| Time | Scene | On screen | Narration (cue = sentence start in timeline.json) |
|---|---|---|---|

## Claims and where each one comes from
- <claim>: <primary source link>, date. Press-only claims are listed as such and appear on screen as "reported".
- Illustrative content (example code, mock data) is labelled EXAMPLE on screen.

## Sound      generated: key, tempo, what builds when, where the hits land, ducking, mixer level
## Pipeline   tools and seeds used (voice engine + seed, brand file, music cues)
## Delivery checks   resolution, fps, frames, duration, LUFS, peak, sync lag
```

## Claims discipline (learned on the first video)

1. Fetch the primary source (author's own post, project tracker, official page). News sites often block fetching; if you only
   saw a search summary, say so in the plan and put "reported" or "per press reports" on screen.
2. Keep nuance the source states. The first video's source said AI helped "at least partially" and that crediting AI alone
   would be a gross oversimplification, so the video says "AI helped, but so did experts and tooling".
3. Quote at most a few words, attribute them on screen, and never put words in quotation marks that are a paraphrase.
4. Illustrative example content must be checked for internal consistency (the MIPS example was decoded by hand).
5. Put the sources on the end card.
