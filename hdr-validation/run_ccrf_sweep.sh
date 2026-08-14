#!/bin/bash
# Capped-CRF (CRF+VBV) validation sweep (2026-08-14) — the one RC mode never
# measured (CRF, ABR and ABR+VBV are done). Per the 2026-08-13 session plan:
# CRF 22/26/30/34 with vbv-maxrate = 1.1x the anchor's bitrate at that CRF
# (per clip, from results.json anchor_crf* rows), vbv-bufsize = maxrate (1 s),
# same buffer rule as the ABR+VBV arms so the modes stay comparable.
#
# Arms (same three as the ABR/VBV fix validation, fixed binary 2026-08-13):
#   anchor      VUI-only flags
#   lumaq05fix  anchor + --hdr-luma-qp 0.5  — the interesting cell: the ABR fix
#               is mode-gated to X265_RC_ABR, so under capped-CRF the RAW
#               one-sided per-QG bias is live *and* the VBV clip engages;
#               this arm answers whether that combination misbehaves.
#   prodmapfix  the recommended stack (--hdr-pq --hdr-chroma-qp-map 0.25
#               --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0)
#
# Launch DETACHED:
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/run_ccrf_sweep.sh'
# Progress: tail ccrf_sweep_progress.out ; done marker ccrf_sweep_done.marker
cd "$(dirname "$0")"
rm -f ccrf_sweep_done.marker
{
    for f in *_ccrf*.log; do
        [ -e "$f" ] || continue
        grep -q encoded "$f" || { echo "prune ${f%.log}"; rm -f "$f" "${f%.log}.hevc"; }
    done

    X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
    ANCHOR=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited)
    LUMAQ=("${ANCHOR[@]}" --hdr-luma-qp 0.5)
    PRODMAP=(--hdr-pq --hdr-chroma-qp-map 0.25 --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0)

    # vbv-maxrate = 1.1x anchor CRF bitrate (results.json, 2026-08-14):
    # sol10   crf22 33493 -> 36843 | crf26 20121 -> 22133 | crf30 11466 -> 12612 | crf34 6487 -> 7136
    # whale10 crf22  6159 ->  6775 | crf26  3744 ->  4119 | crf30  2292 ->  2521 | crf34 1435 ->  1578
    cap() { # $1 clip $2 crf
        case "$1_$2" in
            sol10_22) echo 36843;; sol10_26) echo 22133;; sol10_30) echo 12612;; sol10_34) echo 7136;;
            whale10_22) echo 6775;; whale10_26) echo 4119;; whale10_30) echo 2521;; whale10_34) echo 1578;;
        esac
    }

    encode() { # $1 clip $2 fps $3 cfg-name $4 crf; rest: cfg args
        local clip=$1 fps=$2 cfg=$3 crf=$4; shift 4
        local out="${clip%.yuv}_${cfg}_ccrf${crf}"
        [ -f "$out.log" ] && grep -q "encoded" "$out.log" && { echo "skip $out"; return; }
        local mr; mr=$(cap "${clip%.yuv}" "$crf")
        echo "start $out cap=${mr} $(date +%H:%M:%S)"
        "$X265" --input "$clip" --input-res 3840x2160 --fps "$fps" --input-depth 10 \
            --preset medium --crf "$crf" --vbv-maxrate "$mr" --vbv-bufsize "$mr" \
            "$@" -o "$out.hevc" 2>"$out.log"
        tail -1 "$out.log"
    }

    for crf in 22 26 30 34; do
        encode sol10.yuv 24 anchor     $crf "${ANCHOR[@]}"
        encode sol10.yuv 24 lumaq05fix $crf "${LUMAQ[@]}"
        encode sol10.yuv 24 prodmapfix $crf "${PRODMAP[@]}"
        encode whale10.yuv 60 anchor     $crf "${ANCHOR[@]}"
        encode whale10.yuv 60 lumaq05fix $crf "${LUMAQ[@]}"
        encode whale10.yuv 60 prodmapfix $crf "${PRODMAP[@]}"
    done

    echo "ccrf sweep complete $(date)"
    touch ccrf_sweep_done.marker
} > ccrf_sweep_progress.out 2>&1
