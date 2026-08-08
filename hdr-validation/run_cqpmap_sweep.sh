#!/bin/bash
# 2026-08-08 follow-up: the chroma-QP-map arms, done properly.
#
# Two reasons this exists:
#
# 1. cqpmap10ca in run_vtm_sweep.sh is INVALID -- bit-identical to cqpmap10.
#    --hdr-chroma-adapt refused to run because a guard required nonzero PPS
#    cb/cr offsets (correct when it only scaled those, stale now that it scales
#    the total offset the map assigns). Guard fixed; those 8 keys are purged
#    from results.json and re-encoded here.
# 2. cqpmap10 measured +37.6% wPSNR-Y BD-rate on sol10 for -55.7/-64.6% chroma:
#    the full VVC table (Cb -9/Cr -12 near QP 40) is far too deep for luma
#    metrics. The interesting question is the shallow end, where the offsets are
#    comparable to --hdr-pq's fixed -2/-2 but still track the operating point:
#      cqpmap05  -- strength 0.5  (roughly Cb -2/Cr -3 at QP 32, -4/-6 at QP 40)
#      cqpmap025 -- strength 0.25 (roughly Cb -1/Cr -2 at QP 32, -2/-3 at QP 40)
#    Compare these against the `hdrpq` rows (fixed -2/-2, +7.14% wPSNR-Y on
#    sol10), not just against anchor: the question is whether QP-adaptive depth
#    beats a fixed offset at the same luma cost.
#
# Launch DETACHED (from PowerShell):
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/run_cqpmap_sweep.sh'
# Progress: cqpmap_sweep.out ; done: cqpmap_sweep_done.marker
cd "$(dirname "$0")"
rm -f cqpmap_sweep_done.marker
{
set -u
X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
ANCHOR=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited)

echo "binary: $($X265 --version 2>&1 | head -1)"
echo "start: $(date)"

# purge the invalid cqpmap10ca arm (bitstreams, logs and metric rows) so the
# resumable encode() below actually re-runs it and metrics.py re-measures it
python - <<'PY'
import json, os
keys = [f"{c}_cqpmap10ca_crf{q}" for c in ("sol10", "whale10") for q in (22, 26, 30, 34)]
res = json.load(open("results.json"))
for k in keys:
    res.pop(k, None)
    for ext in (".hevc", ".log"):
        if os.path.exists(k + ext):
            os.remove(k + ext)
json.dump(res, open("results.json", "w"), indent=1)
print(f"purged {len(keys)} invalid cqpmap10ca keys")
PY

encode() { # $1 clip $2 fps $3 cfg-name $4 crf; rest: extra args
    local clip=$1 fps=$2 cfg=$3 crf=$4; shift 4
    local out="${clip%.yuv}_${cfg}_crf${crf}"
    if [ -f "$out.log" ] && grep -q encoded "$out.log"; then echo "skip $out"; return; fi
    echo "=== $out $(date +%H:%M:%S)"
    "$X265" --input "$clip" --input-res 3840x2160 --fps "$fps" --input-depth 10 \
        --preset medium --crf "$crf" "${ANCHOR[@]}" "$@" -o "$out.hevc" 2>"$out.log"
    tail -1 "$out.log"
}

for crf in 22 26 30 34; do
    for clipfps in "sol10.yuv 24" "whale10.yuv 60"; do
        set -- $clipfps
        encode "$1" "$2" cqpmap025  "$crf" --hdr-chroma-qp-map 0.25
        encode "$1" "$2" cqpmap05   "$crf" --hdr-chroma-qp-map 0.5
        encode "$1" "$2" cqpmap10ca "$crf" --hdr-chroma-qp-map 1.0 --hdr-chroma-adapt 1.0
    done
done
echo "ALL_CQPMAP_ENCODES_DONE $(date +%H:%M:%S)"

# sanity: cqpmap10ca must now differ from cqpmap10 (the guard fix)
for c in 22 26 30 34; do
    if cmp -s "sol10_cqpmap10_crf$c.hevc" "sol10_cqpmap10ca_crf$c.hevc"; then
        echo "  WARNING sol10 crf$c: cqpmap10ca still identical to cqpmap10"
    else
        echo "  ok sol10 crf$c: cqpmap10ca differs from cqpmap10"
    fi
done

WPSNR_ONLY=1 python metrics.py
echo "=== BD-rate vs anchor ==="
python bdrate.py || echo "bdrate FAILED"
echo "ALL_CQPMAP_SWEEP_DONE $(date)"
} > cqpmap_sweep.out 2>&1 && touch cqpmap_sweep_done.marker
