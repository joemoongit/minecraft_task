#!/bin/bash
set +e
MC="$HOME/Library/Application Support/minecraft"
ASSETS="$MC/assets"
OUT_OGG="$HOME/minecraft-soundtrack-ogg"
OUT_WAV="$HOME/minecraft-soundtrack-wav"
if [ ! -d "$ASSETS" ]; then
  echo "No assets folder at $ASSETS. Launch Minecraft at least once and let it download resources, then re-run."
  exit 1
fi
if ! command -v jq >/dev/null; then echo "install jq: brew install jq"; exit 1; fi
if ! command -v ffmpeg >/dev/null; then echo "install ffmpeg: brew install ffmpeg"; exit 1; fi
mkdir -p "$OUT_OGG" "$OUT_WAV"
INDEX=$(ls -t "$ASSETS/indexes"/*.json | head -n1)
echo "Using index $INDEX"
jq -r '.objects | to_entries[] | select(.key | test("minecraft/sounds/")) | "\(.value.hash[0:2])/\(.value.hash) \(.key)"' "$INDEX" | sort -u | while IFS= read -r line; do
  h=${line%% *}
  name=${line#* }
  src="$ASSETS/objects/$h"
  rel="${name#minecraft/sounds/}"
  dst="$OUT_OGG/$rel"
  mkdir -p "$(dirname "$dst")"
  [ -f "$src" ] && cp -n "$src" "$dst"
done
echo "Copied $(find "$OUT_OGG" -type f | wc -l) ogg files to $OUT_OGG"
find "$OUT_OGG" -type f -name "*.ogg" -print0 | while IFS= read -r -d '' f; do
  rel="${f#$OUT_OGG/}"
  out="$OUT_WAV/${rel%.ogg}.wav"
  mkdir -p "$(dirname "$out")"
  if [ ! -f "$out" ]; then
    ffmpeg -y -nostdin -loglevel error -i "$f" -c:a pcm_s16le -ar 44100 "$out" || echo "warn: failed $f" >&2
  fi
done
echo "WAV files in $OUT_WAV : $(find "$OUT_WAV" -type f | wc -l)"
