"""Render RD-curve figures (all metrics, all configs) from results.json.

Palette: dataviz reference categorical slots 1-4 (validated adjacent order,
light mode). Marker shapes are the secondary encoding; direct labels in the
first panel; full data tables live in RESULTS.md.
"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

res = json.load(open("results.json"))
CRFS = [22, 26, 30, 34]
SURFACE, GRID, BASELINE = "#fcfcfb", "#e1e0d9", "#c3c2b7"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
CONFIGS = [  # fixed categorical order (validated); marker = secondary encoding
    ("anchor",   "anchor (default CLI + VUI)", "#2a78d6", "o"),
    ("hdr10opt", "--hdr10-opt (in-tree)",      "#eb6834", "s"),
    ("hdrluma",  "hdrluma (pq+luma-qp+scene)", "#1baf7a", "^"),
    ("hdrfull",  "hdrfull (all six tools)",    "#eda100", "D"),
]
METRICS = [("wpsnr_y", "wPSNR-Y (dB)"), ("wpsnr_cb", "wPSNR-Cb (dB)"),
           ("wpsnr_cr", "wPSNR-Cr (dB)"), ("psnr_y", "PSNR-Y (dB)"),
           ("vdp_jod", "HDR-VDP-3 Q_JOD")]
CLIPS = [("sol10", "Sol Levante — 3840x2160p24, frames 2088-2279"),
         ("whale10", "whale — 3840x2160p60, frames 100-399")]

def series(clip, cfg, field):
    ks = [f"{clip}_{cfg}_crf{c}" for c in CRFS]
    return ([res[k]["kbps"] / 1000.0 for k in ks], [res[k][field] for k in ks])

for clip, title in CLIPS:
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 7.6), facecolor=SURFACE)
    fig.suptitle(title, x=0.055, ha="left", fontsize=14, fontweight="bold", color=INK)
    fig.text(0.055, 0.945, "Rate-quality curves - CRF 22/26/30/34, preset medium, single pass. Higher is better.",
             fontsize=9.5, color=INK2)
    for i, (field, ylab) in enumerate(METRICS):
        ax = axes[i // 3][i % 3]
        ax.set_facecolor(SURFACE)
        ends = []
        for cfg, label, color, mark in CONFIGS:
            x, y = series(clip, cfg, field)
            ax.plot(x, y, color=color, lw=2, marker=mark, ms=6.5,
                    markerfacecolor=color, markeredgecolor=SURFACE, markeredgewidth=1.2)
            ends.append((x[0], y[0], label.split(" ")[0], color))
        if i == 0:  # direct labels, first panel only; nudge collisions apart
            ends.sort(key=lambda e: e[1])
            ymin, ymax = ax.get_ylim() if False else (min(e[1] for e in ends), max(e[1] for e in ends))
            gap = max((ymax - ymin) * 0.16, 0.1)
            ys = []
            for k, (x0, y0, name, color) in enumerate(ends):
                yl = y0
                if ys and yl - ys[-1] < gap:
                    yl = ys[-1] + gap
                ys.append(yl)
                ax.annotate(name, (x0, y0), xytext=(x0 * 1.06, yl),
                            fontsize=8.5, color=INK2, fontweight="bold", va="center")
            ax.set_xlim(right=ax.get_xlim()[1] * 1.45)
        ax.set_xscale("log")
        ax.set_ylabel(ylab, fontsize=9.5, color=INK2)
        ax.set_xlabel("bitrate (Mb/s, log)", fontsize=9, color=MUTED)
        ticks = [0.5, 1, 2, 5, 10, 20, 50, 100]
        lo, hi = ax.get_xlim()
        ax.set_xticks([t for t in ticks if lo <= t <= hi])
        ax.set_xticklabels([f"{t:g}" for t in ticks if lo <= t <= hi], fontsize=8.5)
        ax.tick_params(colors=MUTED, labelsize=8.5, length=0)
        ax.grid(True, color=GRID, lw=0.8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(BASELINE)
        ax.minorticks_off()
    # legend cell
    ax = axes[1][2]
    ax.axis("off")
    handles = [Line2D([], [], color=c, lw=2, marker=m, ms=7,
                      markerfacecolor=c, markeredgecolor=SURFACE, label=l)
               for _, l, c, m in CONFIGS]
    ax.legend(handles=handles, loc="center left", frameon=False, fontsize=10.5,
              labelcolor=INK, handlelength=2.4, borderaxespad=0)
    fig.tight_layout(rect=(0.02, 0.01, 0.995, 0.93))
    out = f"plots/rd_{clip}.png"
    fig.savefig(out, dpi=170, facecolor=SURFACE)
    print("wrote", out)
