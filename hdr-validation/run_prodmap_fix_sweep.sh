#!/bin/bash
# hdr-luma-qp ABR fix validation (2026-08-13): the prodmapfix arm is the same
# pure --hdr-luma-qp 0.5 configuration as the 2026-08-12 decomposition's
# lumaq05 arm, encoded with the fixed binary (zero-mean per-QG offsets +
# frame-level bias: absolute under CRF, EMA-relative under ABR/CBR).
# ABR arms answer "is the +0.7..+0.8% wPSNR-Y flip gone?" (compare against
# the pre-fix lumaq05 rows already in results.json); VBV arms cover ABR+VBV.
#
# Launch DETACHED:
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/run_lumaq_fix_sweep.sh'
# Progress: tail prodmap_fix_progress.out ; done marker prodmap_fix_done.marker
cd "$(dirname "$0")"
rm -f prodmap_fix_done.marker
{
    for f in *_prodmapfix_*.log; do
        [ -e "$f" ] || continue
        grep -q encoded "$f" || { echo "prune ${f%.log}"; rm -f "$f" "${f%.log}.hevc"; }
    done

    X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
    LUMAQ=(--hdr-pq --hdr-chroma-qp-map 0.25 --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0)

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
            encode sol10.yuv 24 prodmapfix $mode $kbps "${LUMAQ[@]}"
        done
        for kbps in 1450 2300 3700 6200; do
            encode whale10.yuv 60 prodmapfix $mode $kbps "${LUMAQ[@]}"
        done
    done

    echo "prodmap fix sweep complete $(date)"
    touch prodmap_fix_done.marker
} > prodmap_fix_progress.out 2>&1
