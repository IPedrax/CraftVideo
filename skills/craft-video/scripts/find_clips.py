#!/usr/bin/env python3
"""find_clips.py: pick short clips out of a long recording from its transcript: propose candidates, check the picks, write one edit.json per clip.

  find_clips.py candidates --transcript T.json [--audio rec.mp4] [--min 20] [--max 55] [--top 12] --out candidates.json
  find_clips.py validate PICKS.json --transcript T.json [--min 15] [--max 60] [--snap] [--out PICKS.json]
  find_clips.py edl PICKS.json --source rec.mp4 --transcript T.json --analysis analysis.json --out-dir clips/ [--style talking-head] [--width 1080 --height 1920]
                [--reframe face --face-track track.json | --reframe blur|crop] [--lufs -14]
  find_clips.py --selftest

The division of labour is the point (reference/clips.md): `candidates` is deterministic and cheap, a shortlist from the transcript's own structure (sentence-aligned windows scored on
the opening line, pace, audio energy, how the clip ends, and a penalty for intros, sponsor reads and lines that need what came before). It does NOT decide. The picking is a
judgement (does a viewer who sees only this clip understand and care?) and is made by reading the candidates' text, with the rubric, and writing PICKS.json:
  {"picks": [{"start": 125.4, "end": 163.1, "title": "Why we stopped using microservices", "scores": {"hook": 21, "engagement": 18, "value": 20, "shareability": 15}, "why": "..."}]}
`validate` checks the picks against the transcript (inside the recording, 15 to 60 s, starting and ending at sentence boundaries and not inside a word, a 3 to 9 word title with no hashtag or
emoji, scores 0 to 25, no two clips overlapping by more than 15%) and with --snap moves a bound onto the nearest sentence boundary. `edl` writes one edit.json per pick through plan_edit.py
(--range: the pauses and fillers inside the clip are cut, the audio chain, vertical output, kinetic captions) and prints the edit.sh command for each. Nothing is posted anywhere.
The idea of a transcript-first shortlist with a rubric for the choice, and the signals used (a question or number in the first line, a contrast or story turn, a pause before the line,
an audio energy peak, a penalty for sponsor reads and CTAs) come from SupoClip (FujiwaraChoki/supoclip, AGPL-3.0), which asks an LLM to pick and score. This is our own code, written from a
description of those ideas; none of SupoClip's code or prompts is here. Needs numpy (and ffmpeg for --audio)."""
import argparse, json, os, re, subprocess, sys

END = (".", "?", "!", "…")
TRIGGER = re.compile(r"\b(wait|what|no way|seriously|actually|but|however|instead|because|mistake|secret|wild|crazy|insane|never|always|nobody|everybody|why|how|wrong|truth|changed|biggest|worst|best)\b", re.I)
STORY = re.compile(r"\b(I|we)\s+(thought|realized|found|learned|made|lost|won|decided|tried|used to|started|stopped)\b", re.I)
NUMBER = re.compile(r"\d[\d,.]*\s*(%|x|percent|times|million|billion|thousand|k\b|hours?|minutes?|days?|years?|dollars?)|\$\s?\d|\b\d{2,}\b", re.I)
DANGLING = {"and", "so", "because", "which", "that", "it", "this", "they", "he", "she", "these", "those", "then", "also", "or", "but"}
JUNK = re.compile(r"\b(subscribe|like and|link in the (description|bio)|sponsor(ed)?|use code|promo code|welcome (back )?to|in today'?s (video|episode)|thanks for watching|see you (in|next)|follow (me|us)|newsletter|patreon)\b", re.I)
FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "mm"}
EMOJI = re.compile("[\U0001F000-\U0001FFFF☀-➿]")


def sentences(words, gap=0.7):
    """Sentences from word times: a sentence ends at final punctuation, or at a pause of `gap` seconds."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w); nxt = words[i + 1] if i + 1 < len(words) else None
        if w["text"].rstrip("\"')]”’").endswith(END) or nxt is None or nxt["start"] - w["end"] >= gap:
            out.append({"start": cur[0]["start"], "end": cur[-1]["end"], "text": " ".join(x["text"] for x in cur), "n": len(cur), "gap": (nxt["start"] - w["end"]) if nxt else 9.0}); cur = []
    return out


def audio_peaks(path, span=20.0, lift=5.0, apart=4.0):
    """Seconds where the voice is clearly louder than its surroundings (1 s RMS against the median of the 40 s around it), at least `apart` seconds apart."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32); k = len(x) // 8000
    if k < 5: return []
    rms = 20 * np.log10(np.sqrt((x[:k * 8000].reshape(k, 8000) ** 2).mean(axis=1)) + 1e-3); w = int(span); peaks = []
    for i in np.argsort(-rms):
        if rms[i] < np.median(rms[max(0, i - w):i + w + 1]) + lift: break
        if all(abs(i - p) >= apart for p in peaks): peaks.append(int(i))
    return sorted(p + 0.5 for p in peaks)


def score(S, i, j, peaks):
    first, last = S[i], S[j]; dur = last["end"] - first["start"]; text = " ".join(s["text"] for s in S[i:j + 1]); words = sum(s["n"] for s in S[i:j + 1])
    ft = first["text"]; fw = re.sub(r"\W", "", ft.split()[0].lower()) if ft.split() else ""
    sig = {"hook": (2.0 if "?" in ft else 0) + (1.5 if NUMBER.search(ft) else 0) + (1.5 if TRIGGER.search(ft) else 0) + (1.0 if STORY.search(ft) else 0) + (1.0 if first["n"] <= 12 else 0),
           "standalone": (-0.5 if "?" in ft else -2.0) if fw in DANGLING else 0.0}       # "So how do you..." stands alone; "And then it broke." does not
    wps = words / max(dur, 1e-6)
    sig["pace"] = 1.0 if 2.2 <= wps <= 3.6 else (-1.5 if wps < 1.6 else 0.0)
    sig["energy"] = 1.25 * min(2, sum(1 for p in peaks if first["start"] <= p <= last["end"]))
    sig["payoff"] = (1.0 if last["text"].rstrip().endswith((".", "!")) and last["gap"] >= 0.3 else 0.0) - (1.0 if last["text"].rstrip().endswith("?") else 0.0)
    sig["question"] = 0.5 * min(2, sum(1 for s in S[i + 1:j + 1] if "?" in s["text"]))
    sig["length"] = 1.0 if 25 <= dur <= 50 else (0.0 if 20 <= dur <= 55 else -0.5)
    fill = sum(1 for w in text.lower().split() if re.sub(r"\W", "", w) in FILLERS) / max(1, words)
    sig["junk"] = (-3.0 if JUNK.search(text) else 0.0) - (1.0 if fill > 0.06 else 0.0)
    return {"start": round(first["start"], 3), "end": round(last["end"], 3), "duration": round(dur, 1), "score": round(sum(sig.values()), 2), "signals": {k: v for k, v in sig.items() if v}, "text": text}


def overlap(a, b):
    o = min(a["end"], b["end"]) - max(a["start"], b["start"]); return max(0.0, o) / max(1e-6, min(a["end"] - a["start"], b["end"] - b["start"]))


def candidates(S, peaks, lo, hi, top, keep=0.15):
    pool = []
    for i in range(len(S)):
        wins = []
        for j in range(i, len(S)):
            d = S[j]["end"] - S[i]["start"]
            if d > hi: break
            if d >= lo: wins.append(score(S, i, j, peaks))
        pool += sorted(wins, key=lambda c: -c["score"])[:2]
    out = []
    for c in sorted(pool, key=lambda c: (-c["score"], c["start"])):
        if all(overlap(c, p) <= keep for p in out): out.append(c)
        if len(out) >= top: break
    for n, c in enumerate(sorted(out, key=lambda c: c["start"]), 1): c["id"] = n
    return sorted(out, key=lambda c: -c["score"])


def mmss(t): return f"{int(t // 60):02d}:{t % 60:04.1f}"


def validate(picks, S, words, dur, lo, hi, snap=False):
    errs, warns = [], []
    starts, ends = [s["start"] for s in S], [s["end"] for s in S]
    for n, p in enumerate(picks, 1):
        tag = f"pick {n}" + (f" ({p['title']})" if p.get("title") else ""); a, b = p.get("start"), p.get("end")
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float)) and 0 <= a < b <= dur + 0.5): errs.append(f"{tag}: start and end must be seconds inside the recording (0 to {dur:.1f})"); continue
        d = b - a
        if not lo <= d <= hi: errs.append(f"{tag}: {d:.1f} s is outside {lo:g} to {hi:g} s")
        near = min(starts, key=lambda x: abs(x - a)); nend = min(ends, key=lambda x: abs(x - b))
        inside = lambda t: next((w for w in words if w["start"] + 0.03 < t < w["end"] - 0.03), None)       # a bound inside a word cuts it in half, even within the sentence-edge tolerance
        if abs(near - a) > 0.25 or (snap and inside(a)):
            if snap: p["start"] = round(near, 3); warns.append(f"{tag}: start moved from {a:.2f} to the sentence start at {near:.2f}")
            else: errs.append(f"{tag}: starts mid-sentence ({a:.2f} s; the sentence starts at {near:.2f}): fix it or use --snap")
        if abs(nend - b) > 0.35 or (snap and inside(b)):
            if snap: p["end"] = round(nend, 3); warns.append(f"{tag}: end moved from {b:.2f} to the sentence end at {nend:.2f}")
            else: errs.append(f"{tag}: ends mid-sentence ({b:.2f} s; the sentence ends at {nend:.2f}): fix it or use --snap")
        for edge, verb in ((p["start"], "starts"), (p["end"], "ends")):
            if inside(edge): errs.append(f"{tag}: {verb} inside the word '{inside(edge)['text']}'")
        t = p.get("title")
        if t is not None and (not 3 <= len(t.split()) <= 9 or "#" in t or EMOJI.search(t) or '"' in t): errs.append(f"{tag}: the title wants 3 to 9 plain words, no hashtag, emoji or quotes (got {t!r})")
        for k, v in (p.get("scores") or {}).items():
            if k not in ("hook", "engagement", "value", "shareability") or not isinstance(v, (int, float)) or not 0 <= v <= 25: errs.append(f"{tag}: score '{k}' must be hook, engagement, value or shareability, 0 to 25")
    for i, p in enumerate(picks):
        for q in picks[i + 1:]:
            if all(isinstance(x.get("start"), (int, float)) and isinstance(x.get("end"), (int, float)) for x in (p, q)) and overlap(p, q) > 0.15:
                errs.append(f"two picks overlap by {100 * overlap(p, q):.0f}%: {mmss(p['start'])} to {mmss(p['end'])} and {mmss(q['start'])} to {mmss(q['end'])}")
    return errs, warns


def slug(t): return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:48] or "clip"


def video_python():
    """The python plan_edit.py needs (numpy and soundfile): the skill's own, as lib.sh picks it (VIDEO_PY, else VoiceStudio's venv), else this one."""
    p = os.environ.get("VIDEO_PY") or os.path.join(os.environ.get("VOICESTUDIO_DIR", "/mnt/ai/VoiceStudio"), ".venv", "bin", "python")
    return p if os.access(p, os.X_OK) else sys.executable


def edls(picks, a):
    """One edit.json per pick through plan_edit.py --range; kinetic captions on, loudness for a short."""
    here = os.path.dirname(os.path.abspath(__file__)); os.makedirs(a.out_dir, exist_ok=True); lines = []
    for n, p in enumerate(picks, 1):
        name = f"{n:02d}-{slug(p.get('title', 'clip'))}"; path = os.path.join(a.out_dir, name + ".edit.json")
        cmd = [video_python(), os.path.join(here, "plan_edit.py"), "--source", a.source, "--analysis", a.analysis, "--transcript", a.transcript, "--style", a.style, "--range", f"{p['start']}-{p['end']}",
               "--width", str(a.width), "--height", str(a.height), "--lufs", str(a.lufs), "--captions", "--out", path, "--reframe", a.reframe] + (["--face-track", a.face_track] if a.reframe == "face" and a.face_track else [])
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode: sys.exit(f"find_clips: plan_edit failed for pick {n}: {(r.stderr or r.stdout).strip()[-400:]}")
        e = json.load(open(path)); e["captions"] = {**e.get("captions", {}), "enabled": True, "style": "kinetic", "accent": "#FFD400", "max_words": 3, "burn": True, "sidecar": "srt"}
        e["title"] = p.get("title"); e["pick"] = {k: p[k] for k in ("start", "end", "scores", "why") if k in p}
        json.dump(e, open(path, "w"), indent=1)
        lines.append(f"bash $S/edit.sh {path} {os.path.join(a.out_dir, name + '.mp4')} --transcript {a.transcript}" + (f" --title \"{p['title']}\"" if p.get("title") else ""))
    return lines


def demo_words():
    """A made-up 3.5 minute talk with word times (examples/clips/transcript.json is this): an intro with a sponsor read, two stories, filler talk between, a CTA at the end."""
    lines = [("Welcome back to the channel, and thanks to our sponsor, use code SAVE for ten percent off.", 7.0), ("Today we are talking about shipping software.", 4.0)]
    lines += [("Honestly nothing much happens in this part of the talk, it is background and context.", 6.0)] * 14
    lines += [("Why did we throw away a working system?", 3.0), ("Because every deploy took forty minutes and nobody dared to touch it.", 5.0), ("So I decided to measure it for a month.", 4.0),
              ("We found that ninety percent of the time went into one slow test suite.", 6.0), ("We fixed that in a day and the deploy dropped to four minutes.", 6.0),
              ("That one number changed how the whole team worked, and it was never about the architecture.", 7.0)]
    lines += [("And then there was some more talk about nothing in particular.", 5.0)] * 10
    lines += [("I thought the migration would take a week.", 4.0), ("It took eleven months, and I would do it again.", 5.0), ("The mistake was never the code, it was believing the estimate.", 6.0),
              ("Here is what I wish someone had told me before we started.", 5.0), ("Write the rollback first, and run it before you need it.", 6.0), ("Everything else is detail.", 3.0)]
    lines += [("Thanks for watching, like and subscribe, link in the description.", 6.0)]
    words, t = [], 0.0
    for text, d in lines:
        toks = text.split(); step = (d - 0.6) / len(toks)
        for k, tok in enumerate(toks): words.append({"text": tok, "start": round(t + k * step, 3), "end": round(t + (k + 1) * step - 0.02, 3)})
        t += d
    return words


def selftest():
    import tempfile
    words = demo_words(); S = sentences(words); dur = words[-1]["end"]
    assert len(S) == 2 + 14 + 6 + 10 + 6 + 1, len(S)
    out = candidates(S, [], 20, 55, 6)
    assert out and all(abs(c["start"] - min(S, key=lambda s: abs(s["start"] - c["start"]))["start"]) < 1e-6 for c in out), "candidates must start where a sentence starts"
    assert not any("sponsor" in c["text"] or "subscribe" in c["text"] for c in out), "the sponsor read and the call to action must not be candidates"
    assert all(overlap(c, d) <= 0.15 for i, c in enumerate(out) for d in out[i + 1:]), "candidates must not overlap"
    top = [c for c in out if "Why did we throw away" in c["text"] or "I thought the migration" in c["text"]]
    assert len(top) >= 2, [c["text"][:40] for c in out]
    assert out[0]["score"] >= out[-1]["score"] and "hook" in out[0]["signals"]
    good = {"start": top[0]["start"], "end": top[0]["end"], "title": "Why we threw away a working system", "scores": {"hook": 20, "engagement": 18, "value": 19, "shareability": 14}}
    assert validate([good], S, words, dur, 15, 60)[0] == [], "a clean pick must validate"
    mid = dict(good, start=good["start"] + 2.3)
    e1, _ = validate([mid], S, words, dur, 15, 60); assert any("mid-sentence" in e or "inside the word" in e for e in e1), e1
    e2, w2 = validate([dict(mid)], S, words, dur, 15, 60, snap=True); assert not [x for x in e2 if "mid-sentence" in x] and any("moved" in x for x in w2), (e2, w2)
    bad = [dict(good, end=good["start"] + 5), dict(good, title="Wow"), dict(good, title="Ten words is one too many for a title of this kind ok"), dict(good, title="A #hashtag in the title"),
           dict(good, scores={"hook": 40}), dict(good, start=-3), dict(good), dict(good, start=good["start"] + 1, end=good["end"] + 1)]
    for b in bad[:6]: assert validate([b], S, words, dur, 15, 60)[0], b
    cut = dict(good, end=good["end"] - 0.15)      # inside the last word, though within the sentence-edge tolerance: refused, and --snap puts it on the sentence end
    assert any("ends inside the word" in e for e in validate([dict(cut)], S, words, dur, 15, 60)[0]), "an end inside a word must be refused"
    e3, w3 = validate([cut], S, words, dur, 15, 60, snap=True); assert not e3 and abs(cut["end"] - good["end"]) < 1e-6, (e3, w3, cut["end"])
    assert any("overlap" in e for e in validate([bad[6], bad[7]], S, words, dur, 15, 60)[0])
    # edl: through plan_edit.py with a made-up analysis (the whole talk is voiced)
    d = tempfile.mkdtemp(prefix="cvclips-")
    an = {"duration": dur, "speech": [[0.0, dur]], "video": {"width": 1920, "height": 1080, "fps": 30, "avg_fps": 30}, "audio": {"noise_floor_db": -70}}
    json.dump(an, open(os.path.join(d, "an.json"), "w")); json.dump({"words": words}, open(os.path.join(d, "t.json"), "w"))
    a = argparse.Namespace(source=os.path.join(d, "rec.mp4"), transcript=os.path.join(d, "t.json"), analysis=os.path.join(d, "an.json"), out_dir=os.path.join(d, "clips"), style="talking-head", width=1080, height=1920, reframe="blur", face_track=None, lufs=-14.0)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s=64x36:r=2:d={dur + 1:.0f}", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono", "-t", f"{dur + 1:.0f}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", a.source], check=True)       # a real (black, silent) recording: captions.py and the EDL loader probe the source
    cmds = edls([good], a); e = json.load(open(os.path.join(d, "clips", "01-why-we-threw-away-a-working-system.edit.json")))
    seg = e["segments"]; assert seg and all(good["start"] - 0.3 <= s["in"] and s["out"] <= good["end"] + 0.5 for s in seg), seg
    assert e["captions"]["style"] == "kinetic" and e["output"]["width"] == 1080 and e["output"]["lufs"] == -14.0 and e["output"]["reframe"] == "blur" and "edit.sh" in cmds[0]
    # a clip is cut on its last word, so its last caption must not outlast it: captions.py held every cue 0.6 s, so a fast ending (3 words in 0.3 s) ran past the end and failed qa_edit
    tail = [w for w in words if good["start"] <= w["start"] and w["end"] <= good["end"] + 0.01][-3:]
    for k, w in enumerate(tail): w["start"], w["end"] = round(good["end"] - 0.3 + k * 0.1, 3), round(good["end"] - 0.2 + k * 0.1 - 0.01, 3)
    json.dump({"words": words}, open(a.transcript, "w"))
    srt = os.path.join(d, "clip.srt"); here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([sys.executable, os.path.join(here, "captions.py"), "--transcript", a.transcript, "--edl", os.path.join(d, "clips", "01-why-we-threw-away-a-working-system.edit.json"), "--srt", srt, "--style", "kinetic"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    end = [float(h) * 3600 + float(m) * 60 + float(s.replace(",", ".")) for h, m, s in re.findall(r"--> (\d\d):(\d\d):(\d\d,\d{3})", open(srt).read())][-1]
    assert end <= sum(s["out"] - s["in"] for s in seg) + 1e-3, f"the last caption ends at {end:.2f} s, after the clip"
    print(f"find_clips selftest: ok ({len(out)} candidates from {len(S)} sentences, the top one {out[0]['score']}: {out[0]['text'][:48]}...)")


def main():
    ap = argparse.ArgumentParser(add_help=False); ap.add_argument("cmd", nargs="?"); ap.add_argument("picks", nargs="?")
    ap.add_argument("--transcript"); ap.add_argument("--audio"); ap.add_argument("--min", type=float); ap.add_argument("--max", type=float); ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--out"); ap.add_argument("--snap", action="store_true"); ap.add_argument("--source"); ap.add_argument("--analysis"); ap.add_argument("--out-dir", default="clips")
    ap.add_argument("--style", default="talking-head"); ap.add_argument("--width", type=int, default=1080); ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--reframe", default="crop", choices=["none", "crop", "blur", "face"]); ap.add_argument("--face-track"); ap.add_argument("--lufs", type=float, default=-14.0); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest or a.cmd == "--selftest": return selftest()
    if not a.transcript: sys.exit(__doc__)
    words = json.load(open(a.transcript))["words"]; S = sentences(words); dur = words[-1]["end"]
    if a.cmd == "candidates" and a.out:
        peaks = audio_peaks(a.audio) if a.audio else []
        out = candidates(S, peaks, a.min or 20, a.max or 55, a.top)
        json.dump({"transcript": a.transcript, "duration": dur, "sentences": len(S), "audio_peaks": peaks, "candidates": out}, open(a.out, "w"), indent=1)
        for c in out: print(f"#{c['id']:<2} {mmss(c['start'])}-{mmss(c['end'])} {c['duration']:>5.1f}s  score {c['score']:>5.2f}  {' '.join(f'{k} {v:+g}' for k, v in c['signals'].items())}\n     {c['text'][:150]}")
        print(f"{a.out}: {len(out)} candidates from {len(S)} sentences over {dur / 60:.1f} min" + (f", {len(peaks)} audio energy peak(s)" if a.audio else ""))
        return
    if a.cmd in ("validate", "edl") and a.picks:
        data = json.load(open(a.picks)); picks = data["picks"] if isinstance(data, dict) else data
        errs, warns = validate(picks, S, words, dur, a.min or 15, a.max or 60, a.snap)
        for w in warns: print("find_clips: " + w)
        if errs:
            for e in errs: print("find_clips: ERROR " + e, file=sys.stderr)
            sys.exit(1)
        if a.snap and a.cmd == "validate": json.dump({"picks": picks}, open(a.out or a.picks, "w"), indent=1)
        if a.cmd == "validate": print(f"{len(picks)} pick(s) are fine"); return
        if not (a.source and a.analysis): sys.exit("find_clips: edl needs --source and --analysis (analyze.py)")
        for line in edls(picks, a): print(line)
        return
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
