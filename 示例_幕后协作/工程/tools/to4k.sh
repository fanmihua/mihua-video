#!/usr/bin/env bash
# Normalise a screen recording for the film WITHOUT shrinking it: keep native resolution, 30 fps,
# H.264 yuv420p, high quality, no audio. Optional privacy blur boxes (x:y:w:h in SOURCE pixels).
#   sh tools/to4k.sh in.mp4 assets/video/name.mp4 ["2030:475:390:226" "26:1246:260:60" …]
# Time-limited blurs: edit the filter by hand with enable='between(t,a,b)' (see references/materials.md).
set -euo pipefail
IN="$1"; OUT="$2"; shift 2
mkdir -p "$(dirname "$OUT")"
if [ $# -eq 0 ]; then
  ffmpeg -v error -y -i "$IN" -vf "fps=30,format=yuv420p" -an -c:v libx264 -crf 14 -preset medium "$OUT"
else
  n=$#; fc="[0]split=$((n + 1))[base]"; for i in $(seq 1 $n); do fc="$fc[s$i]"; done; fc="$fc;"
  prev=base; i=1
  for box in "$@"; do
    IFS=: read -r x y w h <<< "$box"
    fc="$fc[s$i]crop=$w:$h:$x:$y,boxblur=30:3:20:3[b$i];[$prev][b$i]overlay=$x:$y[o$i];"; prev="o$i"; i=$((i + 1))
  done
  fc="$fc[$prev]fps=30,format=yuv420p[v]"
  ffmpeg -v error -y -i "$IN" -filter_complex "$fc" -map "[v]" -an -c:v libx264 -crf 14 -preset medium "$OUT"
fi
ffprobe -v error -show_entries stream=width,height:format=duration -of csv=p=0 "$OUT" | tr '\n' ' '; echo " → $OUT"
