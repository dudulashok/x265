#!/bin/bash
# ABR / ABR+VBV validation sweep (2026-08-12): anchor vs prodmap under the
# two rate-control modes never tested (all prior validation was CRF).
# Bitrate targets = the anchor CRF-22/26/30/34 bitrates, so the ABR curves
# overlap the CRF curves and BD-rates are comparable.
# VBV arm: vbv-maxrate = target, vbv-bufsize = target (1-second buffer) --
# tight enough to exercise the VBV clip on both clips, and the profile Dolby
# Vision workflows require.
#
# Launch DETACHED (survives session timeouts; see run_sweep_detached.sh):
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/run_abr_sweep.sh'
# Progress:  tail abr_sweep_progress.out ; grep -c encoded *_abr*.log *_vbv*.log
# Finished:  abr_sweep_done.marker exists
cd "$(dirname "$0")"
rm -f abr_sweep_done.marker
{
    taskkill //F //IM x265.exe 2>/dev/null
    sleep 1
    for f in *_abr*.log *_vbv*.log; do
        [ -e "$f" ] || continue
        grep -q encoded "$f" || { echo "prune ${f%.log}"; rm -f "$f" "${f%.log}.hevc"; }
    done

    X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
    ANCHOR=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited)
    PRODMAP=(--hdr-pq --hdr-chroma-qp-map 0.25 --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0)

    encode() { # $1 clip $2 fps $3 cfg-name $4 mode(abr|vbv) $5 kbps; rest: cfg args
        local clip=$1 fps=$2 cfg=$3 mode=$4 kbps=$5; shift 5
        local out="${clip%.yuv}_${cfg}_${mode}${kbps}"
        [ -f "$out.log" ] && grep -q "encoded" "$out.log" && { echo "skip $out"; return; }
        local rc=(--bitrate "$kbps")
        [ "$mode" = vbv ] && rc+=(--vbv-maxrate "$kbps" --vbv-bufsize "$kbps")
        echo "start $out $(date +%H:%M:%S)"
        "$X265" --input "$clip" --input-res 3840x2160 --fps "$fps" --input-depth 10 \
            --preset medium "${rc[@]}" "$@" -o "$out.hevc" 2>"$out.log"
        tail -1 "$out.log"
    }

    for mode in abr vbv; do
        for kbps in 6500 11500 20000 33500; do
            encode sol10.yuv 24 anchor  $mode $kbps "${ANCHOR[@]}"
            encode sol10.yuv 24 prodmap $mode $kbps "${PRODMAP[@]}"
        done
        for kbps in 1450 2300 3700 6200; do
            encode whale10.yuv 60 anchor  $mode $kbps "${ANCHOR[@]}"
            encode whale10.yuv 60 prodmap $mode $kbps "${PRODMAP[@]}"
        done
    done
    echo "ABR/VBV sweep complete $(date)"
    touch abr_sweep_done.marker
} > abr_sweep_progress.out 2>&1
