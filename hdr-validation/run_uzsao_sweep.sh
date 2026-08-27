#!/bin/bash
# SAO control arm for the ultrafast+zerolatency sweep (2026-08-27, stage-0b of
# the cu-tree study): ultrafast disables SAO but --hdr-pq force-enables it, so
# the uz prodmap-vs-anchor BD conflates {HDR tools} with {SAO}. This arm is
# anchor + --sao under the SAME uzvbv/uzccrf points:
#   prodmap  vs anchorsao — the HDR tools' own value at uz
#   anchorsao vs anchor   — SAO's value at uz
# Caps reuse the stage-1 uzcrf probe files (same cap() rule).
# Launch DETACHED:
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList 'C:/x265_github/x265/hdr-validation/run_uzsao_sweep.sh'
# Progress: uzsao_progress.out ; done marker uzsao_done.marker
cd "$(dirname "$0")"
rm -f uzsao_done.marker
{
    for f in *_anchorsao_uz*.log; do
        [ -e "$f" ] || continue
        grep -q encoded "$f" || { echo "prune ${f%.log}"; rm -f "$f" "${f%.log}.hevc"; }
    done

    X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
    BASE=(--preset ultrafast --tune zerolatency --aq-mode 2 --aq-strength 1.0)
    ANCHORSAO=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited --sao)
    declare -A FPS=( [sol10]=24 [whale10]=60 )
    declare -A NFRAMES=( [sol10]=192 [whale10]=300 )

    encode() { # $1 clip-stem $2 out-name; rest: rc args
        local clip=$1 out=$2; shift 2
        [ -f "$out.log" ] && grep -q "encoded" "$out.log" && { echo "skip $out"; return; }
        echo "start $out $(date +%H:%M:%S)"
        "$X265" --input "$clip.yuv" --input-res 3840x2160 --fps "${FPS[$clip]}" \
            --input-depth 10 "${BASE[@]}" "$@" "${ANCHORSAO[@]}" -o "$out.hevc" 2>"$out.log"
        tail -1 "$out.log"
    }

    cap() { # $1 clip $2 crf -> 1.1x stage-1 probe bitrate in kbps
        local clip=$1 crf=$2 sz dur
        sz=$(stat -c%s "${clip}_anchor_uzcrf${crf}.hevc")
        dur=$(( ${NFRAMES[$clip]} * 100 / ${FPS[$clip]} ))
        echo $(( sz * 8 * 11 / 10 / dur / 10 ))
    }

    for clip in sol10 whale10; do
        for crf in 22 26 30 34; do
            mr=$(cap $clip $crf)
            encode $clip "${clip}_anchorsao_uzccrf${crf}" --crf $crf \
                --vbv-maxrate $mr --vbv-bufsize $((mr / 2))
        done
    done
    for kbps in 6500 11500 20000 33500; do
        encode sol10 "sol10_anchorsao_uzvbv${kbps}" --bitrate $kbps \
            --vbv-maxrate $kbps --vbv-bufsize $((kbps / 2))
    done
    for kbps in 1450 2300 3700 6200; do
        encode whale10 "whale10_anchorsao_uzvbv${kbps}" --bitrate $kbps \
            --vbv-maxrate $kbps --vbv-bufsize $((kbps / 2))
    done

    echo "uzsao sweep complete $(date)"
    touch uzsao_done.marker
} > uzsao_progress.out 2>&1
