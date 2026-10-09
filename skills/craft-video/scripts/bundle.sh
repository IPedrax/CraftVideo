#!/usr/bin/env bash
# bundle.sh SRC.(ts|tsx|js) OUT.js: turn a TypeScript or multi-file JavaScript module into ONE browser-ready ES module.
# The use case is a model or helper written as TypeScript, such as an img2threejs `createObjectModel.ts`, that a scene imports.
# `three` and `three/*` stay bare imports (the html renderer's import map supplies them); everything else is bundled in.
# Needs bun (https://bun.sh) or esbuild. Neither? CRAFTVIDEO_ALLOW_DOWNLOAD=1 lets it run `npx esbuild`.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
SRC="${1:?usage: bundle.sh SRC.ts OUT.js}"; OUT="${2:?output .js}"
[ -f "$SRC" ] || cv_die "not found: $SRC"
if command -v bun >/dev/null; then
  bun build "$SRC" --outfile "$OUT" --target browser --format esm --external three --external 'three/*' >/dev/null
elif command -v esbuild >/dev/null; then
  esbuild "$SRC" --bundle --format=esm --external:three --external:'three/*' --outfile="$OUT" --log-level=error
elif [ "${CRAFTVIDEO_ALLOW_DOWNLOAD:-}" = 1 ] && command -v npx >/dev/null; then
  npx --yes esbuild "$SRC" --bundle --format=esm --external:three --external:'three/*' --outfile="$OUT" --log-level=error
else
  cv_die "need bun or esbuild to bundle TypeScript (bun: https://bun.sh)"
fi
[ -s "$OUT" ] || cv_die "bundling produced nothing at $OUT"
echo "bundle: $OUT ($(wc -c < "$OUT") bytes)"
