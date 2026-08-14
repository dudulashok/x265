"""Metrics + report for the capped-CRF (CRF+VBV) sweep (run_ccrf_sweep.sh).

For every finished {clip}_{cfg}_ccrf{crf}.hevc: wPSNR/PSNR + XPSNR into
results.json (merge-on-write, resumable, same style as abr_metrics.py).
Then the three questions this sweep answers:
  1. cap compliance: actual bitrate vs the 1.1x-anchor vbv-maxrate cap
     (a capped-CRF encode may sit under the cap; exceeding it means the
     VBV constraint failed)
  2. VBV health: underflow/emergency warnings grepped from the encode logs
  3. BD-rate vs anchor within the ccrf mode, comparable to the CRF-mode
     numbers (prodmap sol10 -0.35 / whale10 -0.58 wPSNR-Y) and to the
     ABR/VBV fix-validation numbers (RESULTS.md 2026-08-13)
"""
import glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
W, H = 3840, 2160
FPS = {"sol10": 24.0, "whale10": 60.0}
FRAMES = {"sol10": 192, "whale10": 300}
CAP = {("sol10", 22): 36843, ("sol10", 26): 22133, ("sol10", 30): 12612, ("sol10", 34): 7136,
       ("whale10", 22): 6775, ("whale10", 26): 4119, ("whale10", 30): 2521, ("whale10", 34): 1578}

results = json.load(open("results.json")) if os.path.exists("results.json") else {}


def save():
    cur = json.load(open("results.json")) if os.path.exists("results.json") else {}
    for k, v in results.items():
        cur.setdefault(k, {}).update(v)
    json.dump(cur, open("results.json.tmp", "w"), indent=1)
    os.replace("results.json.tmp", "results.json")


from xpsnr import xpsnr as xpsnr_one

keys = []
for hevc in sorted(glob.glob("*_ccrf*.hevc")):
    key = hevc[:-5]
    m = re.match(r"(sol10|whale10)_(\w+)_ccrf(\d+)$", key)
    if not m or not os.path.exists(f"{key}.log"):
        continue
    if "encoded" not in open(f"{key}.log").read():
        print("UNFINISHED", key)
        continue
    clip = m.group(1)
    keys.append((key, clip, m.group(2), int(m.group(3))))
    ent = results.setdefault(key, {})
    ent["kbps"] = os.path.getsize(hevc) * 8 / (FRAMES[clip] / FPS[clip]) / 1000.0
    if "wpsnr_y" not in ent:
        out = subprocess.check_output(
            [sys.executable, "wpsnr.py", f"{clip}.yuv", hevc, str(W), str(H)])
        ent.update(json.loads(out))
        print(key, "wPSNR-Y %.4f" % ent["wpsnr_y"])
        save()
    if "xpsnr_y" not in ent:
        ent.update(xpsnr_one(f"{clip}.yuv", hevc, W, H, FPS[clip]))
        print(key, "XPSNR-Y %.4f" % ent["xpsnr_y"])
        save()

# ---- 1. cap compliance ----
print("\nCAP COMPLIANCE (actual kbps vs 1.1x-anchor vbv-maxrate; anchor CRF kbps for reference)")
print(f"{'key':<34}{'cap':>8}{'actual':>10}{'of cap%':>9}{'anchor@crf':>11}")
for key, clip, cfg, crf in keys:
    a = results[key]["kbps"]
    cap = CAP[(clip, crf)]
    ref = results.get(f"{clip}_anchor_crf{crf}", {}).get("kbps", float("nan"))
    print(f"{key:<34}{cap:>8}{a:>10.1f}{100*a/cap:>9.1f}{ref:>11.1f}")

# ---- 2. VBV health ----
print("\nVBV HEALTH (warnings in encode logs)")
bad = 0
for key, clip, cfg, crf in keys:
    warns = [ln.strip() for ln in open(f"{key}.log", errors="ignore")
             if re.search(r"underflow|emergency|VBV", ln, re.I) and "warning" in ln.lower()]
    for wl in warns:
        bad += 1
        print(f"{key}: {wl}")
print("none" if not bad else f"{bad} warnings")

# ---- 3. BD-rate vs anchor within the ccrf mode ----
import numpy as np
from bdrate import bd_rate

print("\nBD-RATE vs anchor, ccrf mode (negative = config saves bits at equal quality)")
print(f"{'clip':<9}{'config':<12}" + "".join(f"{f:>10}" for f in
      ["psnr_y", "wpsnr_y", "wpsnr_cb", "wpsnr_cr", "xpsnr_y"]))
for clip in ["sol10", "whale10"]:
    ks = sorted([k for (k, c, g, r) in keys if c == clip and g == "anchor"])
    if len(ks) < 4:
        continue
    for cfg in sorted(set(g for (k, c, g, r) in keys if c == clip and g != "anchor")):
        kt = sorted([k for (k, c, g, r) in keys if c == clip and g == cfg])
        if len(kt) < 4:
            print(f"{clip:<9}{cfg:<12} incomplete ({len(kt)} of 4)")
            continue
        row = f"{clip:<9}{cfg:<12}"
        for f in ["psnr_y", "wpsnr_y", "wpsnr_cb", "wpsnr_cr", "xpsnr_y"]:
            ra = np.array([results[k]["kbps"] for k in ks])
            qa = np.array([results[k][f] for k in ks])
            rt = np.array([results[k]["kbps"] for k in kt])
            qt = np.array([results[k][f] for k in kt])
            row += f"{bd_rate(ra, qa, rt, qt):>+10.2f}"
        print(row)
