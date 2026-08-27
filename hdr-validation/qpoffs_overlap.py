"""Redundancy check for the cu-tree interaction study: does cu-tree's own
per-QG subtraction field already contain the HDR luma-dQP pattern?

For each paired frame: sub = qpCuTree - qpAq in the ANCHOR arm (cu-tree's own
field, HDR-free), hdrTerm = qpAq_on - qpAq_off (the JVET term). On mean-
removed fields reports corr(sub~, hdrTerm~) and the regression slope
(QP of cu-tree discount per QP of HDR term) plus the two fields' sd.
A strongly positive slope means cu-tree already raises QP where the HDR
model would (and vice versa) — the tools' job is partly pre-done, which
shows as diminishing marginal BD gain with cu-tree on, with no interference
needed.

Usage: python qpoffs_overlap.py <dump_dir_off> <dump_dir_on>
"""
import glob, os, sys
import numpy as np

doff, don = sys.argv[1], sys.argv[2]


def load(path):
    with open(path) as f:
        hdr = f.readline().split()
        meta = {hdr[i]: int(hdr[i + 1]) for i in range(0, len(hdr), 2)}
        a = np.loadtxt(f, dtype=np.float64)
    return meta, a[:, 0], a[:, 1]


TYPES = {0: "B", 1: "P", 2: "I"}
acc = {}
for p in sorted(glob.glob(os.path.join(doff, "qpoffs_*.txt"))):
    poc = int(os.path.basename(p)[7:13])
    q = os.path.join(don, "qpoffs_%06d.txt" % poc)
    if not os.path.exists(q):
        continue
    m0, aq0, ct0 = load(p)
    m1, aq1, _ = load(q)
    if m0["type"] != m1["type"] or not m0["ref"]:
        continue  # sub field only meaningful/applied on referenced frames
    hdr = aq1 - aq0
    if np.abs(hdr).max() < 1e-9:
        continue
    sub = ct0 - aq0
    hs, ss = hdr - hdr.mean(), sub - sub.mean()
    vh, vs = (hs * hs).mean(), (ss * ss).mean()
    if vh < 1e-12 or vs < 1e-12:
        continue
    cov = (hs * ss).mean()
    t = TYPES.get(m0["type"], "?")
    acc.setdefault(t, []).append((cov / np.sqrt(vh * vs), cov / vh,
                                  np.sqrt(vh), np.sqrt(vs), sub.mean()))

print(f"{'type':<5}{'n':>4}{'corr':>8}{'slope':>8}{'hdr sd':>8}{'ct sd':>8}{'ct mean':>9}")
for t in ["I", "P", "B"]:
    if t not in acc:
        continue
    a = np.array(acc[t])
    print(f"{t:<5}{len(a):>4}{a[:,0].mean():>8.3f}{a[:,1].mean():>8.3f}"
          f"{a[:,2].mean():>8.3f}{a[:,3].mean():>8.3f}{a[:,4].mean():>9.3f}")
print("\ncorr/slope: mean-removed cu-tree subtraction (anchor arm) vs injected HDR term, referenced frames only")
print("slope = QP of cu-tree offset per QP of HDR term (positive = same direction = redundancy)")
