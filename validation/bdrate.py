"""Bjontegaard-delta rate between anchor and test rate-quality curves.

Classic BD-rate: cubic polynomial fit of log(rate) as a function of the
quality metric; integrate the horizontal (log-rate) gap over the
overlapping quality interval. Negative = test saves bitrate at equal
quality. Works for any metric monotonically increasing with rate
(PSNR, wPSNR, XPSNR).

Importable (`from bdrate import bd_rate`); as a script it reports every
config named on the command line against `anchor`:

    python bdrate.py arf1 arf2
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

def main():
    res = json.load(open("results.json"))
    CRFS = [22, 26, 30, 34]
    CLIPS = ["sol10", "whale10"]
    CFGS = sys.argv[1:]
    if not CFGS:
        sys.exit("usage: python bdrate.py <config> [<config> ...]")

    def series(clip, cfg, field):
        keys = [f"{clip}_{cfg}_crf{c}" for c in CRFS]
        return (np.array([res[k]["kbps"] for k in keys]),
                np.array([res[k][field] for k in keys]))

    rows = []
    for clip in CLIPS:
        for cfg in CFGS:
            row = {"clip": clip, "config": cfg}
            for field in ["psnr_y", "wpsnr_y", "wpsnr_cb", "wpsnr_cr",
                          "xpsnr_y", "xpsnr_cb", "xpsnr_cr"]:
                try:
                    ra, qa = series(clip, "anchor", field)
                    rt, qt = series(clip, cfg, field)
                    row[field] = round(bd_rate(ra, qa, rt, qt), 2)
                except KeyError:
                    row[field] = None
            rows.append(row)
    print(json.dumps(rows, indent=1))

if __name__ == "__main__":
    main()
