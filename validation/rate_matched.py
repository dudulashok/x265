"""Equal-bitrate comparison: does the config actually improve quality per bit?

Why this exists (methodology rule inherited from the HDR project,
2026-08-07): a fixed-CRF comparison is rate-confounded -- a config can
score higher at the same CRF simply by spending more bits, which is not
an improvement -- and BD-rate collapses the whole curve into one number.

So: take each config's operating point, interpolate the ANCHOR curve to
the SAME bitrate, and report the score difference there. Positive =
the config is genuinely better at equal cost.

    python rate_matched.py arf1 [more configs ...]
"""
import json
import math
import sys
import numpy as np

CRFS = [22, 26, 30, 34]
CFGS = sys.argv[1:]
if not CFGS:
    sys.exit("usage: python rate_matched.py <config> [<config> ...]")

res = json.load(open("results.json"))


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


print("EQUAL-BITRATE score deltas vs default anchor")
print("(anchor curve interpolated to the config's own bitrate; "
      "positive = config is better at the same cost)")
print("  ! = the config's bitrate falls outside the anchor's measured range, "
      "so the anchor value is EXTRAPOLATED -- treat as indicative only.\n")

FIELDS = ("psnr_y", "wpsnr_y", "wpsnr_cb", "wpsnr_cr",
          "xpsnr_y", "xpsnr_cb", "xpsnr_cr")
hdr = (f"{'clip':<9}{'config':<11}{'CRF':>4}{'kbps':>9}"
       f"{'dPSNR-Y':>10}{'dwPSNR-Y':>10}{'dwP-Cb':>9}{'dwP-Cr':>9}"
       f"{'dXP-Y':>9}{'dXP-Cb':>9}{'dXP-Cr':>9}")
print(hdr)
print("-" * (len(hdr) + 4))

for clip in ["sol10", "whale10"]:
    la = np.log([res[f"{clip}_anchor_crf{c}"]["kbps"] for c in CRFS])
    wa = {f: [res[f"{clip}_anchor_crf{c}"][f] for c in CRFS]
          for f in FIELDS
          if all(f in res[f"{clip}_anchor_crf{c}"] for c in CRFS)}
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
                    f"{col('psnr_y', 10)}{col('wpsnr_y', 10)}"
                    f"{col('wpsnr_cb')}{col('wpsnr_cr')}"
                    f"{col('xpsnr_y')}{col('xpsnr_cb')}{col('xpsnr_cr')}")
            print(line + ("   !" if ex1 else ""))
        print()

print("Reading it: a config that improves the encoder shows POSITIVE deltas")
print("at equal bitrate. Mixed signs mean the config is trading one metric")
print("for another, not improving quality per bit.")
