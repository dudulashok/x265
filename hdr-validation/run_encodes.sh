#!/bin/bash
# CRF sweep: anchor (VUI signalling only) vs HDR tool sets, 2 real HDR10 PQ clips.
set -e
cd "$(dirname "$0")"
X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe

encode() { # $1 clip $2 fps $3 cfg-name $4 crf; rest: extra args
    local clip=$1 fps=$2 cfg=$3 crf=$4; shift 4
    local out="${clip%.yuv}_${cfg}_crf${crf}"
    [ -f "$out.log" ] && grep -q "encoded" "$out.log" && { echo "skip $out"; return; }
    "$X265" --input "$clip" --input-res 3840x2160 --fps "$fps" --input-depth 10 \
        --preset medium --crf "$crf" "$@" -o "$out.hevc" 2>"$out.log"
    tail -1 "$out.log"
}

ANCHOR=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited)
HDR10OPT=("${ANCHOR[@]}" --hdr10-opt)
HDRLUMA=(--hdr-pq --hdr-luma-qp 1.0 --hdr-scene-qp 1.0)
HDRFULL=("${HDRLUMA[@]}" --hdr-banding-protect 1.0 --hdr-chroma-qp 1.0 --hdr-scaling-list)

for crf in 22 26 30 34; do
    for clipfps in "sol10.yuv 24" "whale10.yuv 60"; do
        set -- $clipfps
        encode "$1" "$2" anchor   "$crf" "${ANCHOR[@]}"
        encode "$1" "$2" hdr10opt "$crf" "${HDR10OPT[@]}"
        encode "$1" "$2" hdrluma  "$crf" "${HDRLUMA[@]}"
        encode "$1" "$2" hdrfull  "$crf" "${HDRFULL[@]}"
    done
done
echo ALL_ENCODES_DONE
