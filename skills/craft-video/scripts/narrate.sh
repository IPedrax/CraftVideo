#!/usr/bin/env bash
# narrate.sh: the TTS dispatcher. Turns script.txt into narration_raw.wav with whichever TTS provider is chosen.
#   narrate.sh script.txt narration_raw.wav [--provider NAME] [--instruct "(voice description)"] [--seed N] [--language English]
#              [--speed 1.0] [--ref ref.wav --ref-text "what the reference says"] [--engine voxcpm2]
# script.txt: one sentence per line, optional "label | sentence"; lines starting with # are ignored.
# Provider order: --provider, env CRAFTVIDEO_TTS, ./craftvideo.json, ~/.config/craftvideo/config.json, then the first usable of
# voicestudio, openai. List and test them with providers.sh and conformance.sh. Whatever the provider writes is normalised to
# 48 kHz mono PCM16 here, so a provider may emit mp3/flac/ogg/wav at any rate (it is handed a .wav path, and ffmpeg sniffs
# the real format from the content, so an engine that always writes mp3 still works).
# --ref clones a voice: only with the speaker's permission. Options a provider cannot honour are refused or warned, never ignored.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
SCRIPT="${1:?usage: narrate.sh script.txt narration_raw.wav [--provider NAME] [options]}"; OUT="${2:?output wav}"; shift 2
PROV=""; PASS=(); REF=""; REFTEXT=""; INSTRUCT_GIVEN=""
while [ $# -gt 0 ]; do
  [ $# -ge 2 ] || cv_die "option $1 needs a value"
  case "$1" in
    --provider) PROV="$2";;
    --ref) REF="$2"; PASS+=("$1" "$2");;
    --ref-text) REFTEXT="$2"; PASS+=("$1" "$2");;
    --instruct) INSTRUCT_GIVEN=1; PASS+=("$1" "$2");;
    *) PASS+=("$1" "$2");;
  esac
  shift 2
done
[ -z "$REF" ] || [ -n "$REFTEXT" ] || cv_die "--ref needs --ref-text (the exact words spoken in the reference clip)"
[ -s "$SCRIPT" ] || cv_die "script file not found or empty: $SCRIPT"

NAME="$(cv_resolve tts "$PROV")"
SRC="$(cv_cfg_source tts)"; [ -z "$PROV" ] || SRC="--provider"
if [ -n "$REF" ]; then
  case "$(cv_info tts "$NAME" clone)" in False|false) cv_die "provider '$NAME' cannot clone a voice (use voicestudio, or a command provider whose engine can)";; esac
fi
if [ -n "$INSTRUCT_GIVEN" ]; then
  case "$(cv_info tts "$NAME" design)" in False|false) cv_warn "provider '$NAME' ignores --instruct (it cannot design a voice)";; esac
fi

PLAIN="$(mktemp)"; RAW="$(mktemp -u).wav"; trap 'rm -f "$PLAIN" "$RAW"' EXIT
grep -v '^\s*#' "$SCRIPT" | sed -E 's/^[^|]{1,40}\|\s*//' | sed -E '/^\s*$/d' > "$PLAIN"
WORDS="$(cv_words "$PLAIN")"; EXP="$(awk -v w="$WORDS" 'BEGIN{printf "%.1f", w / 2.6}')"
echo "narrating $WORDS words (about ${EXP}s at 2.6 words/s) with provider '$NAME'${SRC:+ ($SRC)}" >&2

bash "$(cv_provider_script tts "$NAME")" "$PLAIN" "$RAW" "${PASS[@]}"
[ -s "$RAW" ] || cv_die "provider '$NAME' produced no audio"
cv_wav48 "$RAW" "$OUT" || cv_die "provider '$NAME' wrote something ffmpeg cannot read as audio"
DUR="$(cv_dur "$OUT")"
awk -v d="$DUR" 'BEGIN{exit !(d > 0.3)}' || cv_die "narration is only ${DUR}s long: the provider produced (almost) nothing"
if awk -v d="$DUR" -v e="$EXP" 'BEGIN{exit !(d < 0.4*e || d > 2.5*e)}'; then
  cv_warn "narration is ${DUR}s but about ${EXP}s was expected for $WORDS words: check the voice, speed and text"
fi
echo "ok: $OUT, ${DUR}s, 48 kHz mono (provider $NAME)"
