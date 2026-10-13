#!/usr/bin/env bash
# get_face.sh: install what the face-aware 9:16 crop needs (scripts/face_track.py): OpenCV for Python in its own venv, and the YuNet face detector.
# Destination: $FACE_DIR, else ~/.local/share/craftvideo/face (venv/, face_detection_yunet_2023mar.onnx, LICENSE-yunet; about 200 MB with the venv).
#   OpenCV: opencv-python-headless 4.13.0.92 (Apache-2.0) from PyPI, the wheel pinned by SHA-256 (uv, --require-hashes, --no-deps; numpy comes from the system python).
#   YuNet:  face_detection_yunet_2023mar.onnx (232 KB, MIT, Shiqi Yu) from opencv/opencv_zoo at a pinned commit, pinned by SHA-256, with its licence.
# 4.x on purpose: the 2023mar model has a fixed input shape, which OpenCV 4.x handles and the OpenCV 5 engine does not.
# It needs CRAFTVIDEO_ALLOW_DOWNLOAD=1 (a render tool should not reach the network on its own), plus uv, curl and a system python3 with numpy.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
DEST="${FACE_DIR:-$HOME/.local/share/craftvideo/face}"
ZOO=26cc381e4d2594bb9f47a26eb8fd96c94a13660d
MODEL=face_detection_yunet_2023mar.onnx
MODEL_SHA=8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4
WHEEL_HASHES=(0525a3d2c0b46c611e2130b5fdebc94cf404845d8fa64d2f3a3b679572a5bd22 0bd48544f77c68b2941392fcdf9bcd2b9cdf00e98cb8c29b2455d194763cf99e)
[ "${CRAFTVIDEO_ALLOW_DOWNLOAD:-}" = 1 ] || cv_die "set CRAFTVIDEO_ALLOW_DOWNLOAD=1 to download OpenCV (opencv-python-headless 4.13.0.92 from PyPI, about 55 MB) and the YuNet model (232 KB from github.com/opencv/opencv_zoo)."
for t in uv curl python3; do command -v "$t" >/dev/null || cv_die "$t is needed"; done
python3 -c "import numpy" 2>/dev/null || cv_die "the system python3 needs numpy (the venv reuses it)"
sha() { sha256sum "$1" | cut -d' ' -f1; }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

curl -fsSL "https://media.githubusercontent.com/media/opencv/opencv_zoo/$ZOO/models/face_detection_yunet/$MODEL" -o "$T/$MODEL"
[ "$(sha "$T/$MODEL")" = "$MODEL_SHA" ] || cv_die "the YuNet model does not match its pinned SHA-256 (got $(sha "$T/$MODEL" | cut -c1-12), wanted ${MODEL_SHA:0:12}). Refusing to install it."
curl -fsSL "https://raw.githubusercontent.com/opencv/opencv_zoo/$ZOO/models/face_detection_yunet/LICENSE" -o "$T/LICENSE-yunet"
head -3 "$T/LICENSE-yunet" | grep -q "MIT License" || cv_die "the YuNet licence is not the MIT licence it should be: look before installing"

mkdir -p "$DEST"
[ -x "$DEST/venv/bin/python" ] || uv venv -q --system-site-packages --python "$(command -v python3)" "$DEST/venv"
{ printf 'opencv-python-headless==4.13.0.92'; for h in "${WHEEL_HASHES[@]}"; do printf ' --hash=sha256:%s' "$h"; done; echo; } > "$T/req.txt"
uv pip install -q --python "$DEST/venv/bin/python" --no-deps --require-hashes -r "$T/req.txt"
"$DEST/venv/bin/python" -c "import cv2, numpy; assert hasattr(cv2, 'FaceDetectorYN'); print('opencv', cv2.__version__, 'numpy', numpy.__version__)"
cp "$T/$MODEL" "$DEST/$MODEL"; cp "$T/LICENSE-yunet" "$DEST/LICENSE-yunet"
echo "face tools installed at $DEST (OpenCV 4.13.0.92 and YuNet 2023mar, both pinned by SHA-256)"
