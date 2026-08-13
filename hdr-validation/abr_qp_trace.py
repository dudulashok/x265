#!/usr/bin/env python3
"""Analyze per-frame rc-end debug traces (x265 --log-level debug).

Usage: python abr_qp_trace.py trace1.log trace2.log ...

For each log, parses lines of the form
  x265 [debug]: rc-end: poc N type X qpRc F qpAq F qpNoVbv F bits N satd N
and reports, per slice type and per time segment (first second vs rest):
  mean qpRc (RC bookkeeping QP), mean qpAq (actual coded QP),
  mean AQ offset (qpAq - qpRc), bits share, satd.
The AQ offset is the frame-mean per-QG offset the ABR cplxrSum/predictor
bookkeeping cannot see; comparing an anchor arm against an hdr-luma-qp arm
isolates the hdr term from the (zero-mean) aq-mode-2 and cu-tree terms.
"""
import re
import sys

LINE = re.compile(
    r"rc-end: poc (\d+) type (\w) qpRc ([\d.]+) qpAq ([\d.-]+) qpNoVbv ([\d.]+) bits (\d+) satd (\d+)")


def parse(path):
    frames = []
    with open(path, errors="replace") as f:
        for line in f:
            m = LINE.search(line)
            if m:
                frames.append(dict(
                    poc=int(m.group(1)), type=m.group(2),
                    qpRc=float(m.group(3)), qpAq=float(m.group(4)),
                    qpNoVbv=float(m.group(5)), bits=int(m.group(6)),
                    satd=int(m.group(7))))
    frames.sort(key=lambda x: x["poc"])
    return frames


def seg_stats(frames, types="IPB"):
    sel = [f for f in frames if f["type"] in types]
    if not sel:
        return None
    n = len(sel)
    return dict(
        n=n,
        qpRc=sum(f["qpRc"] for f in sel) / n,
        qpAq=sum(f["qpAq"] for f in sel) / n,
        dAq=sum(f["qpAq"] - f["qpRc"] for f in sel) / n,
        bits=sum(f["bits"] for f in sel),
        satd=sum(f["satd"] for f in sel) / n)


def report(path):
    frames = parse(path)
    if not frames:
        print(f"{path}: no rc-end lines found")
        return
    total_bits = sum(f["bits"] for f in frames)
    print(f"\n=== {path}  ({len(frames)} frames, total {total_bits/1000:.0f} kbit)")
    print(f"{'seg':>10} {'type':>4} {'n':>4} {'qpRc':>7} {'qpAq':>7} {'dAQ':>6} {'bits%':>6}")
    half = len(frames) // 2
    segs = [("all", frames), ("first-half", frames[:half]), ("second-half", frames[half:])]
    for name, seg in segs:
        for t in "IPB":
            s = seg_stats(seg, t)
            if s:
                print(f"{name:>10} {t:>4} {s['n']:>4} {s['qpRc']:>7.2f} {s['qpAq']:>7.2f} "
                      f"{s['dAq']:>6.2f} {100*s['bits']/total_bits:>6.2f}")
    # convergence trace: P-frame qpRc in display order
    ps = [f for f in frames if f["type"] == "P"]
    print("P qpRc trace: " + " ".join(f"{f['qpRc']:.1f}" for f in ps[:20]) +
          (" ..." if len(ps) > 20 else ""))
    print("P dAQ  trace: " + " ".join(f"{f['qpAq']-f['qpRc']:+.1f}" for f in ps[:20]) +
          (" ..." if len(ps) > 20 else ""))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        report(p)
