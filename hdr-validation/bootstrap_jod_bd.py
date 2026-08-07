"""Bootstrap confidence interval for the Q_JOD BD-rate.

Q_JOD spans only ~0.5-1.0 JOD across the whole CRF sweep, so a small error in
a per-CRF mean Q_JOD is amplified into a large BD-rate percentage. A BD-rate
number without an interval is therefore not decision-grade on this metric.

Resamples the 12 evaluated frames with replacement (the same resampled frame
set for anchor and test, preserving the pairing), recomputes each per-CRF mean
Q_JOD, refits BD-rate, and reports the percentile interval.
"""
import collections, json
import numpy as np

CRFS = [22, 26, 30, 34]
CFGS = ["hdr10opt", "prodstack"]
NBOOT = 4000
rng = np.random.default_rng(20260807)   # fixed seed: report must be reproducible

acc = collections.defaultdict(dict)
for ln in open("vdp_results.txt"):
    p = ln.split()
    if len(p) == 3:
        acc[p[0]][int(p[1])] = float(p[2])
res = json.load(open("results.json"))


def bd_rate(r_a, q_a, r_t, q_t):
    la, lt = np.log(r_a), np.log(r_t)
    pa, pt = np.polyfit(q_a, la, 3), np.polyfit(q_t, lt, 3)
    lo, hi = max(min(q_a), min(q_t)), min(max(q_a), max(q_t))
    if hi <= lo:
        return np.nan
    ia = np.polyval(np.polyint(pa), [lo, hi])
    it = np.polyval(np.polyint(pt), [lo, hi])
    return (np.exp(((it[1] - it[0]) - (ia[1] - ia[0])) / (hi - lo)) - 1) * 100


print("Q_JOD BD-rate vs anchor with bootstrap 95% CI "
      f"({NBOOT} resamples over the 12 evaluated frames, paired)\n")
print(f"{'clip':<9}{'config':<11}{'BD-rate':>10}{'95% CI':>22}{'P(<0)':>9}")
print("-" * 61)
for clip in ["sol10", "whale10"]:
    frames = sorted(acc[f"{clip}_anchor_crf{CRFS[0]}"])
    for cfg in CFGS:
        ra = np.array([res[f"{clip}_anchor_crf{c}"]["kbps"] for c in CRFS])
        rt = np.array([res[f"{clip}_{cfg}_crf{c}"]["kbps"] for c in CRFS])
        qa = np.array([np.mean([acc[f"{clip}_anchor_crf{c}"][i] for i in frames]) for c in CRFS])
        qt = np.array([np.mean([acc[f"{clip}_{cfg}_crf{c}"][i] for i in frames]) for c in CRFS])
        point = bd_rate(ra, qa, rt, qt)

        vals = []
        for _ in range(NBOOT):
            idx = rng.choice(len(frames), len(frames), replace=True)
            fr = [frames[i] for i in idx]
            qab = np.array([np.mean([acc[f"{clip}_anchor_crf{c}"][i] for i in fr]) for c in CRFS])
            qtb = np.array([np.mean([acc[f"{clip}_{cfg}_crf{c}"][i] for i in fr]) for c in CRFS])
            v = bd_rate(ra, qab, rt, qtb)
            if np.isfinite(v):
                vals.append(v)
        vals = np.array(vals)
        lo, hi = np.percentile(vals, [2.5, 97.5])
        print(f"{clip:<9}{cfg:<11}{point:>+10.2f}{f'[{lo:+.2f}, {hi:+.2f}]':>22}"
              f"{(vals < 0).mean():>9.2f}")
