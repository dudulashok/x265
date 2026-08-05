#!/bin/bash
# Detached wPSNR metrics driver (companion to run_sweep_detached.sh).
# metrics.py is resumable via results.json; safe to relaunch anytime.
# Launch DETACHED (from PowerShell):
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/run_metrics_detached.sh'
# Finished: metrics_done.marker exists; narrative in metrics_progress.out
cd "$(dirname "$0")"
rm -f metrics_done.marker
WPSNR_ONLY=1 python metrics.py > metrics_progress.out 2>&1 && touch metrics_done.marker
