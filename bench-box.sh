#!/usr/bin/env bash
# Benchmark a render host and produce a frame for look-matching against the
# machine that rendered the stills. Run from the project root on the target box.
#
# Uses bash's builtin timer rather than /usr/bin/time, which is not installed by
# default on Arch and several other distros.
#
# Usage: ./bench-box.sh [fragment]

set -uo pipefail
FRAGMENT=${1:-24}

if [ -n "${F3D:-}" ]; then :
elif command -v f3d >/dev/null 2>&1; then F3D=$(command -v f3d)
else F3D=/Applications/f3d.app/Contents/MacOS/f3d; fi

COMMANDS=f3d-loop-commands.txt
INPUT=gltf/fragment-${FRAGMENT}.glb
OUT=bench-out
mkdir -p "$OUT"

for f in "$COMMANDS" "$INPUT"; do
  [ -f "$f" ] || { echo "ABORT: missing $f (run from the project root)" >&2; exit 1; }
done
[ -x "$F3D" ] || command -v "$F3D" >/dev/null 2>&1 || {
  echo "ABORT: f3d not found at '$F3D' (set F3D=/path/to/f3d)" >&2; exit 1; }

echo "host    : $(uname -srm)"
"$F3D" --version 2>&1 | grep -E "^F3D [0-9]|Module Raytracing" | sed 's/^/f3d     : /'
"$F3D" --version 2>&1 | grep -q "Module Raytracing: ON" || {
  echo "ABORT: this f3d has no raytracing module" >&2; exit 1; }

if command -v lscpu >/dev/null 2>&1; then
  echo "cpu     : $(lscpu | awk -F: '/^Model name/{gsub(/^ +/,"",$2); print $2}')"
  echo "governor: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo unknown)"
  echo "mhz now : $(awk -F: '/MHz/{gsub(/ /,"",$2); print $2; exit}' /proc/cpuinfo 2>/dev/null || echo unknown)"
fi
echo "cores   : $(getconf _NPROCESSORS_ONLN 2>/dev/null || echo unknown) online"
echo

echo "timing (raytraced, single frame at azimuth 42):"
TIMEFORMAT='%R %U'
for res in "2160,3840" "4320,7680"; do
  w=${res%,*}; h=${res#*,}
  printf "  %-12s rendering... " "${w}x${h}"

  # Bash builtin `time`; its report goes to the stderr of the compound command.
  timing=$( { time "$F3D" --no-background=true --resolution="$res" \
                --command-script="$COMMANDS" --camera-azimuth-angle=42 \
                --output "$OUT/bench-${w}.png" --input "$INPUT" \
                >/dev/null 2>/dev/null; } 2>&1 )

  if [ ! -s "$OUT/bench-${w}.png" ]; then
    printf "\r%-79s\r" " "
    printf "  %-12s FAILED -- f3d produced no output\n" "${w}x${h}"
    "$F3D" --no-background=true --resolution="$res" --command-script="$COMMANDS" \
           --camera-azimuth-angle=42 --output "$OUT/bench-${w}.png" --input "$INPUT" 2>&1 | tail -5
    continue
  fi

  real=$(echo "$timing" | awk '{print $1}')
  user=$(echo "$timing" | awk '{print $2}')
  par=$(awk -v u="$user" -v r="$real" 'BEGIN{ if (r+0>0) printf "%.1fx", u/r; else print "n/a" }')
  eta=$(awk -v r="$real" 'BEGIN{ printf "%.1f", (r+0) * 1440 / 3600 }')
  printf "\r%-79s\r" " "
  printf "  %-12s %8ss wall  %9ss cpu  %6s parallel   1440 frames = %sh\n" \
         "${w}x${h}" "$real" "$user" "$par" "$eta"
done

echo
echo "look-match frame: $OUT/bench-2160.png -- copy it back for comparison."
