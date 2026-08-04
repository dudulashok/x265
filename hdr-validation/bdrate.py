"""Bjontegaard-delta rate between anchor and test rate-quality curves.

Classic BD-rate: cubic polynomial fit of log(rate) as a function of the
quality metric; integrate the horizontal (log-rate) gap over the
overlapping quality interval. Negative = test saves bitrate at equal
quality. Works for any metric monotonically increasing with rate
(PSNR, wPSNR, HDR-VDP Q_JOD).
"""
import json, sys
import numpy as np

def bd_rate(r_a, q_a, r_t, q_t):
    la, lt = np.log(r_a), np.log(r_t)
    pa = np.polyfit(q_a, la, 3)
    pt = np.polyfit(q_t, lt, 3)
    lo, hi = max(min(q_a), min(q_t)), min(max(q_a), max(q_t))
    ia = np.polyval(np.polyint(pa), [lo, hi])
    it = np.polyval(np.polyint(pt), [lo, hi])
    avg = ((it[1] - it[0]) - (ia[1] - ia[0])) / (hi - lo)
    return (np.exp(avg) - 1) * 100

res = json.load(open("results.json"))
CRFS = [22, 26, 30, 34]

def series(clip, cfg, field):
    keys = [f"{clip}_{cfg}_crf{c}" for c in CRFS]
    return (np.array([res[k]["kbps"] for k in keys]),
            np.array([res[k][field] for k in keys]))

rows = []
for clip in ["sol10", "whale10"]:
    for cfg in ["hdrluma", "hdrpq", "wsse05", "wsse10", "wsse15", "dbk10",
                "lumaq025", "lumaq05", "lumaq075", "lumaq10", "lumaq15"]:
        row = {"clip": clip, "config": cfg}
        for field in ["psnr_y", "wpsnr_y", "wpsnr_cb", "wpsnr_cr", "vdp_jod"]:
            try:
                ra, qa = series(clip, "anchor", field)
                rt, qt = series(clip, cfg, field)
                row[field] = round(bd_rate(ra, qa, rt, qt), 2)
            except KeyError:
                row[field] = None
        rows.append(row)
print(json.dumps(rows, indent=1))
