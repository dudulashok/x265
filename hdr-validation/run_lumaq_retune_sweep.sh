#!/bin/bash
# hdr-luma-qp strength re-tune under rate-targeted modes (2026-08-13, fixed
# binary 4.2+156-4a85f0835): the 0.5 operating point was CRF-tuned; now that
# the ABR fix landed (zero-mean per-QG + EMA-relative bias, mode-gated),
# find the ABR/ABR+VBV-optimal strength. 0.5 is already measured as
# lumaq05fix in both modes; this adds 0.25 / 0.75 / 1.0 (48 encodes) and
# chains abr_metrics.py (resumable -- if the machine kills it, relaunch).
# Watch sol10 VBV: the one cell where the EMA bias meets the VBV clip.
#
# Launch DETACHED:
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/run_lumaq_retune_sweep.sh'
# Progress: tail lumaq_retune_progress.out ; done marker lumaq_retune_done.marker
cd "$(dirname "$0")"
rm -f lumaq_retune_done.marker
{
    for f in *_lumaq025fix_*.log *_lumaq075fix_*.log *_lumaq10fix_*.log; do
        [ -e "$f" ] || continue
        grep -q encoded "$f" || { echo "prune ${f%.log}"; rm -f "$f" "${f%.log}.hevc"; }
    done

    X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
    VUI=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited)

    encode() { # $1 clip $2 fps $3 cfg-name $4 mode(abr|vbv) $5 kbps $6 strength
        local clip=$1 fps=$2 cfg=$3 mode=$4 kbps=$5 strength=$6
        local out="${clip%.yuv}_${cfg}_${mode}${kbps}"
        [ -f "$out.log" ] && grep -q "encoded" "$out.log" && { echo "skip $out"; return; }
        local rc=(--bitrate "$kbps")
        [ "$mode" = vbv ] && rc+=(--vbv-maxrate "$kbps" --vbv-bufsize "$kbps")
        echo "start $out $(date +%H:%M:%S)"
        "$X265" --input "$clip" --input-res 3840x2160 --fps "$fps" --input-depth 10 \
            --preset medium "${rc[@]}" "${VUI[@]}" --hdr-luma-qp "$strength" \
            -o "$out.hevc" 2>"$out.log"
        tail -1 "$out.log"
    }

    for mode in abr vbv; do
        for s in "lumaq025fix 0.25" "lumaq075fix 0.75" "lumaq10fix 1.0"; do
            set -- $s
            for kbps in 6500 11500 20000 33500; do
                encode sol10.yuv 24 "$1" $mode $kbps "$2"
            done
            for kbps in 1450 2300 3700 6200; do
                encode whale10.yuv 60 "$1" $mode $kbps "$2"
            done
        done
    done
    echo "lumaq retune encodes complete $(date)"

    # metrics + BD report in the same detached process (resumable)
    python abr_metrics.py
    echo "lumaq retune sweep complete $(date)"
    touch lumaq_retune_done.marker
} > lumaq_retune_progress.out 2>&1
