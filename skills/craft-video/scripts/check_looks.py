#!/usr/bin/env python3
"""check_looks.py [DIR]: validate every looks/*.json (default: the skill's own looks folder), so a new or edited look cannot ship broken.

  per file   the id matches the file name; colour roles are #rrggbb; ground, ink, muted, accent are present; every type role has family, weight and a size in (0, 0.5];
  contrast   ink and muted against the ground at least 4.5:1 (small text), accent and signal at least 3:1 (large text, shapes)
Exit 1 on any failure. Python 3 only, no packages."""
import glob, json, os, re, sys


def lum(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def check(path):
    bad, L = [], json.load(open(path)); c = L.get("color", {})
    if L.get("id") != os.path.basename(path)[:-5]: bad.append(f"id '{L.get('id')}' does not match the file name")
    for k in ("ground", "ink", "muted", "accent"):
        if k not in c: bad.append(f"color.{k} is missing")
    for k, v in c.items():
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", v): bad.append(f"color.{k} '{v}' is not #rrggbb")
    for role, t in (L.get("type") or {}).items():
        if not (t.get("family") and t.get("weight") and 0 < t.get("size", 0) <= 0.5): bad.append(f"type.{role} needs a family, a weight and a size in (0, 0.5]")
    if not L.get("type"): bad.append("type is missing")
    if not bad:
        for k, need in (("ink", 4.5), ("muted", 4.5), ("accent", 3), ("signal", 3)):
            if k in c and ratio(c[k], c["ground"]) < need: bad.append(f"color.{k} {c[k]} on {c['ground']} is {ratio(c[k], c['ground']):.1f}:1, wanted {need}:1")
    return bad


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "looks")
    fails = 0
    for f in sorted(glob.glob(os.path.join(d, "*.json"))):
        bad = check(f); fails += bool(bad)
        print(f"  {'FAIL' if bad else 'ok  '} {os.path.basename(f)[:-5]:<16}" + ("; ".join(bad) if bad else ""))
    print(f"check_looks: {'all looks are valid' if not fails else str(fails) + ' look(s) failed'}"); sys.exit(1 if fails else 0)
