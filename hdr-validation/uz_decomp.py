"""Direct BD-rate of prodmap vs the anchorsao control arm within the
ultrafast+zerolatency modes (2026-08-27): the honest HDR-tools-only read
after removing the SAO confound (--hdr-pq force-enables SAO while the
ultrafast anchor has it off)."""
import json
import numpy as np
from bdrate import bd_rate

res = json.load(open("results.json"))
POINTS = {"uzvbv": {"sol10": [6500, 11500, 20000, 33500],
                    "whale10": [1450, 2300, 3700, 6200]},
          "uzccrf": {"sol10": [22, 26, 30, 34], "whale10": [22, 26, 30, 34]}}
FIELDS = ["psnr_y", "wpsnr_y", "wpsnr_cb", "wpsnr_cr", "xpsnr_y"]

print("BD-RATE prodmap vs anchorsao (HDR tools only, SAO equalized)")
print(f"{'clip':<9}{'mode':<8}" + "".join(f"{f:>10}" for f in FIELDS))
for clip in ["sol10", "whale10"]:
    for mode in ["uzvbv", "uzccrf"]:
        ks = [f"{clip}_anchorsao_{mode}{p}" for p in POINTS[mode][clip]]
        kt = [f"{clip}_prodmap_{mode}{p}" for p in POINTS[mode][clip]]
        row = f"{clip:<9}{mode:<8}"
        for f in FIELDS:
            ra = np.array([res[k]["kbps"] for k in ks])
            qa = np.array([res[k][f] for k in ks])
            rt = np.array([res[k]["kbps"] for k in kt])
            qt = np.array([res[k][f] for k in kt])
            row += f"{bd_rate(ra, qa, rt, qt):>+10.2f}"
        print(row)
