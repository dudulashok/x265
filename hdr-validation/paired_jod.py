"""Paired per-frame Q_JOD comparison against the anchor.

The per-config Q_JOD standard error is dominated by *content* variance (some
frames are simply harder than others), which is identical for every config
because every config is evaluated on the same frame indices. The meaningful
uncertainty for "is config X better than the anchor" is therefore the spread
of the per-frame DIFFERENCE, not the spread of each mean -- that is what this
prints, with a paired t-test.

This is the analysis that was missing when the first (4-frame) round concluded
that the Q_JOD deltas were "inside sampling noise".
"""
import collections
import math
import numpy as np

CRFS = [22, 26, 30, 34]
# 2026-08-08: prodmap is the candidate replacement for prodstack
CFGS = ["hdr10opt", "prodstack", "prodmap"]

acc = collections.defaultdict(dict)
for ln in open("vdp_results.txt"):
    p = ln.split()
    if len(p) == 3:
        acc[p[0]][int(p[1])] = float(p[2])


def t_sf(t, df):
    """Two-sided p-value for Student's t (regularized incomplete beta, no scipy)."""
    x = df / (df + t * t)
    a, b = df / 2.0, 0.5
    # continued fraction for I_x(a,b)
    lbeta = (math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b))
    front = np.exp(np.log(x) * a + np.log(1 - x) * b - lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 200):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        d = 1e-30 if abs(d) < 1e-30 else 1.0 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30:
            c = 1e-30
        f *= c * d
        if abs(1.0 - c * d) < 1e-10:
            break
    return front * (f - 1.0)


print("Paired per-frame Q_JOD delta vs anchor (same frames, same reference)")
print("positive = config scores better than anchor at the SAME CRF\n")
hdr = f"{'clip':<9}{'config':<11}{'CRF':>4}{'dQ_JOD':>9}{'sem':>8}{'t':>8}{'p':>9}  {'sig':<4} {'kbps vs anchor':>15}"
print(hdr)
print("-" * len(hdr))

import json
res = json.load(open("results.json"))

for clip in ["sol10", "whale10"]:
    for cfg in CFGS:
        for crf in CRFS:
            ka, kt = f"{clip}_anchor_crf{crf}", f"{clip}_{cfg}_crf{crf}"
            fr = sorted(set(acc[ka]) & set(acc[kt]))
            if not fr:
                continue
            d = np.array([acc[kt][i] - acc[ka][i] for i in fr])
            n = d.size
            sem = d.std(ddof=1) / np.sqrt(n)
            t = d.mean() / sem if sem > 0 else 0.0
            p = t_sf(abs(t), n - 1)
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
            dr = (res[kt]["kbps"] / res[ka]["kbps"] - 1) * 100
            print(f"{clip:<9}{cfg:<11}{crf:>4}{d.mean():+9.4f}{sem:>8.4f}{t:>8.2f}"
                  f"{p:>9.2e}  {sig:<4} {dr:>+14.1f}%")
        print()
