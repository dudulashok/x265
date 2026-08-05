#!/bin/bash
# CRF sweep: anchor (VUI signalling only) vs HDR tool sets, 2 real HDR10 PQ clips.
# 2026-08-04: re-anchored on the v4.3 rebase binary; adds the --hdr-wsse-rd
# strength sweep (0.5/1.0/1.5) and an --hdr-deblock ride-along config.
# hdr10opt/hdrfull are commented out for this round (their pre-rebase numbers
# are in results-2026-08-03-prerebase.json / RESULTS.md).
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
HDRPQ=(--hdr-pq)
WSSE05=(--hdr-pq --hdr-wsse-rd 0.5)
WSSE10=(--hdr-pq --hdr-wsse-rd 1.0)
WSSE15=(--hdr-pq --hdr-wsse-rd 1.5)
DBK10=(--hdr-pq --hdr-deblock 1.0)
# 2026-08-05 plan item 2: content-adaptive chroma offsets on top of the hdr-pq
# floor (needs the post-862809aed binary)
CHROMAADAPT=(--hdr-pq --hdr-chroma-adapt 1.0)

for crf in 22 26 30 34; do
    for clipfps in "sol10.yuv 24" "whale10.yuv 60"; do
        set -- $clipfps
        encode "$1" "$2" anchor   "$crf" "${ANCHOR[@]}"
        # 2026-08-05 plan item 1: pure --hdr-luma-qp strength sweep (no --hdr-pq,
        # so the model is measured without the chroma-offset floor)
        encode "$1" "$2" lumaq025 "$crf" "${ANCHOR[@]}" --hdr-luma-qp 0.25
        encode "$1" "$2" lumaq05  "$crf" "${ANCHOR[@]}" --hdr-luma-qp 0.5
        encode "$1" "$2" lumaq075 "$crf" "${ANCHOR[@]}" --hdr-luma-qp 0.75
        encode "$1" "$2" lumaq10  "$crf" "${ANCHOR[@]}" --hdr-luma-qp 1.0
        encode "$1" "$2" lumaq15  "$crf" "${ANCHOR[@]}" --hdr-luma-qp 1.5
        # encode "$1" "$2" hdr10opt "$crf" "${HDR10OPT[@]}"
        encode "$1" "$2" hdrluma  "$crf" "${HDRLUMA[@]}"
        encode "$1" "$2" hdrpq    "$crf" "${HDRPQ[@]}"
        # encode "$1" "$2" hdrfull  "$crf" "${HDRFULL[@]}"
        encode "$1" "$2" wsse05   "$crf" "${WSSE05[@]}"
        encode "$1" "$2" wsse10   "$crf" "${WSSE10[@]}"
        encode "$1" "$2" wsse15   "$crf" "${WSSE15[@]}"
        encode "$1" "$2" dbk10    "$crf" "${DBK10[@]}"
        encode "$1" "$2" chromaadapt "$crf" "${CHROMAADAPT[@]}"
    done
done
echo ALL_ENCODES_DONE
