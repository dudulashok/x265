#!/bin/bash
# Detached wrapper for uz_metrics.py (space-free Start-Process arg).
# Progress: uz_metrics_run.out ; done marker uz_metrics_done.marker
cd "$(dirname "$0")"
rm -f uz_metrics_done.marker
python uz_metrics.py > uz_metrics_run.out 2>&1
touch uz_metrics_done.marker
