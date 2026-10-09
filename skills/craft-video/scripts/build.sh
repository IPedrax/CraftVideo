#!/usr/bin/env bash
# build.sh [--brand brand.jsx] scenes.jsx out.ecproj
# Concatenates brand + jsx/ec_lib.jsx + your scenes file, runs it in EffectCraft, saves out.ecproj.
# The concatenated script is kept next to the project as <name>.build.jsx, because errors report its line numbers.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRAND="$HERE/jsx/brand-ipedrax.jsx"
if [ "${1:-}" = "--brand" ]; then BRAND="$(realpath "$2")"; shift 2; fi
SCENES="$(realpath "${1:?usage: build.sh [--brand brand.jsx] scenes.jsx out.ecproj}")"
OUT="$(realpath -m "${2:?usage: build.sh [--brand brand.jsx] scenes.jsx out.ecproj}")"
TMP="${OUT%.*}.build.jsx"
{ echo "var OUT_PROJECT = '$OUT';"; cat "$BRAND" "$HERE/jsx/ec_lib.jsx" "$SCENES"; } > "$TMP"
effectcraft-cli script "$TMP"
