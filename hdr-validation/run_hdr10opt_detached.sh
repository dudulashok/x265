#!/bin/bash
# 2026-08-07: the three-way HDR-VDP-3 comparison (anchor vs hdr10opt vs
# prodstack) needs the hdr10opt arm, which was commented out of the post-rebase
# sweep -- anchor and prodstack encodes already exist. Detached-safe, resumable.
#
# Launch (from PowerShell):
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/run_hdr10opt_detached.sh'
# Progress: grep -c encoded *hdr10opt*.log ; done: hdr10opt_done.marker
cd "$(dirname "$0")"
rm -f hdr10opt_done.marker
{
    X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
    ANCHOR=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited)

    # prune partial outputs from any earlier interrupted run
    for f in *_hdr10opt_*.log; do
        [ -e "$f" ] || continue
        grep -q encoded "$f" || { echo "prune ${f%.log}"; rm -f "$f" "${f%.log}.hevc"; }
    done

    for crf in 22 26 30 34; do
        for clipfps in "sol10.yuv 24" "whale10.yuv 60"; do
            set -- $clipfps
            clip=$1; fps=$2
            out="${clip%.yuv}_hdr10opt_crf${crf}"
            if [ -f "$out.log" ] && grep -q encoded "$out.log"; then echo "skip $out"; continue; fi
            echo "=== $out $(date +%H:%M:%S)"
            "$X265" --input "$clip" --input-res 3840x2160 --fps "$fps" --input-depth 10 \
                --preset medium --crf "$crf" "${ANCHOR[@]}" --hdr10-opt -o "$out.hevc" 2>"$out.log"
            tail -1 "$out.log"
        done
    done
    echo ALL_HDR10OPT_ENCODES_DONE
} > hdr10opt_progress.out 2>&1 && touch hdr10opt_done.marker
