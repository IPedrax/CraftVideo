#!/usr/bin/env python3
"""review_edit.py edit.json OUT.mp4 REVIEW_DIR [--transcript T.json]: what the edit did, for a person (or Claude) to check.

Writes REVIEW_DIR/review.md and REVIEW_DIR/cuts.jpg.
review.md   every cut: where it falls in the output, how much was removed, and the WORDS that were removed. A cut that removed a real
            sentence is the failure to catch here; fillers are marked, everything else is listed in full.
cuts.jpg    one row per cut (up to 8): the frame just before the cut on the left, just after on the right. Jump cuts and zoom
            changes show up at a glance; look for a mouth mid-word or a jump between unrelated shots.
Look at both before the edit leaves your hands."""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edl import load

FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "mm", "mmm"}   # the planner's list


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("edl"); ap.add_argument("out"); ap.add_argument("dir"); ap.add_argument("--transcript")
    a = ap.parse_args(); os.makedirs(a.dir, exist_ok=True)
    e = load(a.edl); segs = e["segments"]; words = json.load(open(a.transcript))["words"] if a.transcript else []
    L = ["# Edit review", "", f"Source {e['stats']['source_duration']}s, edited {sum(s['out'] - s['in'] for s in segs):.1f}s, {len(segs)} segments.", ""]
    L += ["| # | output time | removed | words removed |", "|---|---|---|---|"]
    t, risky = 0.0, 0
    for i in range(len(segs) - 1):
        t += segs[i]["out"] - segs[i]["in"]; a0, b0 = segs[i]["out"], segs[i + 1]["in"]
        gone = [w for w in words if a0 <= (w["start"] + w["end"]) / 2 < b0]
        real = [w["text"] for w in gone if w["text"].lower().strip(".,!?") not in FILLERS]
        risky += len(real) > 2
        txt = " ".join(("~~" + w["text"] + "~~") if w["text"].lower().strip(".,!?") in FILLERS else w["text"] for w in gone) or "(silence)"
        L.append(f"| {i + 1} | {t:.2f}s | {b0 - a0:.2f}s | {txt}{' **<- check this**' if len(real) > 2 else ''} |")
    if not words: L.append("\n(no transcript given, so the removed words are not listed)")
    if risky: L.append(f"\n{risky} cut(s) removed more than two real words. Confirm that content was meant to go.")
    open(os.path.join(a.dir, "review.md"), "w").write("\n".join(L) + "\n")
    if len(segs) > 1:
        t, k = 0.0, 0
        for i in range(min(8, len(segs) - 1)):
            t += segs[i]["out"] - segs[i]["in"]
            for dt in (-0.1, 0.1):
                k += 1
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{max(0, t + dt):.3f}", "-i", a.out, "-frames:v", "1", "-vf", "scale=480:-2", os.path.join(a.dir, f"c{k:03d}.jpg")], check=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", "1", "-i", os.path.join(a.dir, "c%03d.jpg"), "-vf", f"tile=2x{k // 2}:padding=6:color=black", "-frames:v", "1", os.path.join(a.dir, "cuts.jpg")], check=True)
        for j in range(1, k + 1): os.remove(os.path.join(a.dir, f"c{j:03d}.jpg"))
    print(f"{a.dir}/review.md, {len(segs) - 1} cuts" + (f", {a.dir}/cuts.jpg" if len(segs) > 1 else ""))


if __name__ == "__main__":
    main()
