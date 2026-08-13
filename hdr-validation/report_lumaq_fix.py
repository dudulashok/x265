#!/usr/bin/env python3
"""BD report for the hdr-luma-qp fix (2026-08-13).

CRF side: lumaq05 (pre-fix) and lumaq05fix (post-fix) vs anchor, plus
fix-vs-prefix directly (bounds the cu-tree interplay shift under CRF).
ABR/VBV side is printed by abr_metrics.py; repeated here for one view.
"""
import json
import numpy as np
from bdrate import bd_rate

r = json.load(open("results.json"))
FIELDS = ["psnr_y", "wpsnr_y", "wpsnr_cb", "wpsnr_cr", "xpsnr_y"]


def curve(clip, cfg, mode, points):
    ks = [f"{clip}_{cfg}_{mode}{p}" for p in points]
    if not all(k in r and "wpsnr_y" in r[k] for k in ks):
        return None
    return ks


def bd_row(label, ka, kt):
    row = f"{label:<38}"
    for f in FIELDS:
        ra = np.array([r[k]["kbps"] for k in ka]); qa = np.array([r[k][f] for k in ka])
        rt = np.array([r[k]["kbps"] for k in kt]); qt = np.array([r[k][f] for k in kt])
        row += f"{bd_rate(ra, qa, rt, qt):>+10.2f}"
    print(row)


CRFS = [22, 26, 30, 34]
ABR_PTS = {"sol10": [6500, 11500, 20000, 33500], "whale10": [1450, 2300, 3700, 6200]}

print(f"{'comparison':<38}" + "".join(f"{f:>10}" for f in FIELDS))
for clip in ["sol10", "whale10"]:
    anchor_crf = curve(clip, "anchor", "crf", CRFS)
    pre = curve(clip, "lumaq05", "crf", CRFS)
    post = curve(clip, "lumaq05fix", "crf", CRFS)
    if anchor_crf and pre:
        bd_row(f"{clip} CRF  lumaq05(prefix) vs anchor", anchor_crf, pre)
    if anchor_crf and post:
        bd_row(f"{clip} CRF  lumaq05fix      vs anchor", anchor_crf, post)
    if pre and post:
        bd_row(f"{clip} CRF  lumaq05fix      vs prefix", pre, post)
    for mode in ["abr", "vbv"]:
        anchor_m = curve(clip, "anchor", mode, ABR_PTS[clip])
        pre_m = curve(clip, "lumaq05", mode, ABR_PTS[clip])
        post_m = curve(clip, "lumaq05fix", mode, ABR_PTS[clip])
        if anchor_m and pre_m:
            bd_row(f"{clip} {mode.upper():<4} lumaq05(prefix) vs anchor", anchor_m, pre_m)
        if anchor_m and post_m:
            bd_row(f"{clip} {mode.upper():<4} lumaq05fix      vs anchor", anchor_m, post_m)

print("\nRATE ACCURACY (single-pass ABR, deviation from target)")
for clip in ["sol10", "whale10"]:
    for cfg in ["anchor", "lumaq05", "lumaq05fix"]:
        devs = []
        for p in ABR_PTS[clip]:
            k = f"{clip}_{cfg}_abr{p}"
            if k in r and "kbps" in r[k]:
                devs.append(100 * (r[k]["kbps"] - p) / p)
        if devs:
            print(f"{clip:<9}{cfg:<12}" + " ".join(f"{d:>+7.2f}" for d in devs))
