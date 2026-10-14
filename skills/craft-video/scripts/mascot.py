#!/usr/bin/env python3
"""mascot.py: check a mascot cue file and turn it into the spec the Clawd overlay page reads.

  mascot.py mascot.json --out spec.json [--timeline work/timeline.json] [--duration S] [--sheet]    prints one JSON line: start, end, stills, warnings
                                                                                           (--sheet: the spec makes the page draw a labelled review sheet of the stills instead)
  mascot.py --emotions                                                                     the 31 emotions, the hats and the emotes
  mascot.py --selftest

mascot.json (reference/mascot.md has the craft):
  { "bpm": 100,                                    the music bed's tempo, so the idle bounce lands on its beat ("offset": seconds to its first downbeat)
    "outline": 3,                                  a paper-cream die-cut edge in px at 1080 high (0 = none): keeps the dark ink marks readable on a dark picture
    "on":   [ { "from": "@reveal-0.4", "to": 21.0, "side": "right", "u": 22, "enter": "neutral" } ],      one entry per appearance
    "cues": [ ["@reveal", "surprised"], ["@proof.end+1.2", "happy", {"emote": "spark"}] ] }              what it feels: [time, emotion, overrides?]
A cue can make him wave until the next cue: ["@intro", "happy", {"wave": true}] (or {"wave": {"arm": "L", "hz": 2.8, "amp": 0.5, "base": 1.22}}).
A time is seconds, or "@moment" (a name in timeline.json's moments, see anchors.py), with ".end" for the end of that moment and "+0.4" / "-0.4" as an offset:
"@reveal", "@reveal.end", "@reveal-0.4", "@proof.end+0.3". Every problem is reported in one run and nothing is written unless there are none.
"""
import argparse, difflib, json, os, re, sys

# the kit's own tables (ClaudeAnimationBase 0ac8bf2, ANIMATION_GUIDE.md): the checks here refuse a typo before a render spends minutes on it
EMOTIONS = ("happy excited laugh love proud starstruck playful hopeful relieved smug cool mischief suspicious sad cry bored sleepy ko "
            "angry furious determined disgusted scared nervous surprised confused dizzy neutral thinking idea shy").split()
HATS = "party hard crown halo wizard hood top fedora band sweatband beanie bow flower headphones cat masq mask bowtie".split()
EMOTES = ["!", "?", "!!", "!?", "zzz", "sweat", "spark", "heart", "hearts", "anger", "steam", "bulb", "dots", "scribble", "music", "swirl", "stars", "cloud"]
OVERRIDES = set("hat emote emoteK lookX lookY view flip blush gloom lid squint tint tintK rot dx dy sq aL aR eyes mouth seed smear smearDir noLegs sx sy col dk lt wave".split())
WAVE = {"arm": ("R", "L"), "hz": (0.5, 6.0), "amp": (0.0, 1.0), "base": (0.4, 1.6)}   # wave: true, or any of these; arm R is the viewer's right, base and amp are radians (0 straight out, positive up)
MIN_WAVE = 1.4     # a wave springs up in 0.3 s, needs a few strokes, and lowers in 0.35 s
DEFAULTS = {"side": "right", "u": 22.0, "margin": 0.05, "ground": 0.80}   # u is the body unit in px at 1080 high; ground is where the feet stand (the caption band starts at 0.82)
MIN_HOLD = 0.6      # a face needs about half a second to be found, understood and to register before the next one


class Bad(Exception):
    pass


def when(spec, moments, where):
    """seconds, or @moment[.start|.end][+-offset]"""
    if isinstance(spec, (int, float)) and not isinstance(spec, bool):
        return float(spec)
    if not (isinstance(spec, str) and spec.startswith("@")):
        raise Bad(f"{where}: a time is seconds or '@moment', got {spec!r}")

    def look(b):
        edge = "start"
        m = re.fullmatch(r"(.+)\.(start|end)", b)
        if m:
            b, edge = m.groups()
        return moments[b][edge] if b in moments else None
    body, off = spec[1:], 0.0
    t = look(body)                                            # a moment's own name wins (names may hold hyphens), then name plus an offset
    if t is None:
        m = re.fullmatch(r"(.+?)([+-]\d+(?:\.\d+)?)", body)
        if m and look(m.group(1)) is not None:
            t, off = look(m.group(1)), float(m.group(2))
    if t is None:
        raise Bad(f"{where}: no moment '{spec}'" + (f" (known: {', '.join(sorted(moments))})" if moments else " (no timeline with moments given: run anchors.py, pass --timeline)"))
    return float(t) + off


def resolve(cfg, moments, duration=None):
    errors, warnings = [], []

    def need(fn, *a):
        try:
            return fn(*a)
        except Bad as e:
            errors.append(str(e))
    if cfg.get("character", "clawd") != "clawd":
        errors.append(f"character: only 'clawd' is supported (got {cfg['character']!r})")
    bpm, offset = float(cfg.get("bpm", 100)), float(cfg.get("offset", 0))
    walk, turn = float(cfg.get("walk", 0.9)), float(cfg.get("turn", 0.16))
    outline = float(cfg.get("outline", 3))                    # a paper-cream die-cut edge, px at 1080 high; 0 for none
    if not 40 <= bpm <= 240:
        errors.append(f"bpm {bpm:g} is outside 40 to 240")
    if not 0 <= outline <= 12:
        errors.append(f"outline {outline:g} is outside 0 to 12")
    floor = 2 * walk + 2 * turn + 0.8                         # walk in, turn, a moment on screen, turn, walk out
    ons = []
    for i, a in enumerate(cfg.get("on", []), 1):
        where = f"on[{i}]"
        t0, t1 = need(when, a.get("from"), moments, where + ".from"), need(when, a.get("to"), moments, where + ".to")
        o = {**DEFAULTS, **{k: a[k] for k in ("side", "u", "margin", "ground") if k in a}, "enter": a.get("enter", "neutral")}
        if o["side"] not in ("left", "right"): errors.append(f"{where}.side must be left or right")
        if not 4 <= o["u"] <= 60: errors.append(f"{where}.u {o['u']:g} is outside 4 to 60 (22 is a sidekick on a 1080p frame)")
        if not 0 <= o["margin"] <= 0.3: errors.append(f"{where}.margin {o['margin']:g} is outside 0 to 0.3")
        if not 0.3 <= o["ground"] <= 1.0: errors.append(f"{where}.ground {o['ground']:g} is outside 0.3 to 1")
        if o["enter"] not in EMOTIONS: errors.append(f"{where}.enter: unknown emotion '{o['enter']}'")
        if t0 is None or t1 is None:
            continue
        if t1 - t0 < floor:
            errors.append(f"{where} lasts {t1 - t0:.2f} s but needs at least {floor:.2f} s (walk in, turn, a moment on screen, turn, walk out)")
        if duration is not None and t1 > duration + 1e-6:
            errors.append(f"{where} ends at {t1:.2f} s, after the video's {duration:.2f} s")
        if t0 < -1e-6:
            errors.append(f"{where} starts before 0 ({t0:.2f} s)")
        ons.append({"from": round(t0, 3), "to": round(t1, 3), **o, "cues": []})
    ons.sort(key=lambda q: q["from"])
    for p, q in zip(ons, ons[1:]):
        if q["from"] < p["to"] - 1e-6:
            errors.append(f"two appearances overlap: {p['from']:.2f} to {p['to']:.2f} s and {q['from']:.2f} to {q['to']:.2f} s")

    for j, c in enumerate(cfg.get("cues", []), 1):
        where = f"cues[{j}]"
        if not (isinstance(c, (list, tuple)) and 2 <= len(c) <= 3):
            errors.append(f"{where}: expected [time, emotion] or [time, emotion, overrides]")
            continue
        t, name, over = need(when, c[0], moments, where), c[1], (c[2] if len(c) == 3 else {})
        if name not in EMOTIONS:
            near = difflib.get_close_matches(str(name), EMOTIONS, 1)
            errors.append(f"{where}: unknown emotion '{name}'" + (f", did you mean '{near[0]}'?" if near else "") + " (mascot.py --emotions lists them)")
        if not isinstance(over, dict):
            errors.append(f"{where}: overrides must be an object")
            continue
        for k, v in over.items():
            if k not in OVERRIDES: errors.append(f"{where}: unknown override '{k}'")
        w = over.get("wave")
        if "wave" in over and w is not True and not isinstance(w, dict):
            errors.append(f"{where}: wave is true or an object with arm, hz, amp, base (got {w!r})")
        elif isinstance(w, dict):
            for k, v in w.items():
                if k not in WAVE: errors.append(f"{where}: unknown wave setting '{k}' (arm, hz, amp, base)")
                elif k == "arm" and v not in WAVE["arm"]: errors.append(f"{where}: wave.arm must be R or L")
                elif k != "arm" and not (isinstance(v, (int, float)) and not isinstance(v, bool) and WAVE[k][0] <= v <= WAVE[k][1]): errors.append(f"{where}: wave.{k} {v!r} is outside {WAVE[k][0]:g} to {WAVE[k][1]:g}")
        if over.get("hat") not in (None, *HATS): errors.append(f"{where}: unknown hat '{over['hat']}'")
        if over.get("emote") not in (None, *EMOTES): errors.append(f"{where}: unknown emote '{over['emote']}'")
        if t is None or name not in EMOTIONS:
            continue
        home = next((a for a in ons if a["from"] - 1e-6 <= t <= a["to"] + 1e-6), None)
        if home is None:
            warnings.append(f"{where} at {t:.2f} s is outside every appearance: ignored")
        else:
            home["cues"].append([round(t, 3), name, over])
    if errors:
        raise Bad("\n".join(errors))

    stills = []
    for a in ons:
        a["cues"].sort(key=lambda k: k[0])
        if not a["cues"] or a["cues"][0][0] > a["from"] + 1e-6:
            a["cues"].insert(0, [a["from"], a["enter"], {}])  # the face it walks in with
        for k, n in zip(a["cues"], a["cues"][1:]):
            if n[0] - k[0] < MIN_HOLD:
                warnings.append(f"{k[1]} at {k[0]:.2f} s is held {n[0] - k[0]:.2f} s before {n[1]}: a face needs about {MIN_HOLD:g} s to be read")
        for k, n in zip(a["cues"], a["cues"][1:] + [[a["to"] - walk - turn, "", {}]]):
            if k[2].get("wave") and n[0] - k[0] < MIN_WAVE:
                warnings.append(f"the wave at {k[0]:.2f} s lasts {n[0] - k[0]:.2f} s (to the next cue or the turn to leave): it needs about {MIN_WAVE:g} s to spring up, swing a few times and lower")
        for k in a["cues"][1:]:
            if k[0] < a["from"] + walk + turn: warnings.append(f"{k[1]} at {k[0]:.2f} s fires while it is still walking in")
            if k[0] > a["to"] - walk - turn: warnings.append(f"{k[1]} at {k[0]:.2f} s fires while it is leaving")
        settled = a["to"] - walk - turn - 0.05       # the review stills: the face it arrives with, then each cue once its take has settled
        stills += [a["from"] + walk + turn + 0.3] + [min(k[0] + 0.55, settled) for k in a["cues"][1:]]
    start, end = (min(a["from"] for a in ons), max(a["to"] for a in ons)) if ons else (0.0, 0.0)
    stills = sorted({round(t, 2) for t in stills})
    if len(stills) > 12: stills = [stills[round(i * (len(stills) - 1) / 11)] for i in range(12)]
    spec = {"mascot": {"character": "clawd", "bpm": bpm, "offset": offset, "t0": start, "walk": walk, "turn": turn, "outline": outline, "on": ons}}
    return spec, start, end, stills, warnings


def selftest():
    mo = {"reveal": {"start": 10.0, "end": 11.2}, "big-number": {"start": 20.0, "end": 21.0}}
    assert when("@reveal", mo, "t") == 10.0 and when("@reveal.end", mo, "t") == 11.2
    assert abs(when("@reveal-0.4", mo, "t") - 9.6) < 1e-9 and abs(when("@reveal.end+0.3", mo, "t") - 11.5) < 1e-9
    assert when("@big-number", mo, "t") == 20.0 and abs(when("@big-number-0.5", mo, "t") - 19.5) < 1e-9     # a hyphen in a name is not an offset
    cfg = {"on": [{"from": "@reveal-0.5", "to": "@big-number.end+4"}],
           "cues": [["@reveal", "surprised"], ["@reveal.end+1", "happy", {"emote": "spark"}], ["@big-number", "idea", {"hat": "party"}], [40, "sad"]]}
    spec, start, end, stills, warns = resolve(cfg, mo, 60)
    a = spec["mascot"]["on"][0]
    assert (start, end) == (9.5, 25.0) and a["cues"][0] == [9.5, "neutral", {}], a["cues"]
    assert [k[0] for k in a["cues"]] == [9.5, 10.0, 12.2, 20.0] and a["side"] == "right" and 0 < len(stills) <= 12
    assert any("outside every appearance" in w for w in warns), warns
    assert any("still walking in" in w for w in warns), warns          # 'surprised' lands 0.5 s after it enters, inside the walk
    bad = [({"on": [{"from": 1, "to": 3}]}, "needs at least"),
           ({"on": [{"from": 1, "to": 9}, {"from": 8, "to": 15}]}, "overlap"),
           ({"on": [{"from": 1, "to": 9}], "cues": [[3, "surprize"]]}, "did you mean 'surprised'"),
           ({"on": [{"from": 1, "to": 9}], "cues": [[3, "happy", {"lookx": 1}]]}, "unknown override 'lookx'"),
           ({"on": [{"from": 1, "to": 9}], "cues": [[3, "happy", {"hat": "sombrero"}]]}, "unknown hat"),
           ({"on": [{"from": "@nope", "to": 9}]}, "no moment '@nope'"),
           ({"on": [{"from": 50, "to": 70}]}, "after the video's"),
           ({"on": [{"from": 1, "to": 9, "side": "up"}]}, "left or right")]
    for c, want in bad:
        try:
            resolve(c, mo, 60)
        except Bad as e:
            assert want in str(e), (want, str(e))
        else:
            raise AssertionError(f"accepted {c}")
    ok = {"on": [{"from": 1, "to": 12}], "cues": [[4, "happy", {"wave": True}], [7, "neutral"], [8, "happy", {"wave": {"arm": "L", "hz": 3, "amp": 0.4, "base": 1.3}}]]}
    spec2, _, _, _, w2 = resolve(ok, {}, 60); assert spec2["mascot"]["on"][0]["cues"][1][2] == {"wave": True} and not any("wave" in x for x in w2), w2
    for c, want in (({"on": [{"from": 1, "to": 12}], "cues": [[4, "happy", {"wave": "yes"}]]}, "wave is true or an object"),
                    ({"on": [{"from": 1, "to": 12}], "cues": [[4, "happy", {"wave": {"arm": "up"}}]]}, "wave.arm must be R or L"),
                    ({"on": [{"from": 1, "to": 12}], "cues": [[4, "happy", {"wave": {"hz": 20}}]]}, "wave.hz 20 is outside 0.5 to 6"),
                    ({"on": [{"from": 1, "to": 12}], "cues": [[4, "happy", {"wave": {"speed": 2}}]]}, "unknown wave setting 'speed'")):
        try:
            resolve(c, {}, 60)
        except Bad as e:
            assert want in str(e), (want, str(e))
        else:
            raise AssertionError(f"accepted {c}")
    assert any("the wave at 4.00 s lasts 0.90 s" in x for x in resolve({"on": [{"from": 1, "to": 12}], "cues": [[4, "happy", {"wave": True}], [4.9, "neutral"]]}, {}, 60)[4])
    assert any("the wave at 10.00 s lasts" in x for x in resolve({"on": [{"from": 1, "to": 12}], "cues": [[10, "happy", {"wave": True}]]}, {}, 60)[4])      # a last cue waves until he turns to leave
    fast = {"on": [{"from": 1, "to": 12}], "cues": [[4, "happy"], [4.3, "sad"]]}
    assert any("held 0.30 s" in w for w in resolve(fast, {}, 60)[4])
    kit = os.path.join(os.environ.get("MASCOT_DIR") or os.path.expanduser("~/.local/share/craftvideo/mascot"), "clawd", "clawd.js")
    if os.path.exists(kit):                                   # when the kit is installed, the emotion list above must be the kit's own
        heard = re.findall(r"^  (\w+):\s+\{\s*eyes", open(kit, encoding="utf-8").read(), re.M)
        assert sorted(heard) == sorted(EMOTIONS), sorted(set(heard) ^ set(EMOTIONS))
    print("mascot selftest: ok")


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("cues", nargs="?"); ap.add_argument("--out"); ap.add_argument("--timeline"); ap.add_argument("--duration", type=float)
    ap.add_argument("--emotions", action="store_true"); ap.add_argument("--selftest", action="store_true"); ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    if a.selftest: return selftest()
    if a.emotions:
        print("emotions:", " ".join(EMOTIONS)); print("hats:", " ".join(HATS)); print("emotes:", " ".join(EMOTES)); return
    if not a.cues or not a.out: sys.exit(__doc__)
    cfg = json.load(open(a.cues, encoding="utf-8"))
    moments = json.load(open(a.timeline, encoding="utf-8")).get("moments", {}) if a.timeline else {}
    try:
        spec, start, end, stills, warns = resolve(cfg, moments, a.duration)
    except Bad as e:
        for line in str(e).splitlines(): print("mascot: " + line, file=sys.stderr)
        sys.exit(1)
    if not spec["mascot"]["on"]: sys.exit("mascot: the cue file has no 'on' entries, so the mascot is never on screen")
    for w in warns: print("mascot: warning: " + w, file=sys.stderr)
    if a.sheet: spec["mascot"]["sheet"] = stills
    json.dump(spec, open(a.out, "w"), indent=1)
    print(json.dumps({"start": start, "end": end, "stills": stills, "warnings": len(warns)}))


if __name__ == "__main__":
    main()
