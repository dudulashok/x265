"""Quantify cu-tree's response to injected HDR per-QG offsets (stage 1 of the
cu-tree interaction study, 2026-08-27).

Consumes two X265_DUMP_QPOFFS dump directories from encodes that differ ONLY
in the HDR per-QG tool (e.g. anchor vs anchor + --hdr-luma-qp 0.5):

  hdrTerm  = qpAq_on - qpAq_off          (the injected term, exact: the AQ
                                          base depends only on pixels+params)
  sub      = qpCuTree - qpAq             (cu-tree's subtraction, per encode)
  dSub     = sub_on - sub_off            (cu-tree's CAUSAL response: lowres
                                          costs/motion are identical, only the
                                          invQscaleFactor weighting changed)
  realized = applied_on - applied_off    (applied = qpCuTree on referenced
                                          frames, qpAq on non-referenced —
                                          frameencoder.cpp qpoffs selection)

Reported per slice type and overall, split into frame-MEAN component (the
2026-08-13 story) and the SPATIAL (mean-removed) component (the open
question): pass-through fraction = cov(realized~, hdrTerm~)/var(hdrTerm~),
absorption slope = -cov(dSub~, hdrTerm~)/var(hdrTerm~) on mean-removed
fields. 1.0 pass-through = cu-tree transparent; 0 = fully absorbed.

Usage: python qpoffs_absorb.py <dump_dir_off> <dump_dir_on> [maxframes]
"""
import glob, os, sys
import numpy as np

doff, don = sys.argv[1], sys.argv[2]
maxframes = int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 9


def load(path):
    with open(path) as f:
        hdr = f.readline().split()
        meta = {hdr[i]: int(hdr[i + 1]) for i in range(0, len(hdr), 2)}
        a = np.loadtxt(f, dtype=np.float64)
    assert a.shape == (meta["blocks"], 2), (path, a.shape, meta)
    return meta, a[:, 0], a[:, 1]  # meta, qpAq, qpCuTree


TYPES = {0: "B", 1: "P", 2: "I"}  # x265 sliceType enum B=0 P=1 I=2
rows = []
pocs = sorted(int(os.path.basename(p)[7:13]) for p in glob.glob(os.path.join(doff, "qpoffs_*.txt")))[:maxframes]
type_mismatch = 0
for poc in pocs:
    fa, fb = (os.path.join(d, "qpoffs_%06d.txt" % poc) for d in (doff, don))
    if not os.path.exists(fb):
        continue
    m0, aq0, ct0 = load(fa)
    m1, aq1, ct1 = load(fb)
    if m0["type"] != m1["type"] or m0["ref"] != m1["ref"]:
        type_mismatch += 1
        continue
    hdr = aq1 - aq0
    if np.abs(hdr).max() < 1e-9:
        continue  # no injection on this frame
    dsub = (ct1 - aq1) - (ct0 - aq0)
    applied0 = ct0 if m0["ref"] else aq0
    applied1 = ct1 if m1["ref"] else aq1
    realized = applied1 - applied0
    hm, dm, rm = hdr.mean(), dsub.mean(), realized.mean()
    hs, ds, rs = hdr - hm, dsub - dm, realized - rm
    var = (hs * hs).mean()
    rows.append(dict(poc=poc, type=TYPES.get(m0["type"], "?"), ref=m0["ref"],
                     hdr_mean=hm, dsub_mean=dm, realized_mean=rm,
                     hdr_sd=np.sqrt(var),
                     absorb_slope=(-(ds * hs).mean() / var) if var > 1e-12 else np.nan,
                     pass_slope=((rs * hs).mean() / var) if var > 1e-12 else np.nan))

if type_mismatch:
    print(f"note: {type_mismatch} frames skipped (slice type/ref mismatch between arms)")
print(f"{len(rows)} frames paired with a nonzero injected term\n")
print(f"{'type':<5}{'n':>4}{'inj mean':>10}{'inj sd':>8} | {'MEAN comp':>10}{'(realized)':>11} | "
      f"{'SPATIAL absorb':>15}{'pass-through':>13}")
for t in ["I", "P", "B"]:
    rs = [r for r in rows if r["type"] == t]
    if not rs:
        continue
    g = lambda k: np.array([r[k] for r in rs])
    inj, rea = g("hdr_mean"), g("realized_mean")
    # mean-component pass-through: realized frame-mean vs injected frame-mean
    mean_pass = (rea / inj)[np.abs(inj) > 0.05]
    print(f"{t:<5}{len(rs):>4}{inj.mean():>10.3f}{g('hdr_sd').mean():>8.3f} | "
          f"{(mean_pass.mean() if len(mean_pass) else np.nan):>10.3f}{'':>11} | "
          f"{np.nanmean(g('absorb_slope')):>15.3f}{np.nanmean(g('pass_slope')):>13.3f}")
print("\nmean comp = realized frame-mean / injected frame-mean (1.0 = passes through)")
print("spatial absorb = -slope(dSub~ vs hdrTerm~), pass-through = slope(realized~ vs hdrTerm~), mean-removed")
