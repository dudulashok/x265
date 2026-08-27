"""Metrics + first report for the ultrafast+zerolatency sweep (run_uz_sweep.sh).

For every finished {clip}_{cfg}_{uzvbv|uzccrf}{point}.hevc: wPSNR/PSNR, XPSNR
and dE-ITP (12-frame HDR-VDP grid, Q_JOD-pairable) into results.json
(merge-on-write, resumable, same key style as the other sweeps). The stage-1
uncapped anchor probes (uzcrf keys) are cap-derivation scratch and are NOT
metric'd. Then prints:
  1. rate accuracy for the uzvbv arms (target vs actual)
  2. VBV health: underflow/emergency warnings in the encode logs
  3. BD-rate prodmap-vs-anchor within each mode
"""
import glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
W, H = 3840, 2160
FPS = {"sol10": 24.0, "whale10": 60.0}
FRAMES = {"sol10": 192, "whale10": 300}
VDP_GRID = {"sol10": "8,24,40,56,72,88,104,120,136,152,168,184",
            "whale10": "12,37,62,87,112,137,162,187,212,237,262,287"}

results = json.load(open("results.json")) if os.path.exists("results.json") else {}


def save():
    cur = json.load(open("results.json")) if os.path.exists("results.json") else {}
    for k, v in results.items():
        cur.setdefault(k, {}).update(v)
    json.dump(cur, open("results.json.tmp", "w"), indent=1)
    os.replace("results.json.tmp", "results.json")


from xpsnr import xpsnr as xpsnr_one

keys = []
for hevc in sorted(glob.glob("*_uzvbv*.hevc")) + sorted(glob.glob("*_uzccrf*.hevc")):
    key = hevc[:-5]
    m = re.match(r"(sol10|whale10)_(\w+?)_(uzvbv|uzccrf)(\d+)$", key)
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
    if "deitp_mean" not in ent:
        out = subprocess.check_output(
            [sys.executable, "deitp.py", f"{clip}.yuv", hevc, str(W), str(H),
             VDP_GRID[clip]])
        ent.update(json.loads(out))
        print(key, "dE-ITP %.4f" % ent["deitp_mean"])
        save()

# ---- 1. rate accuracy (uzvbv only; uzccrf targets are CRF values) ----
print("\nRATE ACCURACY, ABR+VBV arms (deviation from target)")
print(f"{'key':<36}{'target':>8}{'actual':>10}{'dev%':>8}")
for key, clip, cfg, mode, target in keys:
    if mode != "uzvbv":
        continue
    a = results[key]["kbps"]
    print(f"{key:<36}{target:>8}{a:>10.1f}{100*(a-target)/target:>+8.2f}")

# ---- capped-CRF cap compliance ----
print("\nCAPPED-CRF actual bitrates (cap = 1.1x uncapped ultrafast anchor)")
for key, clip, cfg, mode, target in keys:
    if mode != "uzccrf":
        continue
    print(f"{key:<36}{results[key]['kbps']:>10.1f} kbps")

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

print("\nBD-RATE vs anchor per mode (negative = config saves bits at equal quality)")
print(f"{'clip':<9}{'mode':<8}{'config':<9}" + "".join(f"{f:>10}" for f in
      ["psnr_y", "wpsnr_y", "wpsnr_cb", "wpsnr_cr", "xpsnr_y"]))
for clip in ["sol10", "whale10"]:
    for mode in ["uzvbv", "uzccrf"]:
        ks = sorted([k for (k, c, g, m, t) in keys if c == clip and m == mode and g == "anchor"])
        if len(ks) < 4:
            continue
        cfgs = sorted(set(g for (k, c, g, m, t) in keys
                          if c == clip and m == mode and g != "anchor"))
        for cfg in cfgs:
            kt = sorted([k for (k, c, g, m, t) in keys if c == clip and m == mode and g == cfg])
            if len(kt) < 4:
                print(f"{clip:<9}{mode:<8}{cfg:<9} incomplete ({len(kt)} of 4)")
                continue
            row = f"{clip:<9}{mode:<8}{cfg:<9}"
            for f in ["psnr_y", "wpsnr_y", "wpsnr_cb", "wpsnr_cr", "xpsnr_y"]:
                ra = np.array([results[k]["kbps"] for k in ks])
                qa = np.array([results[k][f] for k in ks])
                rt = np.array([results[k]["kbps"] for k in kt])
                qt = np.array([results[k][f] for k in kt])
                row += f"{bd_rate(ra, qa, rt, qt):>+10.2f}"
            print(row)
