#!/bin/bash
# Retry driver for abr_metrics.py: this machine silently kills long-lived
# python processes (~15-25 min), and the script is resumable (merge-on-write
# save after every metric), so just rerun until it prints the BD-RATE block.
# Launch DETACHED:
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/run_abr_metrics.sh'
cd "$(dirname "$0")"
rm -f abr_metrics_done.marker
for i in $(seq 1 20); do
    python abr_metrics.py > abr_report_2026-08-12.txt 2>&1
    grep -q "BD-RATE" abr_report_2026-08-12.txt && { touch abr_metrics_done.marker; exit 0; }
    echo "retry $i $(date +%H:%M:%S)" >> abr_metrics_progress.out
    sleep 2
done
echo "gave up after 20 retries" >> abr_metrics_progress.out
