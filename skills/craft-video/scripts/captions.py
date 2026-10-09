#!/usr/bin/env python3
"""captions.py: captions for the EDITED video from the original transcript.

  captions.py --transcript T.json --edl edit.json --srt out.srt [--ass out.ass] [--style box|plain|karaoke]
              [--max-chars 42] [--max-lines 2] [--max-dur 6] [--font "Noto Sans"] [--accent "#ff2e88"]

Word times are remapped through the edit decision list: a word inside a kept segment moves to its new position, a word inside a removed
span (a cut filler, trimmed dead air) disappears, a word cut in half is clipped. Words are grouped into readable cues (<= max-chars per
line, <= max-lines lines, <= max-dur seconds, broken at sentence ends and long pauses), never overlapping, each on screen at least 0.6 s.
SRT is for sidecar files and other editors; ASS is what gets burned in (styles: box = white text on a dark box, plain = outlined text,
karaoke = the spoken word turns the accent colour). Sizes scale with the output height (the width for portrait, which also gets 26-character lines and a higher margin).
Cue-level source transcripts have estimated word times (transcript.approx_word_times), so captions follow them only approximately."""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edl import load


def srt_t(t):
    t = max(0.0, t); h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}".replace(",1000", ",999")


def ass_t(t):
    t = max(0.0, t); h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def ass_colour(hexs, alpha=0):
    hexs = hexs.lstrip("#"); r, g, b = hexs[0:2], hexs[2:4], hexs[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def remap(words, segs):
    out, off = [], 0.0
    for k, s in enumerate(segs):
        L = s["out"] - s["in"]
        for w in words:
            mid = (w["start"] + w["end"]) / 2
            if s["in"] <= mid < s["out"]:
                ns = off + max(w["start"], s["in"]) - s["in"]; ne = off + min(w["end"], s["out"]) - s["in"]
                if ne - ns >= 0.02: out.append({"text": w["text"], "start": ns, "end": ne, "seg": k})
        off += L
    return out


def cues_from(words, max_chars, max_lines, max_dur):
    cues, cur = [], []
    def flush():
        nonlocal cur
        if cur: cues.append(cur); cur = []
    def text_len(ws): return len(" ".join(w["text"] for w in ws))
    for i, w in enumerate(words):
        if cur:
            gap = w["start"] - cur[-1]["end"]
            # a cut between kept segments is a trimmed pause, so it is a phrase boundary once the cue has some body
            cut = w.get("seg") != cur[-1].get("seg") and text_len(cur) >= max_chars * 0.4
            if (gap > 0.7 or cut or text_len(cur + [w]) > max_chars * max_lines or w["end"] - cur[0]["start"] > max_dur):
                flush()
        cur.append(w)
        if re.search(r"[.!?]$", w["text"]) and (len(cur) >= 3 or cur[-1]["end"] - cur[0]["start"] >= 1.2): flush()
    flush()
    return cues


def lines_of(ws, max_chars, max_lines):
    toks = [w["text"] for w in ws]; lines, cur = [], ""
    for t in toks:
        if cur and len(cur) + 1 + len(t) > max_chars: lines.append(cur); cur = t
        else: cur = (cur + " " + t).strip()
    lines.append(cur)
    while len(lines) > max_lines:                      # too many lines: merge the shortest neighbours
        i = min(range(len(lines) - 1), key=lambda k: len(lines[k]) + len(lines[k + 1]))
        lines[i:i + 2] = [lines[i] + " " + lines[i + 1]]
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True); ap.add_argument("--edl", required=True)
    ap.add_argument("--srt", required=True); ap.add_argument("--ass")
    ap.add_argument("--style", default="box", choices=["box", "plain", "karaoke"])
    ap.add_argument("--max-chars", type=int, default=None, help="default 42 (26 for portrait)"); ap.add_argument("--max-lines", type=int, default=2); ap.add_argument("--max-dur", type=float, default=6.0)
    ap.add_argument("--font", default="Noto Sans"); ap.add_argument("--accent", default="#ff2e88")
    a = ap.parse_args()
    t = json.load(open(a.transcript)); e = load(a.edl)
    o = e.get("output", {}); W = o.get("width") or 1920; H = o.get("height") or 1080; portrait = H > W
    if a.max_chars is None: a.max_chars = 26 if portrait else 42
    words = remap(t["words"], e["segments"])
    if not words: sys.exit("captions: no words fall inside the kept segments")
    # words the cuts removed that no planned filler cut explains: the sign of a mistimed transcript, so say so instead of silently losing them
    planned = [(c["word"].lower(), c["at"]) for c in (e.get("stats") or {}).get("filler_cuts", [])]
    lost = [w for w in t["words"] if not any(s["in"] <= (w["start"] + w["end"]) / 2 < s["out"] for s in e["segments"])
            and not any(abs(w["start"] - at) < 0.2 and re.sub(r"\W", "", w["text"].lower()) == re.sub(r"\W", "", wd) for wd, at in planned)]
    if lost: print(f"captions: warning: {len(lost)} word(s) fall in removed spans without being a planned cut: " + ", ".join(f"'{w['text']}' {w['start']:.1f}s" for w in lost[:6]) + (" ..." if len(lost) > 6 else ""), file=sys.stderr)
    cues = cues_from(words, a.max_chars, a.max_lines, a.max_dur)
    # timing polish: minimum 0.6 s on screen, never overlap the next cue
    spans = []
    for i, c in enumerate(cues):
        s, en = c[0]["start"], c[-1]["end"]
        nxt = cues[i + 1][0]["start"] if i + 1 < len(cues) else en + 1.0
        spans.append((s, min(max(en, s + 0.6), nxt - 0.02) if nxt - 0.02 > s else en))
    with open(a.srt, "w", encoding="utf-8") as f:
        for i, (c, (s, en)) in enumerate(zip(cues, spans), 1):
            f.write(f"{i}\n{srt_t(s)} --> {srt_t(en)}\n" + "\n".join(lines_of(c, a.max_chars, a.max_lines)) + "\n\n")
    if a.ass:
        # portrait: size from the width (the height would give 3 wrapped lines) and sit above the platform UI zone
        size = round(0.065 * W) if portrait else round(0.052 * H); mv = round((0.17 if portrait else 0.075) * H); ml = round(0.06 * W)
        if a.style == "box": bs, outline, shadow = 3, round(0.012 * H), 0
        else: bs, outline, shadow = 1, max(2, round(0.004 * H)), 1
        prim, sec = ("&H00FFFFFF", "&H00FFFFFF") if a.style != "karaoke" else (ass_colour(a.accent), "&H00FFFFFF")
        hdr = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
               f"[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
               f"ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
               f"Style: Default,{a.font},{size},{prim},{sec},&H00000000,&H99000000,-1,0,0,0,100,100,0,0,{bs},{outline},{shadow},2,{ml},{ml},{mv},1\n\n"
               f"[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        with open(a.ass, "w", encoding="utf-8") as f:
            f.write(hdr)
            for c, (s, en) in zip(cues, spans):
                if a.style == "karaoke":
                    parts = []
                    for k, w in enumerate(c):
                        nxt = c[k + 1]["start"] if k + 1 < len(c) else w["end"]
                        parts.append(f"{{\\k{max(1, round((nxt - w['start']) * 100))}}}{w['text'].replace('{', '(').replace('}', ')')} ")
                    txt = "".join(parts).strip()
                else:
                    txt = "\\N".join(l.replace("{", "(").replace("}", ")") for l in lines_of(c, a.max_chars, a.max_lines))
                f.write(f"Dialogue: 0,{ass_t(s)},{ass_t(en)},Default,,0,0,0,,{txt}\n")
    approx = t.get("approx_word_times")
    print(f"{a.srt}: {len(cues)} cues, {len(words)} of {len(t['words'])} words kept, last cue ends {spans[-1][1]:.1f}s"
          f"{' (word times are approximate)' if approx else ''}{', ASS ' + a.style + ' style written' if a.ass else ''}")


if __name__ == "__main__":
    main()
