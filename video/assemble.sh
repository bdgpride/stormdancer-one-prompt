#!/usr/bin/env bash
# assemble.sh — encodes the rendered segments and concatenates them into
# video/final.mp4 (1280x720, 30 fps, H.264 yuv420p, faststart, no audio).
set -euo pipefail
cd "$(dirname "$0")"

for seg in A B C D; do
  ffmpeg -v error -y -framerate 30 -i "frames$seg/%04d.png" \
    -c:v libx264 -pix_fmt yuv420p -crf 17 -r 30 "seg$seg.mp4"
done

printf "file 'segA.mp4'\nfile 'segB.mp4'\nfile 'segC.mp4'\nfile 'segD.mp4'\n" > concat.txt
ffmpeg -v error -y -f concat -safe 0 -i concat.txt \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart final.mp4

ffprobe -v error -show_entries format=duration,size \
  -show_entries stream=codec_name,width,height,r_frame_rate -of default=noprint_wrappers=1 final.mp4
