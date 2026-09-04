#!/usr/bin/env bash
# Verify a rendered PNG sequence covers exactly [0, 360) and therefore loops.
#
# WHY NOT A PIXEL-DIFFERENCE HEURISTIC: comparing the wrap against typical
# adjacent-frame deltas does NOT work for this content. The geometry is thin and
# largely transparent, so even a small rotation decorrelates almost every pixel
# and the difference metric saturates -- a 120 degree jump scores no higher than
# a 30 degree step. A partial rotation passes such a test. (Verified: it did.)
#
# So this verifies by construction instead. For a handful of frame indices it
# re-renders at the angle that index is SUPPOSED to hold and compares against the
# stored frame. If the sequence covers the wrong angular range, the stored frames
# will not match their expected angles and the check fails. It also renders angle
# 360 and confirms it reproduces frame 0 -- the seam itself -- calibrated against
# the raytracer's own noise floor, since OSPRay is not bit-deterministic.
#
# Usage: ./verify-loop.sh <framedir> <fragment> <width> <height>

set -euo pipefail

FRAMEDIR=${1:?usage: ./verify-loop.sh <framedir> <fragment> <width> <height>}
FRAGMENT=${2:-24}
WIDTH=${3:-270}
HEIGHT=${4:-480}

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

frames=$(ls "$FRAMEDIR"/frame-*.png 2>/dev/null | wc -l | tr -d ' ')
[ "$frames" -gt 2 ] || { echo "need more than 2 frames in $FRAMEDIR" >&2; exit 1; }

work=$(mktemp -d); trap 'rm -rf "$work"' EXIT

render() { # angle outfile
  "$F3D" --no-background=true --resolution="${WIDTH},${HEIGHT}" \
         --command-script="$COMMANDS" --camera-azimuth-angle="$1" \
         --output "$2" --input "$INPUT" >/dev/null 2>&1
}
raw() { ffmpeg -v error -y -i "$1" -pix_fmt rgba -f rawvideo "$2"; }

echo "verifying $frames frames in $FRAMEDIR (fragment $FRAGMENT @ ${WIDTH}x${HEIGHT})"
echo "expected angles: i * 360/$frames, i = 0..$((frames - 1))"
echo

# Noise floor: the same angle rendered twice. OSPRay is stochastic, so this is
# the irreducible difference any comparison below must be judged against.
render 0 "$work/nf_a.png"; render 0 "$work/nf_b.png"
raw "$work/nf_a.png" "$work/nf_a.raw"; raw "$work/nf_b.png" "$work/nf_b.raw"

# The seam: angle 360 must reproduce frame 0.
render 360 "$work/wrap.png"
raw "$work/wrap.png" "$work/wrap.raw"
raw "$FRAMEDIR/frame-0000.png" "$work/first.raw"

# Spot-check stored frames against their expected angles.
checks=""
for frac in 4 2; do
  idx=$((frames / frac))
  angle=$(awk -v i="$idx" -v n="$frames" 'BEGIN { printf "%.10f", i * 360.0 / n }')
  render "$angle" "$work/spot_${idx}.png"
  raw "$work/spot_${idx}.png" "$work/spot_${idx}.raw"
  raw "$(printf '%s/frame-%04d.png' "$FRAMEDIR" "$idx")" "$work/stored_${idx}.raw"
  checks="$checks $idx:$angle"
done

python3 - "$work" "$checks" <<'EOF'
import sys
work, checks = sys.argv[1], sys.argv[2].split()

def mad(p, q):
    a, b = open(p,'rb').read(), open(q,'rb').read()
    if len(a) != len(b): return None
    return sum(abs(x-y) for x, y in zip(a, b)) / len(a)

floor = mad(f"{work}/nf_a.raw", f"{work}/nf_b.raw")
tol = max(floor * 4, 0.05)
print(f"  raytracer noise floor (same angle twice) : {floor:.5f}")
print(f"  tolerance (4x floor)                     : {tol:.5f}\n")

ok = True
wrap = mad(f"{work}/wrap.raw", f"{work}/first.raw")
verdict = "OK" if wrap <= tol else "FAIL"
ok &= wrap <= tol
print(f"  seam    angle 360 vs frame 0000          : {wrap:.5f}  {verdict}")

for c in checks:
    idx, angle = c.split(":", 1)
    d = mad(f"{work}/spot_{idx}.raw", f"{work}/stored_{idx}.raw")
    verdict = "OK" if d is not None and d <= tol else "FAIL"
    ok &= d is not None and d <= tol
    print(f"  frame {int(idx):<5} expected angle {float(angle):8.4f}      : {d:.5f}  {verdict}")

print()
if ok:
    print("  SEAMLESS: frames sit at their expected angles and 360 reproduces frame 0.")
else:
    print("  BROKEN: the sequence does not cover exactly [0, 360). It will jump on repeat.")
    sys.exit(1)
EOF
