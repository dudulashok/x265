"""Absolute rate-quality tables for the rate-controlled modes (ABR, ABR+VBV,
capped-CRF), in the abs_table.py layout: config rows x rate-point columns,
each cell

    kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | XPSNR-Y | Q_JOD

(Q_JOD from the rate-mode HDR-VDP-3 pass, vdp_evals_modes.sh, 12-frame grid —
"-" until that pass has covered the arm; no dE-ITP column for these modes).
Emits GitHub markdown ready to paste into RESULTS.md. Default arms are the
fix-validation trio; pass config names as arguments to table anything else,
e.g.  python abs_table_modes.py anchor prodmap prodmapfix
"""
import json
import sys

CFGS = sys.argv[1:] or ["anchor", "lumaq05fix", "prodmapfix"]
CLIPS = [("sol10", "Sol Levante (3840x2160p24, frames 2088-2279)"),
         ("whale10", "whale (3840x2160p60, frames 100-399)")]
# mode -> {clip: [rate-point key suffixes]}, column headers derived per clip
MODES = [
    ("ABR (single-pass --bitrate)", "abr",
     {"sol10": [6500, 11500, 20000, 33500], "whale10": [1450, 2300, 3700, 6200]}),
    ("ABR+VBV (--bitrate + vbv-maxrate/bufsize = target)", "vbv",
     {"sol10": [6500, 11500, 20000, 33500], "whale10": [1450, 2300, 3700, 6200]}),
    ("Capped-CRF (--crf + vbv-maxrate = 1.1x anchor bitrate at that CRF)", "ccrf",
     {"sol10": [22, 26, 30, 34], "whale10": [22, 26, 30, 34]}),
]

res = json.load(open("results.json"))

print("kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | XPSNR-Y | Q_JOD\n")
for title, mode, points in MODES:
    print(f"## {title}\n")
    for clip, ctitle in CLIPS:
        print(f"### {ctitle}\n")
        hdr = [f"{'CRF' if mode == 'ccrf' else ''}{p}{'' if mode == 'ccrf' else ' kbps'}"
               for p in points[clip]]
        print("| Config | " + " | ".join(hdr) + " |")
        print("|---|" + "---|" * len(hdr))
        for cfg in CFGS:
            cells = []
            for p in points[clip]:
                e = res.get(f"{clip}_{cfg}_{mode}{p}")
                if not e or "wpsnr_y" not in e:
                    cells.append("-")
                    continue
                xp = ("%.2f" % e["xpsnr_y"]) if "xpsnr_y" in e else "-"
                jod = ("%.2f" % e["vdp_jod"]) if "vdp_jod" in e else "-"
                cells.append(
                    r" \| ".join([f"{e['kbps']:.0f}", f"{e['psnr_y']:.2f}",
                                  f"{e['wpsnr_y']:.2f}", f"{e['wpsnr_cb']:.2f}",
                                  f"{e['wpsnr_cr']:.2f}", xp, jod]))
            print(f"| {cfg} | " + " | ".join(cells) + " |")
        print()
