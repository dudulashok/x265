#!/bin/bash
# Detached wrapper for nct_metrics.py (space-free Start-Process arg).
# Progress: nct_metrics_run.out ; done marker nct_metrics_done.marker
cd "$(dirname "$0")"
rm -f nct_metrics_done.marker
python nct_metrics.py > nct_metrics_run.out 2>&1
touch nct_metrics_done.marker
