#!/usr/bin/env python3
"""anchors.py: name the words a scene must land on, so scenes follow words instead of seconds.

  anchors.py --anchors work/anchors.txt --transcript work/narration_transcript.json --timeline work/timeline.json [--out work/timeline.json]
  anchors.py --transcript work/narration_transcript.json --words        # print the transcript with word numbers, to write anchors against

work/anchors.txt, one per line, '#' starts a comment:
  name | phrase [#n]                       the phrase: from its first word's start to its last word's end            proof | 6 billion people
  name | first words .. last words [#n]    a range: from the start of the first words to the end of the last, which is searched for after the start     lock | the padlock .. closes
Write each phrase the way the TRANSCRIPT spells it (a digit run is one word, "45" and not "forty five" if that is what was heard); case and punctuation do not matter.
A phrase heard more than once needs `#n` (the n-th time, from 1, applied to the start phrase); without it the script stops and lists where it was heard. A phrase that was
not heard stops it too, naming the nearest words that were. Every problem is reported in one run, and nothing is written unless all anchors resolve.
The result goes into timeline.json as  "moments": {"name": {"start": s, "end": s}}; scenes read spec.timeline.moments.name.start (a count-up can finish at .end) and add their
own lead: a scene's visual may arrive 0.1 to 0.3 s before the word. Transcribe the FINAL narration, so the times are those of the audio in the video.
`--selftest` checks the matching on a hand-made transcript. Python 3 only."""
import argparse, json, re, sys


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def phrase_tokens(text):
    return [t for t in (norm(w) for w in text.split()) if t]


def find_all(toks, phrase):
    n = len(phrase)
    return [i for i in range(len(toks) - n + 1) if toks[i:i + n] == phrase] if n else []


def nearest(toks, words, phrase):
    """the words heard around the first word of the phrase that was heard at all (else around a word with the same first letters): for the error message"""
    i = next((toks.index(t) - k for k, t in enumerate(phrase) if t in toks), None)
    if i is None: i = next((k for k, t in enumerate(toks) if len(phrase[0]) >= 3 and t.startswith(phrase[0][:3])), 0)
    i = max(0, i)
    return " ".join(w["text"] for w in words[max(0, i - 2):i + len(phrase) + 3])


def parse(path):
    out = []
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        if not re.search(r"\s#\d+\s*$", line): line = line.split("#", 1)[0]       # a trailing '#n' is an occurrence, any other '#' starts a comment
        if not line.strip(): continue
        name, sep, spec = line.partition("|")
        if not sep or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", name.strip()): sys.exit(f"anchors: line {n}: expected 'name | phrase', the name made of letters, digits, - or _ (got: {line.strip()[:60]})")
        m = re.search(r"\s#(\d+)\s*$", spec); occ = int(m.group(1)) if m else None
        a, _, b = (spec[:m.start()] if m else spec).partition("..")
        out.append((n, name.strip(), phrase_tokens(a), phrase_tokens(b) if b.strip() else None, occ))
    return out


def resolve(anchors, words):
    toks = [norm(w["text"]) for w in words]; moments, errors = {}, []
    for n, name, a, b, occ in anchors:
        if name in moments: errors.append(f"line {n}: '{name}' is defined twice"); continue
        if not a: errors.append(f"line {n}: '{name}' has an empty phrase"); continue
        hits = find_all(toks, a)
        if not hits: errors.append(f"line {n}: '{name}': [{' '.join(a)}] was not heard; near it the transcript has: {nearest(toks, words, a)}"); continue
        if occ is None and len(hits) > 1:
            errors.append(f"line {n}: '{name}': [{' '.join(a)}] is heard {len(hits)} times, at " + ", ".join(f"{words[i]['start']:.2f} s" for i in hits) + "; add #n to choose"); continue
        if occ is not None and not 1 <= occ <= len(hits): errors.append(f"line {n}: '{name}': #{occ} asked for but it is heard {len(hits)} time(s)"); continue
        i = hits[(occ or 1) - 1]; j = i + len(a) - 1
        if b is not None:
            ends = [k for k in find_all(toks, b) if k > j]
            if not ends: errors.append(f"line {n}: '{name}': [{' '.join(b)}] was not heard after the start; near the start the transcript has: {nearest(toks, words, a)}"); continue
            j = ends[0] + len(b) - 1
        moments[name] = {"start": round(words[i]["start"], 3), "end": round(words[j]["end"], 3)}
    return moments, errors


def selftest():
    import os, tempfile
    words = [{"text": w, "start": round(i * 0.4, 3), "end": round(i * 0.4 + 0.3, 3)} for i, w in enumerate(
        "Over 99% of it travels by cable. About 6 billion people are online. Over 99% is a lot. The padlock closes at last.".split())]
    p = os.path.join(tempfile.mkdtemp(), "a.txt")
    open(p, "w").write("# a comment\nstat | 6 billion people\nfirst | 99% of it   # a trailing comment\nsecond | 99% is #1\nlock | the padlock .. closes\nlast | at last\n")
    got, err = resolve(parse(p), words)
    assert not err, err
    assert got["stat"] == {"start": 3.2, "end": 4.3}, got["stat"]                       # words 8 to 10: the start of "6" to the end of "people"
    assert got["first"] == {"start": 0.4, "end": 1.5}, got["first"]                      # a trailing comment is ignored
    assert got["second"] == {"start": 5.6, "end": 6.3}, got["second"]                    # '#1' is an occurrence, not a comment
    assert got["lock"] == {"start": 7.2, "end": 8.3}, got["lock"]                        # a range runs to the end of the closing words
    assert got["last"] == {"start": 8.4, "end": 9.1}, got["last"]
    open(p, "w").write("dup | 99%\nnone | quantum computers\nlate | the padlock .. 99%\nnth | 99% #3\ntwice | at last\ntwice | at last\n")
    _, err = resolve(parse(p), words); said = " | ".join(err)
    for need in ("heard 2 times", "was not heard; near it", "after the start", "#3 asked for", "defined twice"):          # every kind of problem is reported, in one run
        assert need in said, (need, err)
    print("anchors selftest: ok")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--anchors"); ap.add_argument("--transcript"); ap.add_argument("--timeline"); ap.add_argument("--out"); ap.add_argument("--words", action="store_true")
    a = ap.parse_args()
    if not a.transcript: sys.exit("anchors: --transcript is required")
    words = json.load(open(a.transcript))["words"]
    if a.words:
        for k in range(0, len(words), 10): print(f"{k:4d} {words[k]['start']:7.2f}s  " + " ".join(w["text"] for w in words[k:k + 10]))
        return
    if not (a.anchors and a.timeline): sys.exit("anchors: --anchors and --timeline are required")
    moments, errors = resolve(parse(a.anchors), words)
    if errors:
        print("\n".join("anchors: " + e for e in errors), file=sys.stderr); sys.exit(1)
    tl = json.load(open(a.timeline)); tl["moments"] = moments
    json.dump(tl, open(a.out or a.timeline, "w"), indent=1)
    print(f"{a.out or a.timeline}: {len(moments)} moments: " + ", ".join(f"{k} {v['start']:.2f} to {v['end']:.2f}" for k, v in moments.items()))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest": selftest()
    else: main()
