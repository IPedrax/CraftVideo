# Clips from a long recording

`transcript.json` is a made-up 3.5 minute talk with word times (`find_clips.py --selftest` builds the same one): an intro with a sponsor read, filler chatter, two short stories and a call to action at the end.
It needs no recording, so the first three steps of `reference/clips.md` run on it as they are. `picks.json` is what a person (or Claude) wrote after reading the candidates.

```bash
S=scripts                               # run from skills/craft-video
python3 $S/find_clips.py candidates --transcript examples/clips/transcript.json --min 20 --max 55 --top 6 --out candidates.json
python3 $S/find_clips.py validate examples/clips/picks.json --transcript examples/clips/transcript.json
```

The first command prints six windows with the signals behind each score. The two real stories are #3 (7.5, "Why did we throw away a working system?") and #6 (4.0, "I thought the migration would take a week").
The other four are filler chatter that scores 1 to 4 on structure alone: the script cannot tell they are empty, and reading the text is the step that does. Neither the sponsor read nor the call to action is a candidate.
`picks.json` takes #3 as it is and #6 with its last sentence added ("Everything else is detail."), because that sentence is the payoff and the candidate stopped one short. The second command prints `2 pick(s) are fine`.

With a real recording, add the audio (`--audio rec.mp4`, for the loudness peaks), then run the face track and `edl` as in `reference/clips.md`; `edl` writes one `edit.json` per pick and prints the `edit.sh` command for each:

```bash
python3 $S/find_clips.py edl examples/clips/picks.json --source rec.mp4 --transcript transcript.json --analysis analysis.json --out-dir clips --reframe face --face-track face.json
```

What a real run measured (a 54 s talking-head reel placed on a landscape canvas so that the speaker slides sideways): two clips of 23.6 s and 14.0 s, 1080x1920 at 30 fps, -14.0 LUFS, the speaker in the middle of the
frame, every `qa_edit.py` gate passing; face analysis 2.9 s, the renders 17 s and 11 s on the CPU. The reel is not included.
