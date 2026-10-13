#!/usr/bin/env bash
# get_mascot.sh [PATH_TO_ClaudeAnimationBase_CHECKOUT]: install what the mascot overlay page draws with.
# Destination: $MASCOT_DIR, else ~/.local/share/craftvideo/mascot (p5.min.js, p5.brush.js, clawd/core.js, clawd/clawd.js and the licences, about 1.2 MB).
# Every file is pinned by SHA-256 and a file that differs is refused, not installed:
#   Clawd and its painting engine: JohnHeibel/ClaudeAnimationBase at commit 0ac8bf2 (MIT), src/core.js and src/clawd.js. Clawd is the Claude Code mascot,
#   a character of Anthropic; the drawing code is John Heibel's. Neither is stored in this repository.
#   p5.js 2.3.3 (LGPL-2.1) and p5.brush 2.2.3 (MIT), from npm.
# One line of core.js is patched: the canvas size comes from the page (window.__CV_KIT) instead of being fixed at 1920 x 1080, so the kit can paint a small
# canvas just big enough for the character.
# Source, first that exists: the checkout you give (or $MASCOT_SRC; `npm install` done in it, so node_modules/p5 and node_modules/p5.brush exist). With none
# of those it needs CRAFTVIDEO_ALLOW_DOWNLOAD=1 and downloads the pinned files (curl for the kit, `npm pack` for the libraries), because a render tool
# should not reach the network on its own.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
DEST="${MASCOT_DIR:-$HOME/.local/share/craftvideo/mascot}"
SRC="${1:-${MASCOT_SRC:-}}"
KIT_COMMIT=0ac8bf2b31942376cb6b8c4074715595d512acd2
declare -A SUM=(
  [core.js]=7d8942e917c35089a6db94610367c12e849fe51cbd56ab8e73489046852b0ae2
  [clawd.js]=578fbd46d21cdcc92b14806f3cc8c7b1b9e9f7ea53ddda7b1c150afa9f3c512a
  [LICENSE]=7d25ae95b305b884c08ce898e53b58d2e180ff0119e5d203d8b4ae30420f3b33
  [p5.min.js]=3f8a0c739bd3c6350e239ff7187d38656ed2247e30a2b8084fd16a91e6e843ac
  [p5.license]=eb2f25f8f165d5f20682c1ce7e99ce69144ecfd80fbed8c17dfd327ecd8b6cb6
  [p5.brush.js]=41c25108c69a8eb1cca500d68f3603593e33b53e90a773fc024a6cff461fc31a
  [brush.license]=cabbece1a276329fa28ab40f1c99af3af2b7852a329551a9a485b2199616583a
  [patched-core.js]=4c8be3de785dd3eb7dd7e2f948fd8a9cfca126412e91e477c8f3f022e62c0f52
)
sha() { sha256sum "$1" | cut -d' ' -f1; }
check() { [ "$(sha "$2")" = "${SUM[$1]}" ] || cv_die "$1 does not match its pinned SHA-256 (got $(sha "$2" | cut -c1-12), wanted ${SUM[$1]:0:12}). Refusing to install it."; }

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
if [ -n "$SRC" ]; then
  K="$SRC/src"; P5="$SRC/node_modules/p5"; BR="$SRC/node_modules/p5.brush"; LIC="$SRC/LICENSE"
  [ -f "$K/core.js" ] && [ -f "$P5/lib/p5.min.js" ] && [ -f "$BR/dist/p5.brush.js" ] \
    || cv_die "$SRC is not a ClaudeAnimationBase checkout with npm install done (needs src/core.js, node_modules/p5 and node_modules/p5.brush)"
else
  [ "${CRAFTVIDEO_ALLOW_DOWNLOAD:-}" = 1 ] || cv_die "no local checkout given. Pass its path, or set CRAFTVIDEO_ALLOW_DOWNLOAD=1 to download the pinned files (raw.githubusercontent.com for the kit, npm for p5 and p5.brush; about 4 MB)."
  command -v curl >/dev/null && command -v npm >/dev/null || cv_die "curl and npm are needed to download the kit"
  B="https://raw.githubusercontent.com/JohnHeibel/ClaudeAnimationBase/$KIT_COMMIT"; mkdir -p "$T/kit"
  for f in src/core.js src/clawd.js LICENSE; do curl -fsSL "$B/$f" -o "$T/kit/$(basename "$f")"; done
  (cd "$T" && npm pack p5@2.3.3 p5.brush@2.2.3 --silent --cache "$T/npm" >/dev/null && for z in *.tgz; do mkdir "${z%.tgz}" && tar xzf "$z" -C "${z%.tgz}" --strip-components=1; done)
  K="$T/kit"; P5="$T/p5-2.3.3"; BR="$T/p5.brush-2.2.3"; LIC="$T/kit/LICENSE"
fi
check core.js "$K/core.js"; check clawd.js "$K/clawd.js"; check LICENSE "$LIC"
check p5.min.js "$P5/lib/p5.min.js"; check p5.license "$P5/license.txt"; check p5.brush.js "$BR/dist/p5.brush.js"; check brush.license "$BR/LICENSE.md"

mkdir -p "$DEST/clawd"
sed 's|^const W = 1920, H = 1080;|const W = window.__CV_KIT.width, H = window.__CV_KIT.height;|' "$K/core.js" > "$DEST/clawd/core.js"
check patched-core.js "$DEST/clawd/core.js"
cp "$K/clawd.js" "$DEST/clawd/clawd.js"; cp "$LIC" "$DEST/clawd/LICENSE"
cp "$P5/lib/p5.min.js" "$DEST/p5.min.js"; cp "$P5/license.txt" "$DEST/p5.LICENSE.txt"
cp "$BR/dist/p5.brush.js" "$DEST/p5.brush.js"; cp "$BR/LICENSE.md" "$DEST/p5.brush.LICENSE.md"
echo "mascot kit installed at $DEST (Clawd from ClaudeAnimationBase ${KIT_COMMIT:0:7}, p5 2.3.3, p5.brush 2.2.3, every file checked against its pinned SHA-256)"
