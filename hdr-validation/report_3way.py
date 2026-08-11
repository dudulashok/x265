"""Three-way operating-point report: default anchor vs the in-tree --hdr10-opt
vs the recommended HDR production stack, on both real-content clips.

Prints, per clip and CRF, the columns the project reports on:
    kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | Q_JOD
followed by BD-rate for each metric against the anchor (negative = the config
saves bitrate at equal quality; for Q_JOD, negative = saves bitrate at equal
perceptual quality).
"""
import json
import numpy as np


def bd_rate(r_a, q_a, r_t, q_t):
    """Same cubic BD-rate as bdrate.py (inlined -- importing that module would
    execute its top-level report and print stray tables)."""
    la, lt = np.log(r_a), np.log(r_t)
    pa, pt = np.polyfit(q_a, la, 3), np.polyfit(q_t, lt, 3)
    lo, hi = max(min(q_a), min(q_t)), min(max(q_a), max(q_t))
    ia = np.polyval(np.polyint(pa), [lo, hi])
    it = np.polyval(np.polyint(pt), [lo, hi])
    return (np.exp(((it[1] - it[0]) - (ia[1] - ia[0])) / (hi - lo)) - 1) * 100

# 2026-08-11: prodmap (the new recommended stack) joins the report, and the
# XPSNR columns land alongside wPSNR.
CFGS = ["anchor", "hdr10opt", "prodstack", "prodmap"]
LABEL = {"anchor": "default (anchor)",
         "hdr10opt": "--hdr10-opt",
         "prodstack": "prod stack",
         "prodmap": "prodmap"}
CRFS = [22, 26, 30, 34]
FIELDS = [("kbps", "kbps", "%10.1f"), ("psnr_y", "PSNR-Y", "%9.4f"),
          ("wpsnr_y", "wPSNR-Y", "%9.4f"), ("wpsnr_cb", "wPSNR-Cb", "%9.4f"),
          ("wpsnr_cr", "wPSNR-Cr", "%9.4f"), ("xpsnr_y", "XPSNR-Y", "%9.4f"),
          ("xpsnr_cb", "XPSNR-Cb", "%9.4f"), ("xpsnr_cr", "XPSNR-Cr", "%9.4f"),
          ("vdp_jod", "Q_JOD", "%8.4f")]

res = json.load(open("results.json"))

for clip in ["sol10", "whale10"]:
    print(f"\n=== {clip} " + "=" * 64)
    hdr = f"{'config':<18}{'CRF':>4}" + "".join(f"{h:>10}" for _, h, _ in FIELDS)
    print(hdr)
    print("-" * len(hdr))
    for cfg in CFGS:
        for crf in CRFS:
            e = res.get(f"{clip}_{cfg}_crf{crf}")
            if not e:
                continue
            line = f"{LABEL[cfg]:<18}{crf:>4}"
            for f, _, fmt in FIELDS:
                line += (fmt % e[f]).rjust(10) if f in e else "         -"
            print(line)
        print()

    print(f"--- BD-rate vs default anchor ({clip}), % ---")
    print(f"{'config':<18}" + "".join(f"{h:>10}" for _, h, _ in FIELDS[1:]))
    for cfg in CFGS[1:]:
        line = f"{LABEL[cfg]:<18}"
        for f, _, _ in FIELDS[1:]:
            try:
                ka = [f"{clip}_anchor_crf{c}" for c in CRFS]
                kt = [f"{clip}_{cfg}_crf{c}" for c in CRFS]
                ra = np.array([res[k]["kbps"] for k in ka])
                qa = np.array([res[k][f] for k in ka])
                rt = np.array([res[k]["kbps"] for k in kt])
                qt = np.array([res[k][f] for k in kt])
                line += ("%+9.2f" % bd_rate(ra, qa, rt, qt)).rjust(10)
            except (KeyError, TypeError):
                line += "         -"
        print(line)

# Per-frame Q_JOD spread: the previous round's 4-frame means could not
# separate configs, so report the sampling uncertainty alongside the mean.
try:
    import collections
    acc = collections.defaultdict(list)
    for ln in open("vdp_results.txt"):
        p = ln.split()
        if len(p) == 3:
            acc[p[0]].append(float(p[2]))
    print("\n=== Q_JOD sampling detail (n frames, mean, std, sem) ===")
    for clip in ["sol10", "whale10"]:
        for cfg in CFGS:
            for crf in CRFS:
                k = f"{clip}_{cfg}_crf{crf}"
                v = np.array(acc.get(k, []))
                if v.size:
                    print(f"{k:<28} n={v.size:<3} mean={v.mean():7.4f} "
                          f"std={v.std(ddof=1):6.4f} sem={v.std(ddof=1)/np.sqrt(v.size):6.4f}")
except OSError:
    pass
