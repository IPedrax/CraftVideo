#!/usr/bin/env python3
"""verify_narration.py: did the voice say what the script says?

  verify_narration.py --audio work/narration_raw.wav --script work/script.txt [--transcript t.json] [--language en] [--max-miss 0.12] [--ignore keyside,quayside]

TTS engines drop, add and swap words ("mostly in force" came back as "enforced"). This transcribes the narration (transcribe.sh, any provider) or reads a
transcript you already have, aligns it to the script word by word, and prints every script line that came back different, what was expected and what was
heard, plus words heard that are in no line. Exit 1 when a line misses more than --max-miss of its words, or 4 or more unscripted words came in a row.
Numbers are not compared by value (the script spells "twenty twenty", a transcript writes "2020"): each run of number words or digits is one token, so
a dropped or added number is caught and a wrong one is not. Check those by ear. `--ignore` drops words you respelled for the voice ("Keyside").
Run it BEFORE tighten_voice.py, on the raw take, so a bad line is regenerated while it is cheap. Needs numpy-free Python 3 only; transcribing needs the
transcribe provider."""
import argparse, difflib, json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
NUMW = set("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty "
           "sixty seventy eighty ninety hundred thousand million billion percent dollar dollars".split())


def read_script(path):
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"): continue
        lab, sep, txt = line.partition("|")
        out.append((lab.strip(), txt.strip()) if sep else (f"s{len(out) + 1}", line))
    return out


def tokens(text, ignore=()):
    """lower-case words; apostrophes dropped; every run of number words or digits becomes one '#'; ignored words removed"""
    out = []
    for w in re.findall(r"[a-z0-9']+", text.lower().replace("’", "'")):
        w = w.replace("'", "")
        if not w or w in ignore: continue
        t = "#" if (w in NUMW or any(c.isdigit() for c in w)) else w
        if t == "#" and out and out[-1] == "#": continue
        out.append(t)
    return out


def glue(seq, vocab):
    """glue 2 to 4 neighbouring tokens when the glued word is what the other side wrote ('sea floor' / 'seafloor', 'l g p d' / 'lgpd')"""
    out, i = [], 0
    while i < len(seq):
        for n in (4, 3, 2):
            part = seq[i:i + n]
            if len(part) == n and "".join(t for t, _ in part) in vocab and not all(t in vocab for t, _ in part):
                out.append(("".join(t for t, _ in part), seq[i][1])); i += n; break
        else: out.append(seq[i]); i += 1
    return out


def verify(lines, heard_words, max_miss=0.12, ignore=()):
    S = [(t, k) for k, (_, txt) in enumerate(lines) for t in tokens(txt, ignore)]
    T = [(t, None) for t in tokens(" ".join(w["text"] for w in heard_words), ignore)]
    S = glue(S, {t for t, _ in T}); T = glue(T, {t for t, _ in S})
    owner = [k for _, k in S]; S = [t for t, _ in S]; T = [t for t, _ in T]
    miss = [0] * len(lines); detail = [[] for _ in lines]; extra = []
    for op, a0, a1, b0, b1 in difflib.SequenceMatcher(None, S, T, autojunk=False).get_opcodes():
        if op == "equal": continue
        if a1 > a0:                                                    # script words that were not heard as written
            for k in sorted(set(owner[a0:a1])):
                n = sum(1 for i in range(a0, a1) if owner[i] == k); miss[k] += n
                detail[k].append((" ".join(S[i] for i in range(a0, a1) if owner[i] == k), " ".join(T[b0:b1])))
        elif b1 > b0:                                                  # words heard that no line has
            extra.append((owner[a0 - 1] if a0 else -1, " ".join(T[b0:b1])))
    total = [max(1, sum(1 for o in owner if o == k)) for k in range(len(lines))]
    bad = [k for k in range(len(lines)) if miss[k] / total[k] > max_miss]
    runs = [e for e in extra if len(e[1].split()) >= 4]
    return {"miss": [m / t for m, t in zip(miss, total)], "detail": detail, "extra": extra, "bad": bad, "extra_runs": runs}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--audio"); ap.add_argument("--script", required=True); ap.add_argument("--transcript")
    ap.add_argument("--language", default=""); ap.add_argument("--max-miss", type=float, default=0.12); ap.add_argument("--ignore", default="")
    a = ap.parse_args(argv); ign = {w.strip().lower() for w in a.ignore.split(",") if w.strip()}
    tr = a.transcript
    if not tr:
        if not a.audio: sys.exit("verify_narration: give --audio (to transcribe) or --transcript")
        tr = tempfile.mkdtemp() + "/t.json"
        r = subprocess.run(["bash", f"{HERE}/transcribe.sh", a.audio, tr] + (["--language", a.language] if a.language else []), capture_output=True, text=True)
        if r.returncode: sys.exit(f"verify_narration: transcribing failed:\n{r.stderr.strip()[-600:]}")
    lines = read_script(a.script); res = verify(lines, json.load(open(tr))["words"], a.max_miss, ign)
    for k, (lab, _) in enumerate(lines):
        if res["detail"][k]:
            print(f"  {'FAIL' if k in res['bad'] else 'diff'} {k + 1:>2} {lab[:12]:<12} {res['miss'][k] * 100:3.0f}% " + "; ".join(f"script [{s}] heard [{h or 'nothing'}]" for s, h in res["detail"][k]))
    for k, words in res["extra"]:
        print(f"  extra  after {('line ' + str(k + 1)) if k >= 0 else 'the start'}: heard [{words}] which no line has")
    bad = len(res["bad"]) + len(res["extra_runs"])
    print(f"verify_narration: {len(lines)} lines, {sum(1 for d in res['detail'] if d)} differ, {len(res['bad'])} over {a.max_miss:.0%}, "
          f"{len(res['extra'])} unscripted passages" + (" -> regenerate the failing lines (reword a name the voice gets wrong)" if bad else " -> the voice read the script"))
    return 1 if bad else 0


def selftest():
    d = tempfile.mkdtemp(); open(f"{d}/s.txt", "w").write("hook | Over ninety nine percent of it travels by cable.\nlaw | It is mostly in force since September twenty twenty.\nend | Sources are on screen.\n")
    W = lambda s: [{"text": w, "start": i * .3, "end": i * .3 + .25} for i, w in enumerate(s.split())]
    ok = verify(read_script(f"{d}/s.txt"), W("Over 99% of it travels by cable. It is mostly in force since September 2020. Sources are on screen."))
    assert not ok["bad"] and not any(ok["detail"]) and not ok["extra"], ok                                  # digits and spelled numbers agree, nothing differs
    bad = verify(read_script(f"{d}/s.txt"), W("Over 99% of it travels by cable. It is enforced since September 2020. Sources are on screen. Captions by example dot com today"))
    assert bad["bad"] == [1] and bad["detail"][1][0][0].startswith("mostly in force") and bad["detail"][1][0][1] == "enforced", bad       # the swapped words are found, and where
    assert bad["extra_runs"] and "captions by example" in bad["extra_runs"][0][1], bad                       # a hallucinated tail is reported
    drop = verify(read_script(f"{d}/s.txt"), W("Over of it travels by cable. It is mostly in force since September 2020. Sources are on screen."))
    assert drop["detail"][0], drop                                                                          # a dropped number is caught
    ign = verify([("a", "Visit Keyside today.")], W("Visit Quayside today."), ignore={"keyside", "quayside"}); assert not any(ign["detail"]), ign
    gl = verify([("a", "The sea floor and the L G P D law.")], W("The seafloor and the LGPD law.")); assert not any(gl["detail"]), gl     # spacing and spelled-out letters are not errors
    print("verify_narration selftest: ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest": selftest()
    else: sys.exit(main())
