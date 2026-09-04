#!/usr/bin/env bash
# Render a seamlessly looping turntable of one fragment as a PNG sequence.
#
# Each frame is an independent f3d invocation at an absolute camera azimuth of
# i * 360/FRAMES degrees, so the sequence is fully deterministic: no wall clock,
# no dropped frames, and frame 0 is the exact continuation of frame FRAMES-1.
# Angle 360 is deliberately never rendered -- it is frame 0.
#
# Resumable: completed frames are skipped, and each frame is written to a temp
# file and moved into place only once f3d succeeds, so an interrupted run never
# leaves a half-written PNG to be mistaken for a finished one.
#
# Usage: ./render-loop.sh [fragment] [frames] [width] [height] [outdir]

set -euo pipefail

FRAGMENT=${1:-24}
FRAMES=${2:-1440}
WIDTH=${3:-4320}
HEIGHT=${4:-7680}
OUTDIR=${5:-png/loop-${FRAGMENT}-${WIDTH}x${HEIGHT}}

# f3d location: override with F3D=/path/to/f3d, else PATH, else the macOS app bundle.
if [ -n "${F3D:-}" ]; then
  :
elif command -v f3d >/dev/null 2>&1; then
  F3D=$(command -v f3d)
else
  F3D=/Applications/f3d.app/Contents/MacOS/f3d
fi
COMMANDS=f3d-loop-commands.txt
INPUT=gltf/fragment-${FRAGMENT}.glb

[ -x "$F3D" ]      || { echo "f3d not found at $F3D (set F3D=/path/to/f3d)" >&2; exit 1; }
"$F3D" --version 2>&1 | grep -q "Module Raytracing: ON" || {
  echo "this f3d build lacks raytracing (need 'Module Raytracing: ON' in f3d --version)" >&2
  echo "  found: $($F3D --version 2>&1 | grep -i raytracing || echo 'no raytracing module line')" >&2
  exit 1; }
[ -f "$COMMANDS" ] || { echo "missing $COMMANDS" >&2; exit 1; }
[ -f "$INPUT" ]    || { echo "missing $INPUT" >&2; exit 1; }

mkdir -p "$OUTDIR"
rm -f "$OUTDIR"/.partial-*.png

echo "fragment $FRAGMENT | $FRAMES frames | ${WIDTH}x${HEIGHT} | -> $OUTDIR"

rendered=0
skipped=0
start=$(date +%s)

for ((i = 0; i < FRAMES; i++)); do
  out=$(printf "%s/frame-%04d.png" "$OUTDIR" "$i")

  if [ -f "$out" ]; then
    skipped=$((skipped + 1))
    continue
  fi

  # Full float precision: 1440 frames gives 0.25 degree steps.
  angle=$(awk -v i="$i" -v n="$FRAMES" 'BEGIN { printf "%.10f", i * 360.0 / n }')

  # Temp name keeps a .png extension (f3d picks its writer from the extension)
  # but does not match frame-*.png, so partials are never counted as finished.
  tmp=$(printf "%s/.partial-%04d.png" "$OUTDIR" "$i")
  "$F3D" --no-background=true \
         --resolution="${WIDTH},${HEIGHT}" \
         --command-script="$COMMANDS" \
         --camera-azimuth-angle="$angle" \
         --output "$tmp" \
         --input "$INPUT" >/dev/null 2>&1

  if [ ! -s "$tmp" ]; then
    echo >&2
    echo "frame $i failed (angle $angle) -- rerunning to show the error:" >&2
    "$F3D" --no-background=true --resolution="${WIDTH},${HEIGHT}" \
           --command-script="$COMMANDS" --camera-azimuth-angle="$angle" \
           --output "$tmp" --input "$INPUT" 2>&1 | tail -10 >&2
    rm -f "$tmp"
    exit 1
  fi
  mv "$tmp" "$out"

  rendered=$((rendered + 1))
  now=$(date +%s)
  elapsed=$((now - start))
  remaining=$((FRAMES - i - 1))
  eta=$(awk -v e="$elapsed" -v r="$rendered" -v rem="$remaining" \
        'BEGIN { printf "%.1f", (e / r) * rem / 3600 }')
  printf "\rframe %d/%d  angle %.4f  %ds elapsed  ETA %sh   " \
         "$((i + 1))" "$FRAMES" "$angle" "$elapsed" "$eta"
done

echo
echo "done: $rendered rendered, $skipped already present, $(ls "$OUTDIR"/frame-*.png | wc -l | tr -d ' ') frames total"
