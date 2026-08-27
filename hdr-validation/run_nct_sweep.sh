#!/bin/bash
# cu-tree interaction diagnostic sweep (2026-08-27): anchor vs prodmap at
# MEDIUM preset, plain CRF 22-34, with --no-cutree — the single-variable
# companion to the existing {clip}_{anchor|prodmap}_crf{crf} rows (cu-tree
# on, same preset/flags/binary lineage). Motivation: the ultrafast+
# zerolatency sweep measured prodmap at −3.5..−4.9% wPSNR-Y without cu-tree
# vs −0.06..−0.64% with it at medium, but that comparison changes preset,
# lookahead, B-frames and VBV all at once. This sweep isolates cu-tree:
#   prodmapnct vs anchornct  — the tools' value without cu-tree, at medium
#   anchornct  vs anchor     — cu-tree's own value on this corpus
#   prodmapnct vs anchor     — net absolute (does no-cutree+tools beat default)
#
# Launch DETACHED (single space-free arg — PS 5.1 Start-Process quoting trap):
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList 'C:/x265_github/x265/hdr-validation/run_nct_sweep.sh'
# Progress: tail nct_sweep_progress.out ; done marker nct_sweep_done.marker
cd "$(dirname "$0")"
rm -f nct_sweep_done.marker
{
    for f in *nct_crf*.log; do
        [ -e "$f" ] || continue
        grep -q encoded "$f" || { echo "prune ${f%.log}"; rm -f "$f" "${f%.log}.hevc"; }
    done

    X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
    ANCHOR=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited)
    PRODMAP=(--hdr-pq --hdr-chroma-qp-map 0.25 --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0)
    declare -A FPS=( [sol10]=24 [whale10]=60 )

    encode() { # $1 clip-stem $2 cfg-name $3 crf; rest: cfg args
        local clip=$1 cfg=$2 crf=$3; shift 3
        local out="${clip}_${cfg}_crf${crf}"
        [ -f "$out.log" ] && grep -q "encoded" "$out.log" && { echo "skip $out"; return; }
        echo "start $out $(date +%H:%M:%S)"
        "$X265" --input "$clip.yuv" --input-res 3840x2160 --fps "${FPS[$clip]}" \
            --input-depth 10 --preset medium --crf "$crf" --no-cutree \
            "$@" -o "$out.hevc" 2>"$out.log"
        tail -1 "$out.log"
    }

    for crf in 22 26 30 34; do
        encode sol10 anchornct  $crf "${ANCHOR[@]}"
        encode sol10 prodmapnct $crf "${PRODMAP[@]}"
        encode whale10 anchornct  $crf "${ANCHOR[@]}"
        encode whale10 prodmapnct $crf "${PRODMAP[@]}"
    done

    echo "nct sweep complete $(date)"
    touch nct_sweep_done.marker
} > nct_sweep_progress.out 2>&1
