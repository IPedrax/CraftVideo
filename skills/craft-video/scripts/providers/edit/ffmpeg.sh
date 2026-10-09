#!/usr/bin/env bash
# edit provider: ffmpeg. The full-featured applier: cuts, jump-cut zooms, audio chain (highpass, denoise, EQ, compression),
# music bed with ducking, two-pass loudness, colour, stabilisation, reframing (crop or blurred fill), burned-in captions, titles.
#   ffmpeg.sh EDL.json OUT.mp4 [--ass captions.ass] [--chapters meta.txt]
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; source "$HERE/lib.sh"
case "${1:-}" in
  --info)  echo '{"name":"ffmpeg","kind":"edit","summary":"ffmpeg: cuts, zoom, audio chain, music ducking, loudness, colour, stabilise, reframe, burned-in captions, titles","features":["cuts","zoom","audio","music","loudness","color","stabilize","reframe","captions","overlays","chapters"],"needs":"ffmpeg with libass, vidstab"}'; exit 0;;
  --check) command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || { echo "ffmpeg/ffprobe missing"; exit 1; }
           ffmpeg -hide_banner -filters 2>/dev/null | grep -q ' loudnorm ' || { echo "this ffmpeg has no loudnorm filter"; exit 1; }; exit 0;;
esac
exec "$CV_PY" "$CV_HERE/providers/edit/edit_ffmpeg.py" "$@"
