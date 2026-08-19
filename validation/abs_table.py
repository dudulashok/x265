"""Absolute rate-quality tables: config rows x CRF columns, each cell

    kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | XPSNR-Y

Emits GitHub-markdown (pipes inside cells escaped) ready to paste into
RESULTS.md. Pass config names as arguments:

    python abs_table.py anchor arf1
"""
import json
import sys

CRFS = [22, 26, 30, 34]
CFGS = sys.argv[1:] or ["anchor"]
CLIPS = [("sol10", "Sol Levante (3840x2160p24, frames 2088-2279)"),
         ("whale10", "whale (3840x2160p60, frames 100-399)")]

res = json.load(open("results.json"))

print("kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | XPSNR-Y\n")
for clip, title in CLIPS:
    print(f"### {title}\n")
    print("| Config | " + " | ".join(f"CRF{c}" for c in CRFS) + " |")
    print("|---|" + "---|" * len(CRFS))
    for cfg in CFGS:
        cells = []
        for crf in CRFS:
            e = res.get(f"{clip}_{cfg}_crf{crf}")
            if not e or "wpsnr_y" not in e:
                cells.append("-")
                continue
            xp = ("%.2f" % e["xpsnr_y"]) if "xpsnr_y" in e else "-"
            cells.append(
                r" \| ".join([f"{e['kbps']:.0f}", f"{e['psnr_y']:.2f}",
                              f"{e['wpsnr_y']:.2f}", f"{e['wpsnr_cb']:.2f}",
                              f"{e['wpsnr_cr']:.2f}", xp]))
        print(f"| {cfg} | " + " | ".join(cells) + " |")
    print()
