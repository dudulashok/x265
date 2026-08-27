"""Absolute rate-quality tables for the ultrafast+zerolatency sweep
(run_uz_sweep.sh): ABR+VBV (uzvbv) and capped-CRF (uzccrf) only, per the
2026-08-27 task scope. abs_table_modes.py layout plus a dE-ITP column:

    kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | XPSNR-Y | dE-ITP | Q_JOD

Q_JOD comes from the vdp_evals_modes.sh pass over the uz keys ("-" until
covered). Emits GitHub markdown ready to paste into RESULTS.md.
"""
import json
import sys

CFGS = sys.argv[1:] or ["anchor", "prodmap"]
CLIPS = [("sol10", "Sol Levante (3840x2160p24, frames 2088-2279)"),
         ("whale10", "whale (3840x2160p60, frames 100-399)")]
MODES = [
    ("ABR+VBV, tight buffer (--bitrate + vbv-maxrate = target, bufsize = target/2)",
     "uzvbv",
     {"sol10": [6500, 11500, 20000, 33500], "whale10": [1450, 2300, 3700, 6200]}),
    ("Capped-CRF, tight buffer (--crf + vbv-maxrate = 1.1x ultrafast anchor bitrate, bufsize = maxrate/2)",
     "uzccrf",
     {"sol10": [22, 26, 30, 34], "whale10": [22, 26, 30, 34]}),
]

res = json.load(open("results.json"))

print("Preset ultrafast + tune zerolatency (cu-tree OFF, lookahead 0, bframes 0,"
      " frame-threads 1) + aq-mode 2 / aq-strength 1.0\n")
print("kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | XPSNR-Y | dE-ITP | Q_JOD\n")
for title, mode, points in MODES:
    print(f"## {title}\n")
    for clip, ctitle in CLIPS:
        print(f"### {ctitle}\n")
        hdr = [f"{'CRF' if mode == 'uzccrf' else ''}{p}{'' if mode == 'uzccrf' else ' kbps'}"
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
                de = ("%.2f" % e["deitp_mean"]) if "deitp_mean" in e else "-"
                jod = ("%.2f" % e["vdp_jod"]) if "vdp_jod" in e else "-"
                cells.append(
                    r" \| ".join([f"{e['kbps']:.0f}", f"{e['psnr_y']:.2f}",
                                  f"{e['wpsnr_y']:.2f}", f"{e['wpsnr_cb']:.2f}",
                                  f"{e['wpsnr_cr']:.2f}", xp, de, jod]))
            print(f"| {cfg} | " + " | ".join(cells) + " |")
        print()
