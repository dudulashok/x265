#!/bin/bash
# Detached-safe sweep driver for a thermally-throttling machine.
#
# Why this exists: session/tool timeouts kill the driving shell but NOT its
# x265 child, leaving an orphan that races the next resume (two writers on
# one output file). This wrapper reaps orphans, prunes partial outputs, and
# runs the sweep to completion in one long-lived process.
#
# Launch DETACHED so it survives session timeouts (from PowerShell):
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/run_sweep_detached.sh'
#
# Progress:  grep -c encoded *.log       (from hdr-validation/)
# Finished:  sweep_done.marker exists; narrative in sweep_progress.out
# NOTE: progress/marker filenames must NOT end in .log or the prune loop
# below would delete them (learned the hard way).
cd "$(dirname "$0")"
rm -f sweep_done.marker
{
    taskkill //F //IM x265.exe 2>/dev/null
    sleep 1
    for f in *.log; do
        [ -e "$f" ] || continue
        grep -q encoded "$f" || { echo "prune ${f%.log}"; rm -f "$f" "${f%.log}.hevc"; }
    done
    bash run_encodes.sh
} > sweep_progress.out 2>&1 && touch sweep_done.marker
