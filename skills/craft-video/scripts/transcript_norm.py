#!/usr/bin/env python3
"""transcript_norm.py: turn any common transcript into the one format the pipeline uses.

  transcript_norm.py IN OUT [--duration D] [--language en] [--source NAME] [--audio 16k_mono.wav]

Accepts: our own JSON ({"words":[{"text","start","end"}]}), OpenAI-style verbose_json (top-level "words", or
"segments"[].words[] with "word"), faster-whisper-style segments, SRT, and WebVTT. Cue-level formats (SRT/VTT, or segments
without word times) have no word timings, so words are spread across each cue in proportion to their length and the result is
marked "approx_word_times": true (fine for captions, not for frame-accurate filler cuts).
Writes {"language","source","text","approx_word_times","words":[{"text","start","end"}...]}, sorted, clamped, validated.
With --audio, word times are snapped to where the voice really is (see snap_to_speech): speech models stretch the first word of a
sentence back into the silence before it, by up to 0.7 s, and a cut or a caption built on those times loses the word.
Exit 1 with a reason if nothing usable is found."""
import argparse, json, re, sys


def tc(s):
    s = s.strip().replace(",", ".")
    parts = [float(x) for x in s.split(":")]
    while len(parts) < 3: parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def spread(text, start, end):
    toks = text.split()
    if not toks: return []
    w = [max(1, len(t)) for t in toks]; tot = sum(w); t0 = start; out = []
    for tok, wi in zip(toks, w):
        d = (end - start) * wi / tot
        out.append({"text": tok, "start": round(t0, 3), "end": round(t0 + d, 3)}); t0 += d
    return out


def from_cues(text):
    approx_words = []
    for blk in re.split(r"\n\s*\n", text.replace("\r", "")):
        m = re.search(r"(\d+:\d\d:\d\d[.,]\d+|\d+:\d\d[.,]\d+)\s*-->\s*(\d+:\d\d:\d\d[.,]\d+|\d+:\d\d[.,]\d+)", blk)
        if not m: continue
        body = blk[m.end():].strip()
        body = re.sub(r"<[^>]+>", "", " ".join(l.strip() for l in body.splitlines() if l.strip()))
        approx_words += spread(body, tc(m.group(1)), tc(m.group(2)))
    return approx_words


def from_json(d):
    lang = d.get("language")
    def word(w):
        t = (w.get("text") if "text" in w else w.get("word", "")).strip()
        return {"text": t, "start": float(w["start"]), "end": float(w["end"])}
    if isinstance(d.get("words"), list) and d["words"]:
        return [word(w) for w in d["words"]], lang, False
    segs = d.get("segments") or []
    words = [word(w) for s in segs for w in (s.get("words") or [])]
    if words: return words, lang, False
    approx = [w for s in segs for w in spread(s.get("text", ""), float(s["start"]), float(s["end"]))]
    return approx, lang, True


def snap_to_speech(words, wav):
    """Pull word times onto the voiced audio. A word that starts in silence but overlaps a voiced run starts where the run does; one
    that ends in silence ends where the run ends; a word wholly in silence moves onto the next run (within 1 s), else the previous one
    (within 0.5 s). Words stay in order. Returns how many were moved. Not forced alignment: words inside a long run can still be a few
    tenths of a second off, which is fine for cutting at pauses and captioning, not for lip-sync work."""
    import os, numpy as np, soundfile as sf
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from analyze import frame_db, runs_from_db
    x, sr = sf.read(wav)
    db = frame_db(x, sr); noise, loud = float(np.percentile(db, 10)), float(np.percentile(db, 90))
    runs = runs_from_db(db, float(np.clip(noise + 0.35 * (loud - noise), -50.0, -30.0)), 0.06, 0.12)
    moved, prev_end = 0, 0.0
    for w in words:
        s0, e0 = w["start"], w["end"]
        hit = [r for r in runs if r[0] < e0 and r[1] > s0]
        if hit:
            s0, e0 = max(s0, hit[0][0] - 0.02), min(e0, hit[-1][1] + 0.04)
        else:
            nxt = next((r for r in runs if r[0] >= e0 and r[0] - e0 <= 1.0), None)
            before = [r for r in runs if r[1] <= s0 and s0 - r[1] <= 0.5]
            if nxt: d = e0 - s0; s0 = nxt[0]; e0 = min(s0 + d, nxt[1] + 0.04)
            elif before: d = e0 - s0; e0 = before[-1][1] + 0.04; s0 = max(0.0, e0 - d)
        s0 = max(s0, prev_end); e0 = max(e0, s0 + 0.04)
        moved += abs(s0 - w["start"]) > 0.05 or abs(e0 - w["end"]) > 0.05
        w["start"], w["end"] = round(s0, 3), round(e0, 3); prev_end = w["end"]
    return moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out"); ap.add_argument("--audio")
    ap.add_argument("--duration", type=float); ap.add_argument("--language"); ap.add_argument("--source", default="")
    a = ap.parse_args()
    raw = open(a.inp, encoding="utf-8").read()
    lang, approx = a.language, False
    if raw.lstrip().startswith(("{", "[")):
        d = json.loads(raw)
        words, l2, approx = from_json(d if isinstance(d, dict) else {"segments": d})
        lang = lang or l2
    else:
        words, approx = from_cues(raw), True
    words = [w for w in words if w["text"]]
    if not words: sys.exit("transcript_norm: no words found (is the transcript empty, or in a format I do not know?)")
    words.sort(key=lambda w: (w["start"], w["end"]))
    prev = 0.0
    for w in words:
        w["start"] = round(max(0.0, w["start"], 0.0), 3)
        w["end"] = round(max(w["end"], w["start"] + 0.01), 3)
    snapped = snap_to_speech(words, a.audio) if a.audio and not approx else None   # cue-level times are already a guess: leave them
    if a.duration and words[-1]["start"] > a.duration + 1.0:
        sys.exit(f"transcript_norm: words run to {words[-1]['end']:.1f}s but the recording is {a.duration:.1f}s: wrong transcript for this video?")
    out = {"language": lang or "und", "source": a.source, "approx_word_times": approx, "snapped_to_speech": snapped, "text": " ".join(w["text"] for w in words), "words": words}
    json.dump(out, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(f"{a.out}: {len(words)} words, {words[0]['start']:.1f}s to {words[-1]['end']:.1f}s, language {out['language']}"
          f"{', word times are APPROXIMATE (cue-level source)' if approx else ''}{f', {snapped} snapped to the voiced audio' if snapped else ''}")


if __name__ == "__main__":
    main()
