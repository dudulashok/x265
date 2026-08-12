"""Metrics + first report for the ABR/VBV sweep (run_abr_sweep.sh).

For every finished {clip}_{cfg}_{abr|vbv}{kbps}.hevc: wPSNR/PSNR + XPSNR into
results.json (merge-on-write, resumable, same keys style as the CRF sweep).
Then prints the three things this sweep exists to answer:
  1. rate accuracy: |actual-target|/target per encode, tools-on vs anchor
     (the zero-mean AQ-contribution rule predicts no degradation)
  2. VBV health: underflow/emergency warnings grepped from the encode logs
  3. BD-rate prodmap-vs-anchor within each mode, comparable to the CRF
     numbers (sol10 -0.35 / whale10 -0.58 wPSNR-Y)
"""
import glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
W, H = 3840, 2160
FPS = {"sol10": 24.0, "whale10": 60.0}
FRAMES = {"sol10": 192, "whale10": 300}

results = json.load(open("results.json")) if os.path.exists("results.json") else {}


def save():
    cur = json.load(open("results.json")) if os.path.exists("results.json") else {}
    for k, v in results.items():
        cur.setdefault(k, {}).update(v)
    json.dump(cur, open("results.json.tmp", "w"), indent=1)
    os.replace("results.json.tmp", "results.json")


from xpsnr import xpsnr as xpsnr_one

keys = []
for hevc in sorted(glob.glob("*_abr*.hevc")) + sorted(glob.glob("*_vbv*.hevc")):
    key = hevc[:-5]
    m = re.match(r"(sol10|whale10)_(\w+)_(abr|vbv)(\d+)$", key)
    if not m or not os.path.exists(f"{key}.log"):
        continue
    if "encoded" not in open(f"{key}.log").read():
        print("UNFINISHED", key)
        continue
    clip = m.group(1)
    keys.append((key, clip, m.group(2), m.group(3), int(m.group(4))))
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

# ---- 1. rate accuracy ----
print("\nRATE ACCURACY (deviation from target; sign = over/undershoot)")
print(f"{'key':<32}{'target':>8}{'actual':>10}{'dev%':>8}")
for key, clip, cfg, mode, target in keys:
    a = results[key]["kbps"]
    print(f"{key:<32}{target:>8}{a:>10.1f}{100*(a-target)/target:>+8.2f}")

# ---- 2. VBV health ----
print("\nVBV HEALTH (warnings in encode logs)")
bad = 0
for key, clip, cfg, mode, target in keys:
    warns = [ln.strip() for ln in open(f"{key}.log", errors="ignore")
             if re.search(r"underflow|emergency|VBV", ln, re.I) and "warning" in ln.lower()]
    for wl in warns:
        bad += 1
        print(f"{key}: {wl}")
print("none" if not bad else f"{bad} warnings")

# ---- 3. BD-rate prodmap vs anchor per mode ----
import numpy as np
from bdrate import bd_rate

print("\nBD-RATE prodmap vs anchor (negative = prodmap saves bits at equal quality)")
print(f"{'clip':<9}{'mode':<5}" + "".join(f"{f:>10}" for f in
      ["psnr_y", "wpsnr_y", "wpsnr_cb", "wpsnr_cr", "xpsnr_y"]))
for clip in ["sol10", "whale10"]:
    for mode in ["abr", "vbv"]:
        ks = sorted([k for (k, c, g, m, t) in keys if c == clip and m == mode and g == "anchor"])
        kt = sorted([k for (k, c, g, m, t) in keys if c == clip and m == mode and g == "prodmap"])
        if len(ks) < 4 or len(kt) < 4:
            print(f"{clip:<9}{mode:<5} incomplete ({len(ks)}/{len(kt)} of 4)")
            continue
        row = f"{clip:<9}{mode:<5}"
        for f in ["psnr_y", "wpsnr_y", "wpsnr_cb", "wpsnr_cr", "xpsnr_y"]:
            ra = np.array([results[k]["kbps"] for k in ks])
            qa = np.array([results[k][f] for k in ks])
            rt = np.array([results[k]["kbps"] for k in kt])
            qt = np.array([results[k][f] for k in kt])
            row += f"{bd_rate(ra, qa, rt, qt):>+10.2f}"
        print(row)
