"""Equal-bitrate comparison: does the config actually raise wPSNR-Y and Q_JOD?

Why this exists: neither of the two tables we had answers the question directly.

  * A fixed-CRF comparison is rate-confounded -- --hdr10-opt at CRF 22 scores
    higher partly because it spends 31% more bits, which is not an improvement.
  * BD-rate collapses the whole curve into one number, and on Q_JOD that number
    carries a bootstrap CI wider than the effect (see bootstrap_jod_bd.py).

So: take each config's operating point, interpolate the ANCHOR curve to the
SAME bitrate, and report the score difference there. Positive = the config is
genuinely better at equal cost, which is the thing the project is trying to
improve.

Q_JOD is done per-frame so the pairing (same frames, same reference) is
preserved and a paired t-test is available. wPSNR is a deterministic
sequence-level number, so it needs no error bar.
"""
import collections, json
import math
import numpy as np

CRFS = [22, 26, 30, 34]
# 2026-08-08: prodmap is the candidate replacement for prodstack
CFGS = ["hdr10opt", "prodstack", "prodmap"]

res = json.load(open("results.json"))
acc = collections.defaultdict(dict)
for ln in open("vdp_results.txt"):
    p = ln.split()
    if len(p) == 3:
        acc[p[0]][int(p[1])] = float(p[2])


def interp_at(xs, ys, x):
    """Piecewise-linear in log-rate; linearly extrapolates outside the range.
    Returns (value, extrapolated?)."""
    o = np.argsort(xs)
    xs, ys = np.asarray(xs)[o], np.asarray(ys)[o]
    if x < xs[0]:
        s = (ys[1] - ys[0]) / (xs[1] - xs[0])
        return ys[0] + s * (x - xs[0]), True
    if x > xs[-1]:
        s = (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
        return ys[-1] + s * (x - xs[-1]), True
    return float(np.interp(x, xs, ys)), False


def t_sf(t, df):
    x = df / (df + t * t)
    a, b = df / 2.0, 0.5
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(200):
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


print("EQUAL-BITRATE score deltas vs default anchor")
print("(anchor curve interpolated to the config's own bitrate; "
      "positive = config is better at the same cost)")
print("  ! = the config's bitrate falls outside the anchor's measured range, "
      "so the anchor value is EXTRAPOLATED -- treat as indicative only.\n")

hdr = (f"{'clip':<9}{'config':<11}{'CRF':>4}{'kbps':>9}"
       f"{'dwPSNR-Y':>10}{'dwP-Cb':>9}{'dwP-Cr':>9}"
       f"{'dXP-Y':>9}{'dXP-Cb':>9}{'dXP-Cr':>9}{'dQ_JOD':>9}{'sem':>7}{'p':>9}  sig"
       f"{'dDEITP':>9}")
print(hdr)
print("-" * (len(hdr) + 4))

for clip in ["sol10", "whale10"]:
    la = np.log([res[f"{clip}_anchor_crf{c}"]["kbps"] for c in CRFS])
    FIELDS = ("wpsnr_y", "wpsnr_cb", "wpsnr_cr", "xpsnr_y", "xpsnr_cb", "xpsnr_cr")
    wa = {f: [res[f"{clip}_anchor_crf{c}"][f] for c in CRFS]
          for f in FIELDS
          if all(f in res[f"{clip}_anchor_crf{c}"] for c in CRFS)}
    frames = sorted(acc[f"{clip}_anchor_crf{CRFS[0]}"])
    for cfg in CFGS:
        for crf in CRFS:
            kt = f"{clip}_{cfg}_crf{crf}"
            if kt not in res or "wpsnr_y" not in res[kt]:
                continue
            lr = math.log(res[kt]["kbps"])
            dw, ex1 = {}, False
            for f in FIELDS:
                if f in wa and f in res[kt]:
                    av, ex = interp_at(la, wa[f], lr)
                    dw[f] = res[kt][f] - av
                    ex1 = ex1 or ex

            def col(f, wd=9):
                return f"{dw[f]:>+{wd}.4f}" if f in dw else f"{'-':>{wd}}"

            line = (f"{clip:<9}{cfg:<11}{crf:>4}{res[kt]['kbps']:>9.1f}"
                    f"{col('wpsnr_y', 10)}{col('wpsnr_cb')}{col('wpsnr_cr')}"
                    f"{col('xpsnr_y')}{col('xpsnr_cb')}{col('xpsnr_cr')}")
            if acc.get(kt):
                d = []
                for i in frames:
                    qa = [acc[f"{clip}_anchor_crf{c}"][i] for c in CRFS]
                    av, ex2 = interp_at(la, qa, lr)
                    d.append(acc[kt][i] - av)
                d = np.array(d)
                sem = d.std(ddof=1) / np.sqrt(d.size)
                t = d.mean() / sem if sem > 0 else 0.0
                p = t_sf(abs(t), d.size - 1)
                sig = ("***" if p < 0.001 else "**" if p < 0.01
                       else "*" if p < 0.05 else "ns")
                line += f"{d.mean():>+9.4f}{sem:>7.4f}{p:>9.2e}  {sig}"
            else:
                line += f"{'-':>9}{'-':>7}{'-':>9}  -"
            # DeltaE-ITP, paired per frame like Q_JOD but LOWER = better, so
            # the delta is (anchor_at_rate - config): positive = config better
            dea = [res[f"{clip}_anchor_crf{c}"].get("deitp_frames") for c in CRFS]
            det = res[kt].get("deitp_frames")
            if det and all(dea):
                d = []
                for i in sorted(det, key=int):
                    av, _ = interp_at(la, [a[i] for a in dea], lr)
                    d.append(av - det[i])
                line += f"{np.mean(d):>+9.4f}"
            else:
                line += f"{'-':>9}"
            print(line + ("   !" if ex1 else ""))
        print()

print("Reading it: a config that improves the encoder shows POSITIVE dwPSNR-Y")
print("and POSITIVE dQ_JOD at equal bitrate. Mixed signs mean the config is")
print("trading one metric for the other, not improving quality per bit.")
print("dDEITP is sign-flipped to match (anchor minus config, since lower")
print("DeltaE is better): positive = config has less colour error per bit.")
