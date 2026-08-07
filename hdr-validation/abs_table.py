"""Absolute rate-quality tables in the pre-rebase RESULTS.md layout:
config rows x CRF columns, each cell

    kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | Q_JOD

Emits GitHub-markdown (pipes inside cells escaped) ready to paste into
RESULTS.md. Default arms are the three-way comparison; pass config names as
arguments to table anything else, e.g.  python abs_table.py anchor hdrpq prodstack
"""
import json
import sys

CRFS = [22, 26, 30, 34]
CFGS = sys.argv[1:] or ["anchor", "hdr10opt", "prodstack"]
CLIPS = [("sol10", "Sol Levante (3840x2160p24, frames 2088-2279)"),
         ("whale10", "whale (3840x2160p60, frames 100-399)")]

res = json.load(open("results.json"))

print("kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | Q_JOD\n")
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
            jod = ("%.2f" % e["vdp_jod"]) if "vdp_jod" in e else "-"
            cells.append(
                r" \| ".join([f"{e['kbps']:.0f}", f"{e['psnr_y']:.2f}",
                              f"{e['wpsnr_y']:.2f}", f"{e['wpsnr_cb']:.2f}",
                              f"{e['wpsnr_cr']:.2f}", jod]))
        print(f"| {cfg} | " + " | ".join(cells) + " |")
    print()
