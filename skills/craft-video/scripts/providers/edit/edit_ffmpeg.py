#!/usr/bin/env python3
"""edit_ffmpeg.py EDL.json OUT [--ass captions.ass] [--chapters meta.txt]: apply an edit decision list with ffmpeg.

Cuts the source into the EDL's segments (video and audio together, sample-accurate, with a short audio fade at every cut so nothing
clicks), joins them, then polishes:
  audio  highpass, denoise (afftdn), presence EQ, gentle compression, optional music bed that ducks under the voice (sidechain),
         two-pass loudness normalisation to the EDL's LUFS target (true peak -1.5 dB)
  video  per-segment punch-in zoom (hides jump cuts), colour (auto-level, saturation, or a 3D LUT), optional stabilisation (vidstab),
         reframing to another aspect (crop or blurred fill), rendered overlay clips (alpha), burned-in ASS captions, simple title overlays,
         constant frame rate
Audio-only sources are supported (the output is then audio). One filter graph, one video encode (x264 crf 18, yuv420p, bt709)."""
import json, os, re, subprocess, sys, tempfile


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def probe(path):
    d = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path]).stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    return {"dur": float(d["format"]["duration"]), "v": v, "a": a}


def fc(path, graph):
    """-filter_complex arguments. Inline when small (any ffmpeg); a file for long graphs (one argument is capped near 128 KB):
    ffmpeg 7+ reads it with -/filter_complex, older ones with -filter_complex_script (removed in 9)."""
    text = ";\n".join(graph)
    if len(text) < 100000: return ["-filter_complex", text]
    open(path, "w").write(text)
    major = re.search(r"version \D*(\d+)", run(["ffmpeg", "-version"]).stdout)
    return ["-/filter_complex", path] if major and int(major.group(1)) >= 7 else ["-filter_complex_script", path]


def main():
    args = sys.argv[1:]
    edl_path, out = args[0], args[1]
    opt = {args[i]: args[i + 1] for i in range(2, len(args) - 1, 2)}
    edl = json.load(open(edl_path))
    src = edl["source"]; pr = probe(src)
    has_v, has_a = pr["v"] is not None, pr["a"] is not None
    segs = edl["segments"]; N = len(segs)
    o = edl.get("output", {}); au = edl.get("audio", {}); vd = edl.get("video", {}); mu = edl.get("music")
    fps = o.get("fps") or 30
    W = o.get("width") or (pr["v"]["width"] if has_v else 0); H = o.get("height") or (pr["v"]["height"] if has_v else 0)
    W, H = W - W % 2, H - H % 2
    clips = [x for x in edl.get("overlays", []) if x.get("type") == "clip"]
    for c in clips:
        if not os.path.exists(c["file"]): sys.exit(f"edit_ffmpeg: overlay clip not found: {c['file']}")
    clip_base = 1 + (1 if mu else 0)        # input index of the first overlay clip (source, then music)
    fade = au.get("fade_ms", 8) / 1000.0
    lufs = au.get("lufs", o.get("lufs", -16.0))
    reframe = o.get("reframe", "none")
    tmp = tempfile.mkdtemp(prefix="cvedit-")
    total = sum(s["out"] - s["in"] for s in segs)

    # ---------------- video graph ----------------
    def video_graph():
        g = []; srcv = "0:v"
        if vd.get("stabilize"):
            trf = os.path.join(tmp, "stab.trf")
            r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-vf", f"vidstabdetect=shakiness=5:accuracy=9:result={trf}", "-an", "-f", "null", "-"])
            if r.returncode: sys.exit("edit_ffmpeg: vidstabdetect failed: " + r.stderr[-300:])
            g.append(f"[0:v]vidstabtransform=input={trf}:smoothing=12:zoom=0:optzoom=1[stab]"); srcv = "stab"
        g.append(f"[{srcv}]split={N}" + "".join(f"[sv{i}]" for i in range(N)) if N > 1 else f"[{srcv}]null[sv0]")
        for i, s in enumerate(segs):
            z = float(s.get("zoom", 1.0))
            zoom = f",crop=iw/{z}:ih/{z}:(iw-iw/{z})/2:(ih-ih/{z})/2" if z > 1.0001 else ""
            head = f"[sv{i}]trim=start={s['in']:.4f}:end={s['out']:.4f},setpts=PTS-STARTPTS,fps={fps}{zoom}"
            if reframe == "crop":
                g.append(f"{head},crop='min(iw,ih*{W}/{H})':'min(ih,iw*{H}/{W})',scale={W}:{H},setsar=1[v{i}]")
            elif reframe == "blur":
                g.append(f"{head},split[bg{i}][fg{i}]")
                g.append(f"[bg{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=40[bb{i}]")
                g.append(f"[fg{i}]scale={W}:{H}:force_original_aspect_ratio=decrease[ff{i}]")
                g.append(f"[bb{i}][ff{i}]overlay=(W-w)/2:(H-h)/2,setsar=1[v{i}]")
            else:
                g.append(f"{head},scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[v{i}]")
        return g

    def video_color():                      # grading applies to the footage only, never to graphics laid over it
        f = []
        col = vd.get("color", "none")
        if col == "auto": f.append("normalize=smoothing=24:independence=0:strength=0.6,eq=saturation=1.06")
        elif isinstance(col, dict):
            f.append("eq=" + ":".join(f"{k}={v}" for k, v in col.items() if k in ("brightness", "contrast", "saturation", "gamma")))
        if vd.get("lut"): f.append(f"lut3d=file='{vd['lut']}'")
        return ",".join(f) or "null"

    def overlay_graph(label):               # rendered clips (3D, motion graphics, lower thirds; ProRes 4444 with alpha works) over the footage
        g = []
        for k, c in enumerate(clips):
            st = float(c["start"]); w = f",scale={int(c['width'])}:-2" if c.get("width") else ""
            g.append(f"[{clip_base + k}:v]format=yuva444p{w},setpts=PTS-STARTPTS+{st}/TB[ov{k}]")
            en = f":enable='between(t,{st},{float(c['end'])})'" if c.get("end") else ""
            g.append(f"[{label}][ov{k}]overlay=x={c.get('x', 0)}:y={c.get('y', 0)}:eof_action=pass{en}[vo{k}]")
            label = f"vo{k}"
        return g, label

    def video_post():                       # captions and titles go on top of everything, then the pixel format
        f = []
        if opt.get("--ass"): f.append("ass=captions.ass")
        for k, ov in enumerate(x for x in edl.get("overlays", []) if x.get("type") == "title"):
            open(os.path.join(tmp, f"title{k}.txt"), "w", encoding="utf-8").write(ov["text"])   # a text file needs no escaping
            y = "h*0.66" if ov.get("pos", "lower") == "lower" else "(h-text_h)/2"
            f.append(f"drawtext=font='{ov.get('font', 'Noto Sans')}':textfile=title{k}.txt:expansion=none:fontsize=h*0.06:fontcolor=white:box=1:boxcolor=0x000000AA:boxborderw=14:"
                     f"x=(w-text_w)/2:y={y}:enable='between(t,{ov['start']},{ov['end']})'")
        f.append("format=yuv420p")
        return ",".join(f)

    # ---------------- audio graph ----------------
    def audio_graph(measured=None):
        g, last = [], None
        if has_a:
            g.append(f"[0:a]asplit={N}" + "".join(f"[sa{i}]" for i in range(N)) if N > 1 else "[0:a]anull[sa0]")
            for i, s in enumerate(segs):
                L = s["out"] - s["in"]; fd = min(fade, L / 3)
                g.append(f"[sa{i}]atrim=start={s['in']:.4f}:end={s['out']:.4f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,"
                         f"afade=t=in:st=0:d={fd:.4f},afade=t=out:st={L - fd:.4f}:d={fd:.4f}[a{i}]")
            g.append("".join(f"[a{i}]" for i in range(N)) + f"concat=n={N}:v=0:a=1[ac]")
            chain = []
            if au.get("highpass"): chain.append(f"highpass=f={au['highpass']}")
            if au.get("denoise"): chain.append(f"afftdn=nr={au['denoise']}:nf=-50")
            if au.get("presence"): chain.append("equalizer=f=3200:t=q:w=1.2:g=2")
            if au.get("compress"): chain.append("acompressor=threshold=-20dB:ratio=3:attack=15:release=250")
            g.append("[ac]" + (",".join(chain) if chain else "anull") + "[vox]")
            last = "vox"
        if mu:
            m = f"[1:a]volume={mu.get('db', -22)}dB,aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{total:.4f}[mus]"
            g.append(m)
            if last and mu.get("duck", True):
                g.append(f"[{last}]asplit=2[voxa][sc]")
                g.append("[mus][sc]sidechaincompress=threshold=0.04:ratio=10:attack=20:release=400[md]")
                g.append("[voxa][md]amix=inputs=2:normalize=0:duration=first[mix]")
            elif last:
                g.append(f"[{last}][mus]amix=inputs=2:normalize=0:duration=first[mix]")
            else:
                g.append("[mus]anull[mix]")
            last = "mix"
        if last is None:
            return g, None
        tail = f"loudnorm=I={lufs}:TP=-1.5:LRA=11"
        if measured is None: tail += ":print_format=json"
        else: tail += (f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:measured_LRA={measured['input_lra']}"
                       f":measured_thresh={measured['input_thresh']}:offset={measured['target_offset']}:linear=true")
        g.append(f"[{last}]{tail},aresample=48000[aout]")
        return g, "aout"

    inputs = ["-i", src] + (["-i", mu["file"]] if mu else []) + [x for c in clips for x in ("-i", c["file"])]
    cwd = tmp
    if opt.get("--ass"): os.symlink(os.path.abspath(opt["--ass"]), os.path.join(tmp, "captions.ass"))

    measured = None
    ag, alabel = audio_graph(None)
    if alabel:                                         # pass 1: measure the loudness of the processed mix
        r = run(["ffmpeg", "-hide_banner", "-nostats", *inputs, *fc(os.path.join(tmp, "g1.txt"), ag), "-map", f"[{alabel}]", "-f", "null", "-"], cwd=cwd)
        m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
        if r.returncode or not m: sys.exit("edit_ffmpeg: audio measuring pass failed: " + r.stderr[-400:])
        measured = json.loads(m[-1])
        ag, alabel = audio_graph(measured)

    graph = []
    if has_v:
        graph += video_graph()
        graph.append("".join(f"[v{i}]" for i in range(N)) + f"concat=n={N}:v=1:a=0[vc]")
        graph.append(f"[vc]{video_color()}[vg]")
        og, lab = overlay_graph("vg"); graph += og
        graph.append(f"[{lab}]{video_post()}[vout]")
    graph += ag
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs]
    if opt.get("--chapters"): cmd += ["-i", os.path.abspath(opt["--chapters"])]
    cmd += fc(os.path.join(tmp, "g2.txt"), graph)
    if has_v: cmd += ["-map", "[vout]"]
    if alabel: cmd += ["-map", f"[{alabel}]"]
    if opt.get("--chapters"): cmd += ["-map_metadata", str(len(inputs) // 2)]
    if has_v: cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
    if alabel: cmd += ["-c:a", "aac", "-b:a", "256k", "-ar", "48000"]
    cmd += ["-movflags", "+faststart", "-t", f"{total:.4f}", os.path.abspath(out)]
    r = run(cmd, cwd=cwd)
    if r.returncode: sys.exit("edit_ffmpeg: ffmpeg failed:\n" + r.stderr[-1200:])
    print(f"edit_ffmpeg: {N} segments, {total:.2f}s"
          + (f", loudness {measured['input_i']} -> {lufs} LUFS" if measured else ", no audio")
          + (f", {len(clips)} overlay clip(s)" if clips else "") + (", captions burned in" if opt.get("--ass") else "") + (f", reframe {reframe}" if reframe != "none" else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
