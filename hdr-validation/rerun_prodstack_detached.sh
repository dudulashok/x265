#!/bin/bash
# 2026-08-07: verify_binary_identity.sh proved the stored prodstack encodes
# (made 2026-08-05 21:25 with the 4.2+115-862809aed build) are NOT reproducible
# with the current binary -- 10 bytes of coded data differ, because the current
# build contains the later --hdr-sao-band change, which perturbs the SAO RD
# decision on configs that force SAO on (--hdr-pq does). anchor is unaffected
# (coded data byte-identical; only the version-string SEI differs) and hdr10opt
# was already encoded with the current binary.
#
# Re-encodes the prodstack arm only, so all three arms of the three-way report
# come from one post-rebase binary. Old bitstreams are kept as *.prev.
cd "$(dirname "$0")"
rm -f prodstack_rerun_done.marker
{
X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
PRODSTACK=(--hdr-pq --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0)
echo "binary: $($X265 --version 2>&1 | head -1)"
for crf in 22 26 30 34; do
    for clipfps in "sol10.yuv 24" "whale10.yuv 60"; do
        set -- $clipfps
        clip=$1; fps=$2
        out="${clip%.yuv}_prodstack_crf${crf}"
        if [ -f "$out.rerun.log" ] && grep -q encoded "$out.rerun.log"; then
            echo "skip $out"; continue
        fi
        [ -f "$out.hevc" ] && [ ! -f "$out.hevc.prev" ] && cp "$out.hevc" "$out.hevc.prev"
        echo "=== $out $(date +%H:%M:%S)"
        "$X265" --input "$clip" --input-res 3840x2160 --fps "$fps" --input-depth 10 \
            --preset medium --crf "$crf" "${PRODSTACK[@]}" -o "$out.hevc" 2>"$out.rerun.log"
        cp "$out.rerun.log" "$out.log"
        tail -1 "$out.rerun.log"
        echo -n "   vs previous bitstream: "
        if cmp -s "$out.hevc" "$out.hevc.prev"; then echo "identical"; else
            echo "differs ($(stat -c%s "$out.hevc") vs $(stat -c%s "$out.hevc.prev") bytes)"; fi
    done
done
echo ALL_PRODSTACK_RERUN_DONE
} > prodstack_rerun.out 2>&1 && touch prodstack_rerun_done.marker
