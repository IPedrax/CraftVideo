#!/usr/bin/env bash
# get_three.sh [PATH_TO_three_PACKAGE]: put Three.js where the html render provider (and bundle.sh) look for it.
# Destination: $THREE_DIR, else ~/.local/share/craftvideo/three (build/ and examples/jsm/, about 23 MB, MIT).
# Source, first that exists: the path you give, $THREE_SRC, ./node_modules/three. With none of those it needs
# CRAFTVIDEO_ALLOW_DOWNLOAD=1 and fetches the package with `npm pack three`, because a render tool should not reach the
# network on its own.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
DEST="${THREE_DIR:-$HOME/.local/share/craftvideo/three}"
SRC="${1:-${THREE_SRC:-}}"
[ -n "$SRC" ] || { [ -f node_modules/three/build/three.module.js ] && SRC=node_modules/three; } || true
if [ -z "$SRC" ]; then
  [ "${CRAFTVIDEO_ALLOW_DOWNLOAD:-}" = 1 ] || cv_die "no local three package found. Pass its path, or set CRAFTVIDEO_ALLOW_DOWNLOAD=1 to fetch it with npm (MIT, about 10 MB)."
  command -v npm >/dev/null || cv_die "npm is needed to fetch three"
  T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
  (cd "$T" && npm pack three --silent >/dev/null && tar xzf three-*.tgz); SRC="$T/package"
fi
[ -f "$SRC/build/three.module.js" ] || cv_die "$SRC is not a three package (no build/three.module.js)"
mkdir -p "$DEST/examples"; rm -rf "$DEST/build" "$DEST/examples/jsm"
cp -r "$SRC/build" "$DEST/build"; cp -r "$SRC/examples/jsm" "$DEST/examples/jsm"; cp "$SRC/package.json" "$DEST/"; cp "$SRC/LICENSE" "$DEST/" 2>/dev/null || true
echo "three $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$DEST/package.json") installed at $DEST"
