#!/usr/bin/env bash
# Encode a rendered PNG sequence into a looping video.
#
# Encoding is cheap and repeatable -- rendering is not. Everything here can be
# re-run against the same PNG sequence to produce a different codec, frame rate
# or deliverable without re-rendering a single frame.
#
# Formats:
#   hevc    H.265 carrying alpha, via VideoToolbox. Plays in QuickTime, Safari
#           and on Apple hardware. Generic media players will NOT show the
#           alpha channel correctly -- use prores for those.
#   prores  ProRes 4444 with alpha. The safe archival/museum master. Very large.
#   flat    H.265 with the alpha composited over a solid colour (arg 5).
#
# Usage: ./encode-loop.sh <framedir> [fps] [outbase] [format] [flatcolour]

set -euo pipefail

FRAMEDIR=${1:?usage: ./encode-loop.sh <framedir> [fps] [outbase] [format] [flatcolour]}
FPS=${2:-24}
OUTBASE=${3:-fragment-loop}
FORMAT=${4:-hevc}
FLATCOLOUR=${5:-white}

count=$(ls "$FRAMEDIR"/frame-*.png 2>/dev/null | wc -l | tr -d ' ')
[ "$count" -gt 0 ] || { echo "no frames in $FRAMEDIR" >&2; exit 1; }
echo "$count frames @ ${FPS}fps = $(awk -v c="$count" -v f="$FPS" 'BEGIN{printf "%.2f", c/f}')s loop"

in=(-framerate "$FPS" -start_number 0 -i "$FRAMEDIR/frame-%04d.png")

case "$FORMAT" in
  hevc)
    out="${OUTBASE}-hevc-alpha.mov"
    ffmpeg -y -v warning -stats "${in[@]}" \
      -c:v hevc_videotoolbox -alpha_quality 0.9 -pix_fmt bgra \
      -allow_sw 1 -tag:v hvc1 -q:v 65 \
      "$out"
    ;;
  prores)
    out="${OUTBASE}-prores4444.mov"
    ffmpeg -y -v warning -stats "${in[@]}" \
      -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le -vendor apl0 \
      "$out"
    ;;
  flat)
    out="${OUTBASE}-${FLATCOLOUR}.mp4"
    size=$(ffprobe -v error -select_streams v:0 \
      -show_entries stream=width,height -of csv=p=0:s=x "$FRAMEDIR/frame-0000.png")
    # The colour source must be pinned to FPS. Left at its 25fps default it
    # fights a 24fps sequence and ffmpeg silently drops frames.
    ffmpeg -y -v warning -stats "${in[@]}" \
      -filter_complex "color=c=${FLATCOLOUR}:s=${size}:r=${FPS}[bg];[bg][0:v]overlay=shortest=1,format=yuv420p" \
      -c:v libx265 -crf 18 -tag:v hvc1 -r "$FPS" \
      "$out"
    ;;
  *)
    echo "unknown format: $FORMAT (want hevc, prores or flat)" >&2; exit 1 ;;
esac

echo
ls -la "$out"
ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,nb_frames,pix_fmt \
  -show_entries format=duration -of default=nw=1 "$out"
