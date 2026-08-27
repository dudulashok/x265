"""Metrics + report for the cu-tree diagnostic sweep (run_nct_sweep.sh).

For every finished {clip}_{anchornct|prodmapnct}_crf{crf}.hevc: wPSNR/PSNR,
XPSNR and dE-ITP into results.json (merge-on-write, resumable). Then prints
the three BD-rate views the sweep exists for, using the EXISTING cu-tree-on
medium CRF rows (anchor_crf*, prodmap_crf*) as the other half:
  1. prodmapnct vs anchornct  — the tools' value without cu-tree, at medium
  2. anchornct  vs anchor     — cu-tree's own value on this corpus
  3. prodmapnct vs anchor     — net absolute
  (plus the reference row: prodmap vs anchor, cu-tree on, from stored data)
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

for hevc in sorted(glob.glob("*nct_crf*.hevc")):
    key = hevc[:-5]
    m = re.match(r"(sol10|whale10)_(anchornct|prodmapnct)_crf(\d+)$", key)
    if not m or not os.path.exists(f"{key}.log"):
        continue
    if "encoded" not in open(f"{key}.log").read():
        print("UNFINISHED", key)
        continue
    clip = m.group(1)
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

import numpy as np
from bdrate import bd_rate

FIELDS = ["psnr_y", "wpsnr_y", "wpsnr_cb", "wpsnr_cr", "xpsnr_y"]


def curve(clip, cfg):
    ks = [f"{clip}_{cfg}_crf{c}" for c in (22, 26, 30, 34)]
    if not all(k in results and "wpsnr_y" in results[k] for k in ks):
        return None
    return ks


def bd_row(label, clip, ref_cfg, test_cfg):
    ks, kt = curve(clip, ref_cfg), curve(clip, test_cfg)
    if not ks or not kt:
        print(f"{label:<34} incomplete")
        return
    row = f"{label:<34}"
    for f in FIELDS:
        ra = np.array([results[k]["kbps"] for k in ks])
        qa = np.array([results[k][f] for k in ks])
        rt = np.array([results[k]["kbps"] for k in kt])
        qt = np.array([results[k][f] for k in kt])
        row += f"{bd_rate(ra, qa, rt, qt):>+10.2f}"
    print(row)


print("\nBD-RATE (medium preset, plain CRF; negative = saves bits at equal quality)")
print(f"{'comparison':<34}" + "".join(f"{f:>10}" for f in FIELDS))
for clip in ["sol10", "whale10"]:
    bd_row(f"{clip} prodmap vs anchor (CT ON)", clip, "anchor", "prodmap")
    bd_row(f"{clip} prodmapnct vs anchornct", clip, "anchornct", "prodmapnct")
    bd_row(f"{clip} anchornct vs anchor", clip, "anchor", "anchornct")
    bd_row(f"{clip} prodmapnct vs anchor", clip, "anchor", "prodmapnct")
    print()
