#!/bin/bash
# Stage-1 trace encodes for the cu-tree interaction study (2026-08-27):
# anchor vs anchor+--hdr-luma-qp 0.5 (the only per-QG AQ-coupled HDR tool) at
# medium CRF 30, cu-tree ON, with X265_DUMP_QPOFFS dumping the final per-block
# qpAqOffset/qpCuTreeOffset fields per frame. qpoffs_absorb.py pairs the
# off/on dumps to measure cu-tree's causal response to the injected term.
# Also re-encodes one arm WITHOUT the env var and byte-compares: proves the
# dump hook is bitstream-neutral (same binary, deterministic encoder).
# Launch DETACHED:
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList 'C:/x265_github/x265/hdr-validation/run_trace_encodes.sh'
# Progress: trace_progress.out ; done marker trace_done.marker
cd "$(dirname "$0")"
rm -f trace_done.marker
{
    X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
    ANCHOR=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited)
    declare -A FPS=( [sol10]=24 [whale10]=60 )

    trace() { # $1 clip $2 arm-name; rest: extra args
        local clip=$1 arm=$2; shift 2
        local out="trace_${clip}_${arm}"
        mkdir -p "dump_${clip}_${arm}"
        echo "start $out $(date +%H:%M:%S)"
        X265_DUMP_QPOFFS="dump_${clip}_${arm}" \
        "$X265" --input "$clip.yuv" --input-res 3840x2160 --fps "${FPS[$clip]}" \
            --input-depth 10 --preset medium --crf 30 "${ANCHOR[@]}" "$@" \
            -o "$out.hevc" 2>"$out.log"
        tail -1 "$out.log"
    }

    trace sol10 off
    trace sol10 on --hdr-luma-qp 0.5
    trace whale10 off
    trace whale10 on --hdr-luma-qp 0.5

    # neutrality check: same command, no dump env -> must be byte-identical
    echo "neutrality re-encode $(date +%H:%M:%S)"
    "$X265" --input whale10.yuv --input-res 3840x2160 --fps 60 --input-depth 10 \
        --preset medium --crf 30 "${ANCHOR[@]}" --hdr-luma-qp 0.5 \
        -o trace_whale10_on_nodump.hevc 2>trace_whale10_on_nodump.log
    if cmp -s trace_whale10_on.hevc trace_whale10_on_nodump.hevc; then
        echo "NEUTRALITY OK: dump-on and dump-off bitstreams byte-identical"
        rm -f trace_whale10_on_nodump.hevc trace_whale10_on_nodump.log
    else
        echo "NEUTRALITY FAIL: bitstreams differ"
    fi

    echo "trace encodes complete $(date)"
    touch trace_done.marker
} > trace_progress.out 2>&1
