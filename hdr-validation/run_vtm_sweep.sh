#!/bin/bash
# 2026-08-08: sweep the three VTM-derived tools (X265_BUILD 225, commit 96275df9c).
#
#   cascade05/10/15 -- --hdr-qp-cascade 0.5/1.0/1.5, the QP-adaptive
#       hierarchical-B QP cascade (JCTVC-X0038 model VTM uses in its
#       random-access GOP table). Nothing below QP ~22, up to +3 QP on
#       non-referenced B frames at high QP.
#   vtmlam05/10    -- --hdr-vtm-lambda 0.5/1.0, x265's QP-to-lambda mapping
#       blended toward VTM's 0.57*2^((QP-12)/3). At 1.0 this is a 15-20%
#       global lambda reduction; it is also the "pure lambda-scale, quantizer
#       untouched" arm of the --hdr-wsse-rd RD-hull post-mortem, but applied
#       globally and consistently (RDO + ME + RDOQ + SAO + lookahead) rather
#       than per-CTU.
#   cqpmap10       -- --hdr-chroma-qp-map 1.0, the HDR-PQ chroma QP mapping
#       table VVC signals, reproduced with slice-level offsets (Cb -5/Cr -7 at
#       QP 32, Cb -9/Cr -12 at QP 40 -- far deeper than --hdr-pq's -2/-2).
#   cqpmap10ca     -- the same plus --hdr-chroma-adapt 1.0, which scales the
#       map by the frame's chroma share of AC energy. The VVC table is
#       content-blind and a deep static offset is known to cost +7% wPSNR-Y on
#       chroma-heavy content, so this is the arm expected to work.
#
# All arms ride on the ANCHOR VUI flags, NOT --hdr-pq: these are coding-
# efficiency / chroma-mapping models, so the --hdr-pq chroma floor would only
# confound the reading. Compare against the `anchor` rows in results.json.
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
        encode "$1" "$2" cascade05  "$crf" --hdr-qp-cascade 0.5
        encode "$1" "$2" cascade10  "$crf" --hdr-qp-cascade 1.0
        encode "$1" "$2" cascade15  "$crf" --hdr-qp-cascade 1.5
        encode "$1" "$2" vtmlam05   "$crf" --hdr-vtm-lambda 0.5
        encode "$1" "$2" vtmlam10   "$crf" --hdr-vtm-lambda 1.0
        encode "$1" "$2" cqpmap10   "$crf" --hdr-chroma-qp-map 1.0
        encode "$1" "$2" cqpmap10ca "$crf" --hdr-chroma-qp-map 1.0 --hdr-chroma-adapt 1.0
    done
done
echo "ALL_VTM_ENCODES_DONE $(date +%H:%M:%S)"

WPSNR_ONLY=1 python metrics.py
echo "=== BD-rate vs anchor ==="
python bdrate.py || echo "bdrate FAILED"

# Provenance: the three new options are default-off and the default path was
# verified bit-identical (matching MD5), so the existing arms should be
# unchanged under X265_BUILD 225. Prove it rather than assume it (the
# 2026-08-07 lesson): re-encode whale10 CRF34 per existing arm and locate the
# differing bytes. Only the version-string SEI (first few hundred bytes) may
# differ. Runs last so it never delays the sweep.
echo "=== provenance check: existing arms under this binary ==="
for cfg in "anchor ${ANCHOR[*]}" \
           "hdr10opt ${ANCHOR[*]} --hdr10-opt" \
           "prodstack --hdr-pq --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0"; do
    set -- $cfg; name=$1; shift
    "$X265" --input whale10.yuv --input-res 3840x2160 --fps 60 --input-depth 10 \
        --preset medium --crf 34 "$@" -o "chk_$name.hevc" 2>"chk_$name.log"
    ref="whale10_${name}_crf34.hevc"
    if cmp -s "chk_$name.hevc" "$ref"; then
        echo "  $name IDENTICAL"
    else
        n=$(cmp -l "chk_$name.hevc" "$ref" | wc -l)
        last=$(cmp -l "chk_$name.hevc" "$ref" | tail -1 | awk '{print $1}')
        echo "  $name differs in $n bytes, last differing offset $last (SEI-only if < 500)"
    fi
    rm -f "chk_$name.hevc" "chk_$name.log"
done

echo "ALL_VTM_SWEEP_DONE $(date)"
} > vtm_sweep.out 2>&1 && touch vtm_sweep_done.marker
