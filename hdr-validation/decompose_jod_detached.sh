#!/bin/bash
# 12-frame Q_JOD for the two decomposition arms, so the production stack's
# Q_JOD position can be attributed to a specific tool:
#   hdrpq   = --hdr-pq alone            (the chroma-offset floor, luma untouched)
#   hdrluma = --hdr-pq --hdr-luma-qp 1.0 --hdr-scene-qp 1.0   (pre-rebase arm)
# vs the already-measured prodstack (= hdrpq + chroma-adapt 1.0 + luma-qp 0.5
# + scene-qp 1.0). Encodes already exist -- this is metric work only.
# Answers: is the prodstack Q_JOD position driven by --hdr-chroma-adapt (which
# HDR-VDP-3 should barely see, its quality pathway being achromatic) or by the
# --hdr-luma-qp strength drop 1.0 -> 0.5?
cd "$(dirname "$0")"
rm -f decompose_jod_done.marker
{
CFGS="hdrpq hdrluma" PAR=8 bash vdp_evals.sh
python merge_vdp.py
echo "=== rate-matched decomposition ==="
python rate_matched_decomp.py
echo ALL_DECOMPOSE_DONE
} > decompose_jod.out 2>&1 && touch decompose_jod_done.marker
