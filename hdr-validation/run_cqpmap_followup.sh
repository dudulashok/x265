#!/bin/bash
# 2026-08-08 late: close out the chroma-QP-map result with the two arms that
# decide whether it is worth keeping.
#
#   fixed12 -- anchor flags + --cbqpoffs -1 --crqpoffs -2, i.e. a FIXED offset
#       at roughly cqpmap025's average depth. The control that separates "the
#       ramp shape is better" from "it is simply shallower than -2/-2".
#       cqpmap025 signals 0/0 near QP 24, -1/-2 at 32, -2/-3 at 40, so its mean
#       depth over a CRF 22-34 sweep sits near -1/-2. If cqpmap025 still beats
#       this, the QP-adaptive shape is doing real work.
#
#   prodmap -- the production stack with the ramp swapped in for --hdr-pq's
#       fixed -2/-2:
#         --hdr-pq --hdr-chroma-qp-map 0.25 --hdr-chroma-adapt 1.0
#         --hdr-luma-qp 0.5 --hdr-scene-qp 1.0
#       cqpmap025 beat the hdrpq floor by 1.65 pp wPSNR-Y on sol10 and 0.41 pp
#       on whale10; this asks whether that carries into the recommended stack,
#       whose current numbers are -0.16% (sol10) / -0.26% (whale10) wPSNR-Y.
#
# Compare against `hdrpq`, `cqpmap025` and `prodstack` in results.json.
#
# Launch DETACHED (from PowerShell):
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/run_cqpmap_followup.sh'
# Progress: cqpmap_followup.out ; done: cqpmap_followup_done.marker
cd "$(dirname "$0")"
rm -f cqpmap_followup_done.marker
{
set -u
X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
ANCHOR=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited)

echo "binary: $($X265 --version 2>&1 | head -1)"
echo "start: $(date)"

encode() { # $1 clip $2 fps $3 cfg-name $4 crf; rest: extra args (NO anchor flags added)
    local clip=$1 fps=$2 cfg=$3 crf=$4; shift 4
    local out="${clip%.yuv}_${cfg}_crf${crf}"
    if [ -f "$out.log" ] && grep -q encoded "$out.log"; then echo "skip $out"; return; fi
    echo "=== $out $(date +%H:%M:%S)"
    "$X265" --input "$clip" --input-res 3840x2160 --fps "$fps" --input-depth 10 \
        --preset medium --crf "$crf" "$@" -o "$out.hevc" 2>"$out.log"
    tail -1 "$out.log"
}

for crf in 22 26 30 34; do
    for clipfps in "sol10.yuv 24" "whale10.yuv 60"; do
        set -- $clipfps
        encode "$1" "$2" fixed12 "$crf" "${ANCHOR[@]}" --cbqpoffs -1 --crqpoffs -2
        encode "$1" "$2" prodmap "$crf" --hdr-pq --hdr-chroma-qp-map 0.25 \
                                        --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0
    done
done
echo "ALL_FOLLOWUP_ENCODES_DONE $(date +%H:%M:%S)"

WPSNR_ONLY=1 python metrics.py
echo "=== BD-rate vs anchor ==="
python bdrate.py || echo "bdrate FAILED"
echo "ALL_FOLLOWUP_DONE $(date)"
} > cqpmap_followup.out 2>&1 && touch cqpmap_followup_done.marker
