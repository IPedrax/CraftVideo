#!/usr/bin/env python3
"""analyze.py: measure a recording so the edit can be planned from facts, not guesses.

  analyze.py recording.mp4 analysis.json [--min-silence 0.25] [--scene 0.35]

Writes analysis.json:
  source, duration, video {width,height,fps,vfr,codec}, audio {rate,channels,lufs,lra,true_peak_db,sample_peak_db,
  noise_floor_db,speech_level_db,threshold_db}, speech [[s,e]...] (voiced runs), silences [[s,e]...], scenes [t...],
  black [[s,e]...], frozen [[s,e]...], audio_wav (a 16 kHz mono copy the planner reuses for snapping cuts to quiet points)

Speech vs silence is decided against THIS recording's own noise floor (a fixed dB threshold is wrong for most footage):
threshold = noise floor + 35% of the way to the speech level, kept between -50 and -30 dB, with 3 dB of hysteresis.
Needs numpy + soundfile (the VoiceStudio venv has them), ffmpeg and ffprobe."""
import argparse, json, os, re, subprocess, sys
import numpy as np
import soundfile as sf

HOP = 0.02   # 20 ms analysis frames


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path):
    p = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path])
    if p.returncode:
        sys.exit(f"analyze: ffprobe cannot read {path}: {p.stderr.strip()[:200]}")
    d = json.loads(p.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    frac = lambda x: (lambda n, m: n / m if m else 0.0)(*map(float, x.split("/")))
    out = {"duration": float(d["format"]["duration"]), "video": None, "audio": None}
    if v:
        r, av = frac(v.get("r_frame_rate", "0/1")), frac(v.get("avg_frame_rate", "0/1"))
        out["video"] = {"width": v["width"], "height": v["height"], "fps": round(r, 3), "avg_fps": round(av, 3),
                        "vfr": bool(r and av and abs(r - av) / r > 0.01), "codec": v["codec_name"],
                        "rotation": next((int(sd.get("rotation", 0)) for sd in v.get("side_data_list", []) if "rotation" in sd), 0)}
    if a:
        out["audio"] = {"rate": int(a["sample_rate"]), "channels": a["channels"], "codec": a["codec_name"]}
    return out


def extract_wav(path, wav):
    r = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav])
    if r.returncode:
        sys.exit(f"analyze: could not extract audio: {r.stderr.strip()[:200]}")


def frame_db(x, sr):
    n, hop = int(0.03 * sr), int(HOP * sr)
    if len(x) < n:
        return np.array([-90.0])
    idx = np.arange(0, len(x) - n, hop)
    c = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    rms = np.sqrt((c[idx + n] - c[idx]) / n)
    return 20 * np.log10(rms + 1e-9)


def runs_from_db(db, thr, min_speech, min_silence):
    on, hi, lo = False, thr, thr - 3.0
    s = 0
    runs = []
    for i, v in enumerate(db):
        if not on and v > hi:
            on, s = True, i
        elif on and v < lo:
            on = False; runs.append([s * HOP, i * HOP])
    if on:
        runs.append([s * HOP, len(db) * HOP])
    merged = []
    for r in runs:                                   # bridge gaps shorter than min_silence
        if merged and r[0] - merged[-1][1] < min_silence:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return [[round(a, 3), round(b, 3)] for a, b in merged if b - a >= min_speech]


def ffmpeg_filter_log(path, vf=None, af=None):
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", path]
    if vf: cmd += ["-vf", vf, "-an"]
    if af: cmd += ["-af", af, "-vn"]
    return run(cmd + ["-f", "null", "-"]).stderr


def spans(log, start_key, end_key):
    st = [float(x) for x in re.findall(start_key + r":\s*(-?[\d.]+)", log)]
    en = [float(x) for x in re.findall(end_key + r":\s*(-?[\d.]+)", log)]
    return [[round(max(0, s), 3), round(e, 3)] for s, e in zip(st, en)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("out")
    ap.add_argument("--min-silence", type=float, default=0.25)
    ap.add_argument("--min-speech", type=float, default=0.12)
    ap.add_argument("--scene", type=float, default=0.35)
    a = ap.parse_args()
    info = probe(a.video)
    res = {"source": os.path.abspath(a.video), **info, "speech": [], "silences": [], "scenes": [], "black": [], "frozen": []}
    if info["audio"]:
        wav = os.path.splitext(os.path.abspath(a.out))[0] + ".audio16k.wav"
        extract_wav(a.video, wav)
        x, sr = sf.read(wav)
        db = frame_db(x, sr)
        noise, speech_lv = float(np.percentile(db, 10)), float(np.percentile(db, 90))
        thr = float(np.clip(noise + 0.35 * (speech_lv - noise), -50.0, -30.0))
        speech = runs_from_db(db, thr, a.min_speech, a.min_silence)
        sil, prev = [], 0.0
        for s, e in speech:
            if s - prev >= a.min_silence: sil.append([round(prev, 3), s])
            prev = e
        if info["duration"] - prev >= a.min_silence: sil.append([round(prev, 3), round(info["duration"], 3)])
        eb = ffmpeg_filter_log(a.video, af="ebur128=peak=true")
        summ = eb[eb.rfind("Summary:"):]
        grab = lambda k: (lambda m: float(m.group(1)) if m else None)(re.search(k + r":\s*(-?[\d.]+)", summ))
        res["audio"].update({"lufs": grab("I"), "lra": grab("LRA"), "true_peak_db": grab("Peak"),
                             "sample_peak_db": round(float(20 * np.log10(np.abs(x).max() + 1e-9)), 1),
                             "noise_floor_db": round(noise, 1), "speech_level_db": round(speech_lv, 1), "threshold_db": round(thr, 1)})
        res.update({"speech": speech, "silences": sil, "audio_wav": wav})
    if info["video"]:
        sc = ffmpeg_filter_log(a.video, vf=f"select='gt(scene,{a.scene})',showinfo")
        res["scenes"] = [round(float(t), 3) for t in re.findall(r"pts_time:([\d.]+)", sc)][:300]
        res["black"] = spans(ffmpeg_filter_log(a.video, vf="blackdetect=d=0.5:pix_th=0.10"), "black_start", "black_end")
        res["frozen"] = spans(ffmpeg_filter_log(a.video, vf="freezedetect=n=-55dB:d=2"), "freeze_start", "freeze_end")
    json.dump(res, open(a.out, "w"), indent=1)
    sp = sum(e - s for s, e in res["speech"])
    print(f"{a.out}: {info['duration']:.1f}s, " + (f"{info['video']['width']}x{info['video']['height']} @ {info['video']['fps']} fps{' (VFR)' if info['video']['vfr'] else ''}" if info["video"] else "audio only") +
          (f", speech {sp:.1f}s in {len(res['speech'])} runs ({100 * sp / info['duration']:.0f}%), {len(res['silences'])} silences, "
           f"{res['audio']['lufs']} LUFS, noise floor {res['audio']['noise_floor_db']} dB" if info["audio"] else ", no audio") +
          f", {len(res['scenes'])} scene cuts, {len(res['black'])} black / {len(res['frozen'])} frozen spans")


if __name__ == "__main__":
    main()
