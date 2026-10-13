#!/usr/bin/env python3
"""find_retakes.py: list the takes a recording repeats, so a person can approve cutting the earlier ones. It never edits anything.

  find_retakes.py transcript.json [--out retakes.json] [--gap 0.85] [--window 75] [--similar 0.34]

People re-say a line until it comes out right, and a filler-and-silence cutter keeps every attempt. This splits the transcript into takes (a pause over --gap seconds, a sentence
end once a take is over 7.5 s, or 16 s whatever happens), fingerprints each take by its first 18 content words, and compares it with the next 8 takes inside --window seconds:
  retake       the word sets overlap by --similar or more (Jaccard), or by 0.24 with 2 of the first 4 content words equal: the EARLIER take is the candidate to cut
  false start  a take under 6 s whose opening words come back within 12 s: it was abandoned and restarted
Prints each candidate with its time span and both texts, and with --out writes {"candidates": [{cut: [s, e], keep: [s, e], reason, cut_text, keep_text}]}. To apply one, remove or
shorten that span in edit.json's `segments`, then read review.md: a repeated take is a judgement (the later one is not always the better one, and a deliberate repeat is content).
The idea comes from the retake finder in the HyperFrames student kit (MIT, Nate Herk); this is our own implementation. Python 3 only; `--selftest` checks it."""
import argparse, json, re, sys

STOP = set("the a an and or but so to of in on it its is was were be been are am i you we they he she that this these those for with at as by from not no my me our your have has had do does did will would can could just like um uh yeah okay".split())


def takes(words, gap=0.85, sentence_after=7.5, hard=16.0):
    out, cur = [], []
    for w in words:
        if cur and (w["start"] - cur[-1]["end"] > gap or w["end"] - cur[0]["start"] > hard
                    or (re.search(r"[.!?]$", cur[-1]["text"]) and cur[-1]["end"] - cur[0]["start"] >= sentence_after)):
            out.append(cur); cur = []
        cur.append(w)
    if cur: out.append(cur)
    return [{"start": t[0]["start"], "end": t[-1]["end"], "text": " ".join(w["text"] for w in t), "sig": signature(t)} for t in out]


def signature(ws, n=18):
    toks = [re.sub(r"[^a-z0-9']", "", w["text"].lower()) for w in ws]
    return [t for t in toks if len(t) > 2 and t not in STOP][:n]


def jaccard(a, b):
    A, B = set(a), set(b)
    return len(A & B) / len(A | B) if A | B else 0.0


def find(words, gap=0.85, window=75.0, similar=0.34):
    T, found, used = takes(words, gap), [], set()
    for i, a in enumerate(T):
        if len(a["sig"]) < 2: continue
        for j in range(i + 1, min(len(T), i + 9)):
            b = T[j]
            if b["start"] - a["end"] > window or len(b["sig"]) < 2: continue
            jac = jaccard(a["sig"], b["sig"]); head = len(set(a["sig"][:4]) & set(b["sig"][:4])); full = len(a["sig"]) >= 3 and len(b["sig"]) >= 3     # a retake needs real content; a false start can be two words
            if full and (jac >= similar or (jac >= 0.24 and head >= 2)): kind = "retake"
            elif a["end"] - a["start"] < 6.0 and b["start"] - a["end"] <= 12.0 and len(set(a["sig"][:3]) & set(b["sig"][:3])) >= 2: kind = "false start"
            else: continue
            if i in used: break
            used.add(i)
            found.append({"cut": [round(a["start"], 2), round(a["end"], 2)], "keep": [round(b["start"], 2), round(b["end"], 2)], "reason": f"{kind} (overlap {jac:.2f})", "cut_text": a["text"], "keep_text": b["text"]})
            break
    return found


def selftest():
    def seq(parts):                                   # parts: (text, pause before the take); words 0.3 s each
        t, out = 0.0, []
        for text, pause in parts:
            t += pause
            for w in text.split(): out.append({"text": w, "start": round(t, 3), "end": round(t + 0.28, 3)}); t += 0.3
        return out
    ws = seq([("So the first thing to understand is that cables carry the internet under the oceans.", 0),
              ("So the first thing to understand is that undersea cables carry nearly all of the internet.", 1.4),      # a retake of the line above
              ("First a packet leaves your phone and finds the nearest tower.", 1.2),
              ("Now let me", 1.5), ("Now let me show you how a packet gets from Brazil to Portugal.", 1.1),             # a false start, then the real take
              ("Next we talk about money and ledgers in banking.", 1.3)])                                                # unrelated: must not be flagged
    got = find(ws); kinds = [(g["reason"].split(" (")[0], g["cut_text"][:20]) for g in got]
    assert ("retake", "So the first thing t") in kinds, kinds
    assert any(k == "false start" and t.startswith("Now let me") and len(t) < 12 for k, t in kinds), kinds
    assert not any("money" in g["cut_text"] or "money" in g["keep_text"] for g in got), got
    assert all(g["cut"][1] <= g["keep"][0] for g in got), got                      # the candidate to cut is always the earlier take
    print(f"find_retakes selftest: ok ({len(got)} candidates: " + ", ".join(k for k, _ in kinds) + ")")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest": selftest(); sys.exit(0)
    ap = argparse.ArgumentParser(); ap.add_argument("transcript"); ap.add_argument("--out"); ap.add_argument("--gap", type=float, default=0.85)
    ap.add_argument("--window", type=float, default=75.0); ap.add_argument("--similar", type=float, default=0.34); a = ap.parse_args()
    found = find(json.load(open(a.transcript))["words"], a.gap, a.window, a.similar)
    for g in found: print(f"  {g['cut'][0]:7.2f} to {g['cut'][1]:7.2f} s  cut candidate, {g['reason']}\n      says: {g['cut_text'][:110]}\n      kept: {g['keep'][0]:.2f} to {g['keep'][1]:.2f} s  {g['keep_text'][:110]}")
    print(f"find_retakes: {len(found)} candidate(s); nothing was edited. Approve each, then remove the span from edit.json's segments and read review.md.")
    if a.out: json.dump({"candidates": found}, open(a.out, "w"), indent=1)
