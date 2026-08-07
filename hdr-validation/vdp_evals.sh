#!/bin/bash
# Resumable HDR-VDP-3 evaluation driver.
# Preps frames per encode (short-lived python), then runs octave evals
# N-way parallel via xargs. Results accumulate in vdp_results.txt as
# "<key> <frame> <Q_JOD>" lines; already-done pairs are skipped.
#
# 2026-08-07: sampling deepened from 4 to 12 frames per clip (the TODO item
# "current deltas are unusable for tuning" -- 4-frame means put the
# config-to-config deltas inside sampling noise). The 12-frame grids are
# SUPERSETS of the original 4-frame grids (sol10 24/72/120/168, whale10
# 37/112/187/262), so the pre-rebase 4-frame numbers stay comparable.
# Config list is the three-way comparison: default anchor vs the in-tree
# --hdr10-opt vs the recommended production stack.
set -e
cd "$(dirname "$0")"
OCTAVE="$(cd .. && pwd)/octave-11.3.0-w64/mingw64/bin/octave-cli.exe"
PY=python
PAR=${PAR:-4}
CFGS=${CFGS:-"anchor hdr10opt prodstack"}
touch vdp_results.txt

declare -A FR=( [sol10]="8 24 40 56 72 88 104 120 136 152 168 184" \
                [whale10]="12 37 62 87 112 137 162 187 212 237 262 287" )

# 1. prep missing reference and test frames (one short python process per encode)
for clip in sol10 whale10; do
    idxs="${FR[$clip]// /,}"
    for i in ${FR[$clip]}; do
        [ -f "$(printf 'vdp/ref_%s_%04d.f32' "$clip" "$i")" ] || \
            { $PY prep_frames.py yuv "$clip.yuv" 3840 2160 "vdp/ref_$clip" "$idxs" c1920x1080; break; }
    done
    for cfg in $CFGS; do
        for crf in 22 26 30 34; do
            key="${clip}_${cfg}_crf${crf}"
            [ -f "$key.hevc" ] || continue
            need=0
            for i in ${FR[$clip]}; do
                [ -f "$(printf 'vdp/t_%s_%04d.f32' "$key" "$i")" ] || \
                    { grep -q "^$key $i " vdp_results.txt || need=1; }
            done
            [ $need -eq 1 ] && $PY prep_frames.py hevc "$key.hevc" 3840 2160 "vdp/t_$key" "$idxs" c1920x1080
        done
    done
done

# 2. build pending job list
: > vdp_jobs.txt
for clip in sol10 whale10; do
    for cfg in $CFGS; do
        for crf in 22 26 30 34; do
            key="${clip}_${cfg}_crf${crf}"
            for i in ${FR[$clip]}; do
                t=$(printf 'vdp/t_%s_%04d.f32' "$key" "$i")
                r=$(printf 'vdp/ref_%s_%04d.f32' "$clip" "$i")
                [ -f "$t" ] || continue
                grep -q "^$key $i " vdp_results.txt && continue
                echo "$key $i $t $r" >> vdp_jobs.txt
            done
        done
    done
done
echo "$(wc -l < vdp_jobs.txt) evals pending"

# 3. run evals, PAR in parallel; append results atomically per line
export OCTAVE
run_one() {
    key=$1; i=$2; t=$3; r=$4
    out=$("$OCTAVE" --no-init-file run_hdrvdp.m "$t" "$r" 1920 1080 2>/dev/null | grep '^HDRVDP_Q_JOD=' | tail -1)
    jod=${out#HDRVDP_Q_JOD=}; jod=${jod%% *}
    if [ -n "$jod" ]; then
        echo "$key $i $jod" >> vdp_results.txt
        echo "done $key $i $jod"
    else
        echo "FAILED $key $i"
    fi
}
export -f run_one
xargs -a vdp_jobs.txt -L1 -P"$PAR" bash -c 'run_one "$@"' _
echo VDP_EVALS_DONE
