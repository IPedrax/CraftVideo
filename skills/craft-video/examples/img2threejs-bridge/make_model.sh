#!/usr/bin/env bash
# make_model.sh: spec.json -> model.ts (img2threejs generator) -> model.js (bundled for the scene).
#
# THIS IS A PLUMBING DEMO, not a reconstruction. It calls img2threejs' generator as a Python function, the way upstream's own tests do,
# which skips its quality gate on purpose: the real CLI refuses this toy spec (strict quality needs colour recipes, lighting,
# local overrides ...) and writes a BLOCKED artifact instead. A real model comes from img2threejs' full pipeline (reference image,
# intake, quality contract, spec, passes with screenshot review; its docs estimate 80k to 180k tokens for an object). Run that in
# your project with the checkout at $IMG2THREEJS_HOME, then hand the resulting createObjectModel.ts to bundle.sh the same way.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
I2T="${IMG2THREEJS_HOME:-$HOME/tools/img2threejs}"
[ -f "$I2T/forge/stage3_build/generate_threejs_factory.py" ] || { echo "img2threejs not found at $I2T (git clone https://github.com/img2threejs/img2threejs; or set IMG2THREEJS_HOME)" >&2; exit 1; }
python3 - "$I2T" "$HERE" <<'PY'
import json, sys
f, here = sys.argv[1] + "/forge", sys.argv[2]
sys.path[:0] = [f, f + "/_shared", f + "/stage2_spec", f + "/stage3_build"]
import generate_threejs_factory as g
open(f"{here}/model.ts", "w").write(g.generate(json.load(open(f"{here}/spec.json")), "blockout"))
PY
bash "$HERE/../../scripts/bundle.sh" "$HERE/model.ts" "$HERE/model.js"
