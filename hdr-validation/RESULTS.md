# HDR tools validation results — real HDR10 PQ content

Date: 2026-08-03 · Encoder: `HDR` branch @ `479426a59` (banding-protect fix
included) · Preset medium, CRF {22, 26, 30, 34}, single pass, 4 configs (incl. --hdr10-opt baseline) ·
Metrics: JVET-CTC wPSNR, HDR-VDP-3.0.7 (Q_JOD, 4 frames/encode,
1920x1080 center crop, 62 ppd). See [README.md](README.md) for setup.

## Rate-quality curves — all metrics, all configurations

![Sol Levante rate-quality curves: wPSNR-Y/Cb/Cr, PSNR-Y and HDR-VDP-3 Q_JOD vs bitrate for anchor, hdr10opt, hdrluma and hdrfull](plots/rd_sol10.png)

![whale rate-quality curves: wPSNR-Y/Cb/Cr, PSNR-Y and HDR-VDP-3 Q_JOD vs bitrate for anchor, hdr10opt, hdrluma and hdrfull](plots/rd_whale10.png)

How to read them: a curve up-and-left of another wins BD-rate. On **whale**,
hdrluma (aqua) sits on top of the anchor (blue) in wPSNR-Y — the −0.8%
BD-rate — while both hdr10-opt (orange) and hdrfull (yellow) fall below.
On **Sol Levante**, hdr10-opt and hdrfull shift right (more bits for the
same luminance quality) but dominate the chroma panels, where hdrluma also
beats the anchor throughout. The Q_JOD panels show all four configs within
a narrow band on Sol Levante (hdr10-opt slightly on top at extra rate).
Regenerate with `python plot_results.py` (matplotlib, reads `results.json`).

## Headline BD-rates vs anchor (negative = bits saved at equal quality)

| Clip | Config | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr |
|---|---|---:|---:|---:|---:|
| Sol Levante | hdr10opt (in-tree) | +42.4% | +33.1% | −56.3% | −49.6% |
| Sol Levante | hdrluma | +15.8% | +7.3% | **−18.7%** | **−12.8%** |
| Sol Levante | hdrfull | +286% | +255% | **−59.3%** | **−51.5%** |
| whale | hdr10opt (in-tree) | +9.0% | +6.4% | −56.3% | −49.4% |
| whale | hdrluma | +1.4% | **−0.8%** | **−21.1%** | **−11.5%** |
| whale | hdrfull | +6.8% | +6.7% | **−35.3%** | **−48.5%** |

### vs x265's existing `--hdr10-opt`

`hdr10opt` = the anchor command + `--hdr10-opt` (the in-tree fixed JCTVC
luma-dQP staircase + slice-level chroma offsets). Compared against it, the
HDR-branch `hdrluma` set achieves its luminance goal far more cheaply:
wPSNR-Y BD-rate +7.3% vs +33.1% (Sol Levante) and **−0.8% vs +6.4%**
(whale). `--hdr10-opt` trades luma for chroma much more aggressively
(−50..−56% chroma wPSNR BD-rate, similar to the six-tool `hdrfull` stack).
On HDR-VDP-3, `hdr10opt` posts the highest Q_JOD per CRF on Sol Levante
(9.31 at CRF22 vs 9.23 hdrluma / 9.18 anchor) but at ~31% more bits; on
whale its Q_JOD tracks slightly below anchor at each CRF at ~18% fewer
bits. In short: the continuous `--hdr-luma-qp` model is a strictly milder,
tunable version of the `--hdr10-opt` trade, and `--hdr-chroma-qp` /
`--hdr-scaling-list` reproduce the aggressive chroma end of it when
explicitly requested.

HDR-VDP-3 BD-rates are not tabulated: with 4 sampled frames per encode the
Q_JOD spread between configs (0.02–0.09 JOD) is within sampling noise and
the Bjøntegaard fit amplifies it into meaningless percentages. Per-CRF
Q_JOD means are in the raw tables below; the consistent observations are:
Sol Levante hdrluma scores **above** anchor at every CRF (+0.03..+0.05
JOD at ~12% more bits); whale hdrluma scores slightly below anchor at
each CRF while spending ~25% fewer bits.

## Reading

- **hdr-pq + hdr-luma-qp + hdr-scene-qp (`hdrluma`)** is roughly
  wPSNR-Y-neutral on natural content (−0.8% on whale, a real if small
  BD-rate win; +7.3% on the anime clip, a loss) and delivers **large,
  consistent chroma wPSNR gains** (−11..−21% BD-rate) from the BT.2020
  chroma QP offsets. The luma-adaptive dQP model redistributes bits
  toward bright regions exactly as the JVET CTC model prescribes; on
  content whose brightness distribution doesn't match the model's
  assumptions (dark anime), it costs luma BD-rate.
- **The full stack (`hdrfull`)** is expensive on luminance metrics *by
  construction* — `--hdr-scaling-list` relaxes high-frequency
  quantization and `--hdr-chroma-qp` moves bits from luma to chroma;
  both are documented as subjective tools. The chroma wPSNR gains are
  correspondingly very large (−35..−59%).
- **`--hdr-scene-qp`** was near-inert (+0.04 dB wPSNR-Y, +1% bits) on
  these steady-state segments, as designed — its trigger is transient
  brightness deviation, which the Sol Levante segment's single hard cut
  correctly re-baselines instead of biasing.

## Single-tool ablation (whale, CRF 22, 48 frames)

| Tool (alone, strength 1.0) | kbps | Δ wPSNR-Y | Δ wPSNR-Cb | Δ wPSNR-Cr |
|---|---:|---:|---:|---:|
| anchor | 6837 | — | — | — |
| --hdr-pq | 7068 | +0.01 | +0.77 | +0.80 |
| --hdr-luma-qp 1.0 | 4977 | −1.96 | −1.36 | −1.41 |
| --hdr-banding-protect 1.0 (fixed) | 4060 | −4.15 | −2.07 | −1.36 |
| --hdr-banding-protect 1.0 (pre-fix) | 8067 | **−16.6** | −5.4 | −1.4 |
| --hdr-scene-qp 1.0 | 6916 | +0.04 | +0.03 | +0.05 |

## Validation caught a real bug

The first sweep produced non-overlapping RD curves: the HDR configs lost
10–16 dB PSNR-Y while spending **more** bits, traced to
`--hdr-banding-protect` multiplying the raw `-log2(acEnergy)` term
(≈ −20 for typical blocks) by the 1.0-vs-0.2 luma-range gate — the gate,
not flatness, dominated the zero-meaned signal, producing per-block QP
offsets of ±60..80. Fixed in `479426a59` by gating the clamped flatness
*deviation* (max ±6 QP at strength 1.0). The pre-fix ablation row above
shows the failure signature.

## Caveats

- Two clips, one segment each (192 / 300 frames). No animation-vs-natural
  generalization should be drawn from n=1 per class.
- HDR-VDP-3 sampled at 4 frames/encode on a 1080p center crop; treat
  Q_JOD deltas < ~0.1 as noise.
- `hdr-scene-qp` needs content with brightness transients (flashes,
  strobes) for a meaningful test; these segments barely exercise it.
- All strengths were 1.0; no strength sweep was performed.

## Raw rate-quality tables

kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | Q_JOD

### Sol Levante (3840x2160p24, frames 2088–2279)

| Config | CRF22 | CRF26 | CRF30 | CRF34 |
|---|---|---|---|---|
| anchor | 33493 \| 43.71 \| 42.71 \| 44.03 \| 45.42 \| 9.18 | 20121 \| 41.27 \| 40.28 \| 41.78 \| 43.92 \| 8.92 | 11466 \| 39.00 \| 38.00 \| 39.70 \| 42.69 \| 8.58 | 6487 \| 37.02 \| 35.99 \| 38.35 \| 41.76 \| 8.20 |
| hdr10opt | 44035 \| 44.01 \| 43.39 \| 47.56 \| 47.66 \| 9.31 | 28219 \| 41.49 \| 40.86 \| 45.75 \| 46.33 \| 9.10 | 18342 \| 39.19 \| 38.50 \| 44.54 \| 45.41 \| 8.83 | 11834 \| 37.23 \| 36.43 \| 43.31 \| 44.60 \| 8.51 |
| hdrluma | 37643 \| 43.62 \| 43.00 \| 45.61 \| 46.29 \| 9.23 | 22467 \| 41.14 \| 40.49 \| 43.03 \| 44.57 \| 8.95 | 12985 \| 38.86 \| 38.15 \| 40.91 \| 43.22 \| 8.63 | 7237 \| 36.92 \| 36.10 \| 39.12 \| 42.16 \| 8.24 |
| hdrfull | 65670 \| 40.22 \| 39.63 \| 50.70 \| 50.14 \| 9.25 | 37600 \| 38.44 \| 37.73 \| 48.49 \| 48.07 \| 8.97 | 21910 \| 36.85 \| 36.01 \| 46.17 \| 46.25 \| 8.62 | 13101 \| 35.48 \| 34.53 \| 43.86 \| 44.79 \| 8.21 |

### whale (3840x2160p60, frames 100–399)

| Config | CRF22 | CRF26 | CRF30 | CRF34 |
|---|---|---|---|---|
| anchor | 6159 \| 49.96 \| 51.79 \| 53.11 \| 57.41 \| 8.47 | 3744 \| 47.77 \| 49.45 \| 51.64 \| 55.76 \| 8.35 | 2292 \| 45.41 \| 46.92 \| 50.02 \| 53.93 \| 8.17 | 1435 \| 42.95 \| 44.31 \| 48.66 \| 53.32 \| 7.97 |
| hdr10opt | 5032 \| 48.69 \| 50.59 \| 54.00 \| 58.34 \| 8.44 | 3071 \| 46.38 \| 48.10 \| 52.96 \| 57.02 \| 8.29 | 1860 \| 43.95 \| 45.47 \| 52.05 \| 55.96 \| 8.10 | 1099 \| 41.52 \| 42.81 \| 50.98 \| 55.19 \| 7.92 |
| hdrluma | 4699 \| 48.63 \| 50.50 \| 52.97 \| 57.04 \| 8.38 | 2831 \| 46.32 \| 48.01 \| 51.39 \| 55.56 \| 8.20 | 1681 \| 43.89 \| 45.39 \| 49.93 \| 52.95 \| 7.97 | 986 \| 41.40 \| 42.71 \| 48.23 \| 52.21 \| 7.89 |
| hdrfull | 2451 \| 45.27 \| 46.80 \| 51.27 \| 55.85 \| 8.32 | 1482 \| 42.96 \| 44.28 \| 50.05 \| 54.68 \| 8.11 | 906 \| 40.70 \| 41.77 \| 48.76 \| 53.43 \| 7.96 | 582 \| 38.62 \| 39.44 \| 47.40 \| 52.24 \| 7.76 |

Raw per-encode numbers: [results.json](results.json) · BD-rates: [bd.json](bd.json)
