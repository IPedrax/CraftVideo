#!/usr/bin/env bash
# providers.sh: see and choose the tools behind each stage.
#   providers.sh list                       every provider of every kind: usable here or not (and why), with what it does
#   providers.sh which [kind]               the provider each kind will use now, and where that choice came from
#   providers.sh set <kind> <name> [--global]   remember a choice in ./craftvideo.json (or ~/.config/craftvideo/config.json)
#   providers.sh unset <kind> [--global]
#   providers.sh info <kind> <name>         the provider's --info JSON
# kinds: tts (script -> narration), render (scenes -> silent picture), assemble (picture + voice + music -> final file)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
CMD="${1:-list}"; shift || true
cfgfile() { if [ "${1:-}" = "--global" ]; then echo "${XDG_CONFIG_HOME:-$HOME/.config}/craftvideo/config.json"; else echo "./craftvideo.json"; fi; }
case "$CMD" in
  list)
    for kind in $(cv_kinds); do
      echo "$kind  (auto order: $(cv_order "$kind"); configured: $(cv_cfg "$kind" || true)${CRAFTVIDEO_X:-})"
      for n in $(cv_names "$kind"); do
        sc="$(cv_provider_script "$kind" "$n")"
        if bash "$sc" --check >/dev/null 2>&1; then st="usable "; why=""; else st="missing"; why="  <- $(cv_why_not "$kind" "$n")"; fi
        sum="$(bash "$sc" --info 2>/dev/null | python3 -c 'import json,sys; print(json.loads(sys.stdin.read() or "{}").get("summary",""))')"
        printf '  %-12s %s  %s%s\n' "$n" "$st" "$sum" "$why"
      done
      echo
    done ;;
  which)
    for kind in ${1:-$(cv_kinds)}; do
      src="$(cv_cfg_source "$kind")"
      if p="$(cv_resolve "$kind" 2>/dev/null)"; then printf '%-9s %s  (%s)\n' "$kind" "$p" "${src:-auto: first usable of $(cv_order "$kind")}"
      else printf '%-9s none usable  (%s)\n' "$kind" "$(cv_resolve "$kind" 2>&1 | tail -1)"; fi
    done ;;
  set)
    kind="${1:?kind}"; name="${2:?provider name}"; f="$(cfgfile "${3:-}")"
    [ -f "$(cv_provider_script "$kind" "$name")" ] || cv_die "no $kind provider named '$name' (available: $(cv_names "$kind" | tr '\n' ' '))"
    mkdir -p "$(dirname "$f")"
    python3 - "$f" "$kind" "$name" <<'PY'
import json, os, sys
f, kind, name = sys.argv[1:4]
d = json.load(open(f)) if os.path.exists(f) else {}
d[kind] = name
json.dump(d, open(f, "w"), indent=2); open(f, "a").write("\n")
print(f"{kind} -> {name} (saved in {f})")
PY
    cv_usable "$kind" "$name" || cv_warn "'$name' is not usable here right now: $(cv_why_not "$kind" "$name")" ;;
  unset)
    kind="${1:?kind}"; f="$(cfgfile "${2:-}")"
    [ -f "$f" ] && python3 - "$f" "$kind" <<'PY'
import json, sys
f, kind = sys.argv[1:3]; d = json.load(open(f)); d.pop(kind, None); json.dump(d, open(f, "w"), indent=2); open(f, "a").write("\n"); print(f"{kind} cleared in {f}")
PY
    ;;
  info) bash "$(cv_provider_script "${1:?kind}" "${2:?name}")" --info ;;
  *) echo "usage: providers.sh list | which [kind] | set <kind> <name> [--global] | unset <kind> [--global] | info <kind> <name>" >&2; exit 2 ;;
esac
