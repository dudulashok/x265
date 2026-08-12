#!/bin/bash
# ABR luma-cost decomposition (2026-08-12 late): which prodmap component turns
# CRF's luma gain into ABR's +1.5..+2.0% luma cost? Three single-component
# arms under plain ABR (no VBV clip in the way):
#   hdrpq    -- chroma offsets only (the mechanical "luma pays the chroma
#               bill under a fixed budget" suspect)
#   lumaq05  -- per-QG luma model only (AQ-path interaction with cplxr)
#   sceneqp10 -- per-frame QP bias inside rateEstimateQscale (direct RC suspect)
# Compare against the anchor/prodmap ABR arms already in results.json.
#
# Launch DETACHED:
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/run_abr_decomp.sh'
# Progress: tail abr_decomp_progress.out ; done marker abr_decomp_done.marker
cd "$(dirname "$0")"
rm -f abr_decomp_done.marker
{
    taskkill //F //IM x265.exe 2>/dev/null
    sleep 1
    for f in *_hdrpq_abr*.log *_lumaq05_abr*.log *_sceneqp10_abr*.log; do
        [ -e "$f" ] || continue
        grep -q encoded "$f" || { echo "prune ${f%.log}"; rm -f "$f" "${f%.log}.hevc"; }
    done

    X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
    HDRPQ=(--hdr-pq)
    LUMAQ05=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited --hdr-luma-qp 0.5)
    SCENEQP10=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited --hdr-scene-qp 1.0)

    encode() { # $1 clip $2 fps $3 cfg-name $4 kbps; rest: cfg args
        local clip=$1 fps=$2 cfg=$3 kbps=$4; shift 4
        local out="${clip%.yuv}_${cfg}_abr${kbps}"
        [ -f "$out.log" ] && grep -q "encoded" "$out.log" && { echo "skip $out"; return; }
        echo "start $out $(date +%H:%M:%S)"
        "$X265" --input "$clip" --input-res 3840x2160 --fps "$fps" --input-depth 10 \
            --preset medium --bitrate "$kbps" "$@" -o "$out.hevc" 2>"$out.log"
        tail -1 "$out.log"
    }

    for kbps in 6500 11500 20000 33500; do
        encode sol10.yuv 24 hdrpq     $kbps "${HDRPQ[@]}"
        encode sol10.yuv 24 lumaq05   $kbps "${LUMAQ05[@]}"
        encode sol10.yuv 24 sceneqp10 $kbps "${SCENEQP10[@]}"
    done
    for kbps in 1450 2300 3700 6200; do
        encode whale10.yuv 60 hdrpq     $kbps "${HDRPQ[@]}"
        encode whale10.yuv 60 lumaq05   $kbps "${LUMAQ05[@]}"
        encode whale10.yuv 60 sceneqp10 $kbps "${SCENEQP10[@]}"
    done
    echo "ABR decomposition sweep complete $(date)"
    touch abr_decomp_done.marker
} > abr_decomp_progress.out 2>&1
