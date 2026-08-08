#!/bin/bash
# 2026-08-08: sweep the two VTM-derived coding-efficiency tools (X265_BUILD 224).
#
#   cascade05/10/15 -- --hdr-qp-cascade 0.5/1.0/1.5, the QP-adaptive
#       hierarchical-B QP cascade (JCTVC-X0038 model VTM uses in its
#       random-access GOP table). Nothing below QP ~22, up to +3 QP on
#       non-referenced B frames at high QP.
#   cqpmap10       -- --hdr-chroma-qp-map 1.0, the HDR-PQ chroma QP mapping
#       table VVC signals, reproduced with slice-level offsets (Cb -5/Cr -7 at
#       QP 32, Cb -9/Cr -12 at QP 40 -- far deeper than --hdr-pq's -2/-2).
#   cqpmap10ca     -- the same plus --hdr-chroma-adapt 1.0, which scales the
#       map by the frame's chroma share of AC energy. The VVC table is
#       content-blind and we already know a deep static offset costs +7%
#       wPSNR-Y on chroma-heavy content, so this is the arm that should work.
#   vtmlam05/10    -- --hdr-vtm-lambda 0.5/1.0, x265's QP-to-lambda mapping
#       blended toward VTM's 0.57*2^((QP-12)/3). At 1.0 this is a ~15-20%
#       global lambda reduction; it is also the "pure lambda-scale, quantizer
#       untouched" arm of the --hdr-wsse-rd RD-hull post-mortem, but applied
#       globally and consistently (RDO + ME + RDOQ + SAO + lookahead) rather
#       than per-CTU.
#
# All arms ride on the ANCHOR VUI flags, NOT --hdr-pq: both tools are
# coding-efficiency models rather than PQ allocation, so the chroma-offset
# floor would only confound the luma reading. Compare against the `anchor`
# rows already in results.json.
#
# wPSNR only -- Q_JOD is reserved for whichever arm wins on wPSNR BD-rate
# (Q_JOD BD-rate is not usable, see RESULTS.md 2026-08-07 methodology note).
#
# Launch DETACHED (from PowerShell):
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/run_vtm_sweep.sh'
# Progress: vtm_sweep.out ; done: vtm_sweep_done.marker
cd "$(dirname "$0")"
rm -f vtm_sweep_done.marker
{
set -u
X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
ANCHOR=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited)

echo "binary: $($X265 --version 2>&1 | head -1)"
echo "start: $(date)"

encode() { # $1 clip $2 fps $3 cfg-name $4 crf; rest: extra args
    local clip=$1 fps=$2 cfg=$3 crf=$4; shift 4
    local out="${clip%.yuv}_${cfg}_crf${crf}"
    if [ -f "$out.log" ] && grep -q encoded "$out.log"; then echo "skip $out"; return; fi
    echo "=== $out $(date +%H:%M:%S)"
    "$X265" --input "$clip" --input-res 3840x2160 --fps "$fps" --input-depth 10 \
        --preset medium --crf "$crf" "${ANCHOR[@]}" "$@" -o "$out.hevc" 2>"$out.log"
    tail -1 "$out.log"
}

# prune partial outputs from any earlier interrupted run
for f in *_cascade*_*.log *_vtmlam*_*.log *_cqpmap*_*.log; do
    [ -e "$f" ] || continue
    grep -q encoded "$f" || { echo "prune ${f%.log}"; rm -f "$f" "${f%.log}.hevc"; }
done

for crf in 22 26 30 34; do
    for clipfps in "sol10.yuv 24" "whale10.yuv 60"; do
        set -- $clipfps
        encode "$1" "$2" cascade05 "$crf" --hdr-qp-cascade 0.5
        encode "$1" "$2" cascade10 "$crf" --hdr-qp-cascade 1.0
        encode "$1" "$2" cascade15 "$crf" --hdr-qp-cascade 1.5
        encode "$1" "$2" vtmlam05  "$crf" --hdr-vtm-lambda 0.5
        encode "$1" "$2" vtmlam10  "$crf" --hdr-vtm-lambda 1.0
        encode "$1" "$2" cqpmap10  "$crf" --hdr-chroma-qp-map 1.0
        encode "$1" "$2" cqpmap10ca "$crf" --hdr-chroma-qp-map 1.0 --hdr-chroma-adapt 1.0
    done
done
echo "ALL_VTM_ENCODES_DONE $(date +%H:%M:%S)"

WPSNR_ONLY=1 python metrics.py
echo "=== BD-rate vs anchor ==="
python bdrate.py || echo "bdrate FAILED"
echo "ALL_VTM_SWEEP_DONE $(date)"
} > vtm_sweep.out 2>&1 && touch vtm_sweep_done.marker
