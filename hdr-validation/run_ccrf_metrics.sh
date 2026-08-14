#!/bin/bash
# Detached wrapper for ccrf_metrics.py (2026-08-14). Output in ccrf_metrics.out,
# done marker ccrf_metrics_done.marker.
cd "$(dirname "$0")"
rm -f ccrf_metrics_done.marker
python ccrf_metrics.py > ccrf_metrics.out 2>&1
touch ccrf_metrics_done.marker
