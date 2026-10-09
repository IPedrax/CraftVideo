#!/usr/bin/env python3
"""synth_music.py: a generated soundtrack (no samples, nothing fetched) that follows your scene cuts.

pad + sub bass + plucked arpeggio + boom hits + beat thumps + risers + count-up ticks + a short synthetic reverb,
then ducked under the narration. Stereo 48 kHz WAV, peak normalised to -6 dBFS (mix it lower in the editor).

  synth_music.py --cues cues.json --narration narration.wav --out music.wav [--seed 7]

cues.json (all times in seconds; every key optional except duration):
  {"duration":30, "bpm":100,
   "progression":["Am","F","C","G", ...],      one triad per bar, bars start at 0 (major "C", minor "Am", "Bb", "F#m")
   "hits":   [[time, level], ...],              low boom (level ~0.5; the final one ~0.95)
   "arp":    [[time, level], ...],              arpeggio density; a level holds until the next entry, 0 = off
   "pulse":  [[time, "half"|"every"|"off"], ...] soft thump every other beat / every beat / stop
   "risers": [[start, end, level], ...],
   "ticks":  [[start, end, seconds_between], ...]   quiet rising blips under count-ups}
Needs numpy + soundfile (the VoiceStudio venv has them)."""
import argparse, json, re
import numpy as np
import soundfile as sf

SR = 48000
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7,
        "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def hz(m): return 440.0 * 2 ** ((m - 69) / 12)


def triad(name):
    m = re.match(r"^([A-G][#b]?)(m)?$", name)
    if not m:
        raise SystemExit(f"unsupported chord '{name}' (use triads like Am, F, C#m, Bb)")
    r = NOTE[m.group(1)]
    root = next(v for v in range(53, 65) if v % 12 == r)         # keep the pad in F3..E4
    return [root, root + (3 if m.group(2) else 4), root + 7]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cues", required=True)
    ap.add_argument("--narration")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    cues = json.load(open(a.cues))
    DUR = float(cues["duration"]); N = int(SR * DUR)
    BEAT = 60.0 / float(cues.get("bpm", 100)); BAR = 4 * BEAT
    prog = cues.get("progression", ["Am", "F", "C", "G"] * 4)
    rng = np.random.default_rng(a.seed)

    def adsr(n, atk, rel):
        e = np.ones(n); na, nr = int(atk * SR), int(rel * SR)
        e[:na] = np.linspace(0, 1, na) ** 2
        e[-nr:] *= np.linspace(1, 0, nr) ** 2
        return e

    def add(buf, sig, start):
        i = int(start * SR)
        if i >= len(buf): return
        j = min(len(buf), i + len(sig)); buf[i:j] += sig[: j - i]

    def saw(f, n, cents=(-7, 0, 7), top=1800.0):
        tt = np.arange(n) / SR; out = np.zeros(n)
        for c in cents:
            ff = f * 2 ** (c / 1200); ph = rng.uniform(0, 2 * np.pi)
            for k in range(1, int(top / ff) + 1):
                out += np.sin(2 * np.pi * k * ff * tt + ph * k) / k
        return out / len(cents)

    nbars = int(np.ceil(DUR / BAR))                                # last bar may run past the end; it is truncated
    chord_at = lambda bi: prog[min(bi, len(prog) - 1)]
    # --- pad ---
    pad = np.zeros(N)
    for bi in range(nbars):
        n = int((BAR + 1.0) * SR)
        ch = sum(saw(hz(m), n) for m in triad(chord_at(bi))) / 3
        add(pad, ch * adsr(n, 0.7, 1.0) * 0.5, bi * BAR)
    # --- sub ---
    sub = np.zeros(N)
    for bi in range(nbars):
        n = int((BAR + 0.3) * SR); tt = np.arange(n) / SR
        add(sub, np.sin(2 * np.pi * hz(triad(chord_at(bi))[0] - 12) * tt) * adsr(n, 0.05, 0.4) * 0.55, bi * BAR)

    # --- arp ---
    def pluck(f, n=int(0.5 * SR)):
        tt = np.arange(n) / SR
        return (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * 2 * f * tt)) * np.exp(-tt / 0.13)

    def level_at(table, x, default=0.0):
        v = default
        for t, l in table:
            if x >= t: v = l
        return v
    arp_t = cues.get("arp", [])
    arp = np.zeros(N); step = BEAT / 2
    for i in range(int(DUR / step)):
        x = i * step; lv = level_at(arp_t, x)
        if lv == 0: continue
        notes = [m + 12 for m in triad(chord_at(int(x // BAR)))]
        notes = notes + [notes[0] + 12]
        add(arp, pluck(hz(notes[[0, 1, 2, 3, 2, 1, 2, 1][i % 8]])) * lv * 0.30, x)
    d = int(0.45 * SR); echo = np.zeros(N); echo[d:] += arp[:-d] * 0.38; echo[2 * d:] += arp[:-2 * d] * 0.15
    arp = arp + echo

    # --- fx bus: booms, thumps, risers, ticks ---
    fx = np.zeros(N)
    tonic = 33 + ((NOTE[re.match(r"^[A-G][#b]?", chord_at(0)).group(0)] - 9) % 12)
    def boom(level):
        n = int(1.6 * SR); tt = np.arange(n) / SR
        f = hz(tonic) + 40 * np.exp(-tt / 0.05)
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.45)
        nz = rng.standard_normal(n) * np.exp(-tt / 0.03)
        nz = np.convolve(nz, np.ones(24) / 24, mode="same")
        return (s + 0.25 * nz) * level
    for x, lv in cues.get("hits", []): add(fx, boom(lv), x)

    def thump():
        n = int(0.22 * SR); tt = np.arange(n) / SR
        return np.sin(2 * np.pi * np.cumsum(45 + 80 * np.exp(-tt / 0.03)) / SR) * np.exp(-tt / 0.07)
    pulse = cues.get("pulse", [])
    for k in range(int(DUR / BEAT)):
        x = k * BEAT; mode = level_at([(t, m) for t, m in pulse], x, "off") if pulse else "off"
        if mode == "every": add(fx, thump() * 0.42, x)
        elif mode == "half" and k % 2 == 0: add(fx, thump() * 0.30, x)

    def riser(s, e, level):
        n = int((e - s) * SR); tt = np.arange(n) / SR
        ch = np.sin(2 * np.pi * np.cumsum(200 * (3200 / 200) ** (tt / (e - s))) / SR)
        nz = np.convolve(rng.standard_normal(n), np.ones(6) / 6, mode="same")
        return (0.7 * ch + 0.3 * nz) * (tt / (e - s)) ** 2.2 * level
    for s, e, lv in cues.get("risers", []): add(fx, riser(s, e, lv), s)

    def tick(f, n=int(0.03 * SR)):
        tt = np.arange(n) / SR
        return np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.008)
    for s, e, dt in cues.get("ticks", []):
        for i in range(int((e - s) / dt)):
            add(fx, tick(660 + 660 * (i * dt) / (e - s)) * 0.07, s + i * dt)

    # --- reverb on pad + arp, tiny Haas width on the right ---
    def ir(seed):
        r = np.random.default_rng(seed); n = int(1.5 * SR); tt = np.arange(n) / SR
        x = r.standard_normal(n) * np.exp(-tt / 0.38)
        return x - np.convolve(x, np.ones(48) / 48, mode="same")

    def fconv(x, h):
        n = len(x) + len(h) - 1; m = 1 << (n - 1).bit_length()
        return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(h, m), m)[: len(x)]
    bus = pad + arp
    rl, rr = fconv(bus, ir(1)), fconv(bus, ir(2))
    rl /= np.abs(rl).max() + 1e-9; rr /= np.abs(rr).max() + 1e-9
    pk = np.abs(bus).max()
    L = bus + 0.22 * rl * pk * 0.6 + sub + fx
    R = np.roll(bus, int(0.012 * SR)) + 0.22 * rr * pk * 0.6 + sub + fx

    # --- duck under the narration (about -10 dB while it speaks) ---
    duck = np.ones(N)
    if a.narration:
        v, vsr = sf.read(a.narration)
        if v.ndim > 1: v = v.mean(axis=1)
        assert vsr == SR and len(v) == N, f"narration must be {SR} Hz and exactly {DUR}s (got {len(v) / vsr:.3f}s)"
        w = int(0.02 * SR)
        env = np.clip(np.sqrt(np.convolve(v ** 2, np.ones(w) / w, mode="same")) / 0.08, 0, 1)
        att, rel = np.exp(-1 / (0.03 * SR)), np.exp(-1 / (0.28 * SR))
        sm = np.zeros(N); y = 0.0
        for i in range(N):
            xv = env[i]; c = att if xv > y else rel
            y = c * y + (1 - c) * xv; sm[i] = y
        duck = 1 - 0.68 * sm
    music = np.stack([L, R], axis=1) * duck[:, None]
    music[: int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))[:, None]
    music[-int(0.6 * SR):] *= np.linspace(1, 0, int(0.6 * SR))[:, None]
    music *= 0.5 / (np.abs(music).max() + 1e-9)
    assert np.isfinite(music).all()
    sf.write(a.out, music, SR, subtype="PCM_16")
    print(f"{a.out}: {DUR}s stereo {SR} Hz, peak {np.abs(music).max():.2f}"
          f"{', ducked under ' + a.narration if a.narration else ''}")


if __name__ == "__main__":
    main()
