#!/bin/bash
# Ultrafast + zero-latency HDR validation sweep (2026-08-27): anchor vs prodmap
# under ABR+VBV and capped-CRF, at --preset ultrafast --tune zerolatency.
# Purpose: zerolatency sets rc.cuTree=0 (and lookahead 0, bframes 0,
# frame-threads 1), so the HDR per-QG tools act WITHOUT cu-tree absorbing
# them — the cleanest read yet of the tools' own effect. Ultrafast also sets
# aq-mode 0 AND aq-strength 0.0, so both are re-enabled explicitly
# (aq-mode 2 per user decision 2026-08-27; the HDR tools require AQ).
# VBV buffer is TIGHT (bufsize = maxrate/2, ~500 ms) per user decision —
# realistic zero-latency sizing, deliberately NOT comparable to the 1-s
# buffers of the 2026-08-12/14 medium-preset sweeps.
#
# Key naming: {clip}_{cfg}_uzvbv{kbps} and {clip}_{cfg}_uzccrf{crf}; the
# capped-CRF caps come from stage-1 anchor uncapped probes
# ({clip}_anchor_uzcrf{crf}, kept only for cap derivation) at 1.1x, since the
# medium-preset caps do not transfer to ultrafast bitrates.
#
# Launch DETACHED (single space-free arg — PS 5.1 Start-Process quoting trap):
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList 'C:/x265_github/x265/hdr-validation/run_uz_sweep.sh'
# Progress: tail uz_sweep_progress.out ; done marker uz_sweep_done.marker
cd "$(dirname "$0")"
rm -f uz_sweep_done.marker
{
    for f in *_uzcrf*.log *_uzvbv*.log *_uzccrf*.log; do
        [ -e "$f" ] || continue
        grep -q encoded "$f" || { echo "prune ${f%.log}"; rm -f "$f" "${f%.log}.hevc"; }
    done

    X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
    BASE=(--preset ultrafast --tune zerolatency --aq-mode 2 --aq-strength 1.0)
    ANCHOR=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited)
    PRODMAP=(--hdr-pq --hdr-chroma-qp-map 0.25 --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0)
    declare -A FPS=( [sol10]=24 [whale10]=60 )
    declare -A NFRAMES=( [sol10]=192 [whale10]=300 )

    encode() { # $1 clip-stem $2 out-name; rest: rc + cfg args
        local clip=$1 out=$2; shift 2
        [ -f "$out.log" ] && grep -q "encoded" "$out.log" && { echo "skip $out"; return; }
        echo "start $out $(date +%H:%M:%S)"
        "$X265" --input "$clip.yuv" --input-res 3840x2160 --fps "${FPS[$clip]}" \
            --input-depth 10 "${BASE[@]}" "$@" -o "$out.hevc" 2>"$out.log"
        tail -1 "$out.log"
    }

    # ---- stage 1: anchor uncapped-CRF probes (cap derivation only) ----
    for clip in sol10 whale10; do
        for crf in 22 26 30 34; do
            encode $clip "${clip}_anchor_uzcrf${crf}" --crf $crf "${ANCHOR[@]}"
        done
    done

    cap() { # $1 clip $2 crf -> 1.1x probe bitrate in kbps
        local clip=$1 crf=$2 sz dur
        sz=$(stat -c%s "${clip}_anchor_uzcrf${crf}.hevc")
        dur=$(( ${NFRAMES[$clip]} * 100 / ${FPS[$clip]} ))   # centiseconds
        echo $(( sz * 8 * 11 / 10 / dur / 10 ))              # kbps, floor
    }

    # ---- stage 2: capped-CRF (uzccrf), bufsize = maxrate/2 ----
    for clip in sol10 whale10; do
        for crf in 22 26 30 34; do
            mr=$(cap $clip $crf)
            echo "cap ${clip} crf${crf} = ${mr} kbps"
            encode $clip "${clip}_anchor_uzccrf${crf}" --crf $crf \
                --vbv-maxrate $mr --vbv-bufsize $((mr / 2)) "${ANCHOR[@]}"
            encode $clip "${clip}_prodmap_uzccrf${crf}" --crf $crf \
                --vbv-maxrate $mr --vbv-bufsize $((mr / 2)) "${PRODMAP[@]}"
        done
    done

    # ---- stage 3: ABR+VBV (uzvbv), bufsize = target/2 ----
    for kbps in 6500 11500 20000 33500; do
        encode sol10 "sol10_anchor_uzvbv${kbps}" --bitrate $kbps \
            --vbv-maxrate $kbps --vbv-bufsize $((kbps / 2)) "${ANCHOR[@]}"
        encode sol10 "sol10_prodmap_uzvbv${kbps}" --bitrate $kbps \
            --vbv-maxrate $kbps --vbv-bufsize $((kbps / 2)) "${PRODMAP[@]}"
    done
    for kbps in 1450 2300 3700 6200; do
        encode whale10 "whale10_anchor_uzvbv${kbps}" --bitrate $kbps \
            --vbv-maxrate $kbps --vbv-bufsize $((kbps / 2)) "${ANCHOR[@]}"
        encode whale10 "whale10_prodmap_uzvbv${kbps}" --bitrate $kbps \
            --vbv-maxrate $kbps --vbv-bufsize $((kbps / 2)) "${PRODMAP[@]}"
    done

    echo "uz sweep complete $(date)"
    touch uz_sweep_done.marker
} > uz_sweep_progress.out 2>&1
