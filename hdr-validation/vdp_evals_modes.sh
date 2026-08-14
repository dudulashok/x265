#!/bin/bash
# Resumable HDR-VDP-3 driver for the RATE-MODE arms (abr / vbv / ccrf keys),
# added 2026-08-14 so the absolute rate-quality tables can carry a Q_JOD
# column. Same 12-frame grids, crop and result format as vdp_evals.sh
# (results accumulate in vdp_results.txt, merged by merge_vdp.py).
#
# Differs from vdp_evals.sh in two ways:
#   - keys come from globbing {clip}_{cfg}_{mode}*.hevc for CFGS x MODES,
#     so bitrate/CRF points need no hard-coding;
#   - frames are prepped, evaluated and DELETED one key at a time (~300 MB
#     in flight) — the disk cannot hold 72 keys' worth of f32 dumps.
#
# Launch DETACHED:
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/vdp_evals_modes.sh'
# Progress: tail vdp_modes_progress.out ; done marker vdp_modes_done.marker
set -e
cd "$(dirname "$0")"
OCTAVE="$(cd .. && pwd)/octave-11.3.0-w64/mingw64/bin/octave-cli.exe"
PY=python
PAR=${PAR:-5}
CFGS=${CFGS:-"anchor lumaq05fix prodmapfix"}
MODES=${MODES:-"abr vbv ccrf"}
touch vdp_results.txt

declare -A FR=( [sol10]="8 24 40 56 72 88 104 120 136 152 168 184" \
                [whale10]="12 37 62 87 112 137 162 187 212 237 262 287" )

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

{
    rm -f vdp_modes_done.marker
    # refs must exist (kept from the CRF-mode passes); regenerate if missing
    for clip in sol10 whale10; do
        idxs="${FR[$clip]// /,}"
        for i in ${FR[$clip]}; do
            [ -f "$(printf 'vdp/ref_%s_%04d.f32' "$clip" "$i")" ] || \
                { $PY prep_frames.py yuv "$clip.yuv" 3840 2160 "vdp/ref_$clip" "$idxs" c1920x1080; break; }
        done
    done

    for clip in sol10 whale10; do
        idxs="${FR[$clip]// /,}"
        for cfg in $CFGS; do
            for mode in $MODES; do
                for hevc in "${clip}_${cfg}_${mode}"*.hevc; do
                    [ -e "$hevc" ] || continue
                    key="${hevc%.hevc}"
                    grep -q encoded "$key.log" 2>/dev/null || { echo "skip-unfinished $key"; continue; }
                    # pending frames for this key
                    : > vdp_jobs.txt
                    for i in ${FR[$clip]}; do
                        grep -q "^$key $i " vdp_results.txt && continue
                        printf '%s %s vdp/t_%s_%04d.f32 vdp/ref_%s_%04d.f32\n' \
                            "$key" "$i" "$key" "$i" "$clip" "$i" >> vdp_jobs.txt
                    done
                    [ -s vdp_jobs.txt ] || { echo "skip-done $key"; continue; }
                    echo "prep $key ($(wc -l < vdp_jobs.txt) evals) $(date +%H:%M:%S)"
                    $PY prep_frames.py hevc "$hevc" 3840 2160 "vdp/t_$key" "$idxs" c1920x1080 >/dev/null
                    xargs -a vdp_jobs.txt -L1 -P"$PAR" bash -c 'run_one "$@"' _
                    rm -f vdp/t_"$key"_*.f32
                done
            done
        done
    done
    echo "vdp modes pass complete $(date)"
    touch vdp_modes_done.marker
} > vdp_modes_progress.out 2>&1
