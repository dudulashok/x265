"""Chroma-offset depth series as a Pareto read: luma cost vs colour gain.

For each arm, the equal-bitrate deltas vs anchor (same interpolation as
rate_matched.py) averaged over the non-extrapolated CRF points:

    dwPSNR-Y   luma cost at equal bitrate (dB, negative = cost)
    dXPSNR-Y   same, on the perceptual luma metric
    dDEITP     colour gain at equal bitrate (sign-flipped: positive = better)
    dE/dB      exchange rate: dDEITP per dB of wPSNR-Y given up

The 2026-08-11 DeltaE-ITP backfill finally gives the chroma tools a metric
that sees them directly; this table asks whether prodmap's depth choice
(cqpmap 0.25) sits on the luma-vs-colour Pareto frontier.
"""
import collections, json, math, sys
import numpy as np

CRFS = [22, 26, 30, 34]
ARMS = sys.argv[1:] or ["chromaadapt", "fixed12", "cqpmap025", "hdrpq",
                        "cqpmap10ca", "cqpmap05", "cqpmap10", "hdr10opt"]

res = json.load(open("results.json"))


def interp_at(xs, ys, x):
    o = np.argsort(xs)
    xs, ys = np.asarray(xs)[o], np.asarray(ys)[o]
    if x < xs[0] or x > xs[-1]:
        return None, True
    return float(np.interp(x, xs, ys)), False


for clip in ["sol10", "whale10"]:
    la = np.log([res[f"{clip}_anchor_crf{c}"]["kbps"] for c in CRFS])
    ya = [res[f"{clip}_anchor_crf{c}"]["wpsnr_y"] for c in CRFS]
    xa = [res[f"{clip}_anchor_crf{c}"]["xpsnr_y"] for c in CRFS]
    dea = [res[f"{clip}_anchor_crf{c}"]["deitp_frames"] for c in CRFS]
    print(f"### {clip} (means over non-extrapolated CRF points)\n")
    print(f"{'arm':<12}{'n':>3}{'dwPSNR-Y':>10}{'dXPSNR-Y':>10}{'dDEITP':>9}{'dE/dB':>8}")
    for cfg in ARMS:
        dy, dx, de = [], [], []
        for crf in CRFS:
            e = res.get(f"{clip}_{cfg}_crf{crf}")
            if not e or "deitp_frames" not in e:
                continue
            lr = math.log(e["kbps"])
            ay, ex = interp_at(la, ya, lr)
            if ex:
                continue
            dy.append(e["wpsnr_y"] - ay)
            dx.append(e["xpsnr_y"] - interp_at(la, xa, lr)[0])
            de.append(np.mean([interp_at(la, [a[i] for a in dea], lr)[0]
                               - e["deitp_frames"][i]
                               for i in sorted(e["deitp_frames"], key=int)]))
        if not dy:
            print(f"{cfg:<12}  0 (all points extrapolated)")
            continue
        my, mx, me = np.mean(dy), np.mean(dx), np.mean(de)
        rate = me / -my if my < 0 else float("inf")
        r = "inf" if math.isinf(rate) else f"{rate:.2f}"
        print(f"{cfg:<12}{len(dy):>3}{my:>+10.3f}{mx:>+10.3f}{me:>+9.3f}{r:>8}")
    print()
