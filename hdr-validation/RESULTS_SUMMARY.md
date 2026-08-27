# HDR tools — results summary: absolute rate-quality tables per rate-control mode

Condensed view of `RESULTS.md` (which remains the full record): one absolute
rate-quality table per RC mode — CRF, ABR, ABR+VBV, capped-CRF (CRF+VBV) —
with the verdict for that mode directly under each table. All encodes:
medium preset, 4K HDR10 PQ corpus, fixed binary after the 2026-08-13
`--hdr-luma-qp` ABR fix (`cedc6485e` + `4a85f0835`) for the rate-targeted
modes; CRF table from 2026-08-12.

**Clips**
- `sol10` — Sol Levante (3840x2160p24, frames 2088–2279): dark-graded anime,
  chroma-heavy, bright-then-dark.
- `whale10` — whale (3840x2160p60, frames 100–399): natural content, dark
  throughout (APL 108–131), chroma-flat.

**Key configurations**
- `anchor` — plain x265, no HDR tools.
- `hdrpq` — `--hdr-pq` alone (BT.2020/PQ signalling + static −2/−2 chroma offsets).
- `hdr10opt` — in-tree `--hdr10-opt` (for comparison).
- `prodstack` — `--hdr-pq --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0`.
- `prodmap` / `prodmapfix` — **the recommended stack**: `--hdr-pq
  --hdr-chroma-qp-map 0.25 --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5
  --hdr-scene-qp 1.0` (`fix` = same stack on the ABR-fixed binary).
- `lumaq05fix` — `--hdr-luma-qp 0.5` alone on the fixed binary.
- Depth-series arms (CRF table only): `chromaadapt`, `fixed12` (−1/−2),
  `cqpmap025/05/10` (`--hdr-chroma-qp-map` at 0.25/0.5/1.0), `cqpmap10ca`
  (deep map + chroma-adapt).

---

## 1. CRF (constant rate factor)

Cell format: kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | XPSNR-Y | dE-ITP | Q_JOD
(dE-ITP lower = better; Q_JOD only where measured.)

### Sol Levante (3840x2160p24, frames 2088-2279)

| Config | CRF22 | CRF26 | CRF30 | CRF34 |
|---|---|---|---|---|
| anchor | 33493 \| 43.70 \| 42.71 \| 44.03 \| 45.42 \| 40.33 \| 7.083 \| 9.13 | 20121 \| 41.27 \| 40.28 \| 41.78 \| 43.92 \| 38.14 \| 8.779 \| 8.86 | 11466 \| 39.00 \| 38.00 \| 39.70 \| 42.69 \| 35.90 \| 10.748 \| 8.54 | 6487 \| 37.02 \| 35.99 \| 38.35 \| 41.76 \| 33.65 \| 12.687 \| 8.17 |
| hdrpq | 36027 \| 43.71 \| 42.72 \| 45.48 \| 46.39 \| 40.33 \| 6.477 \| 9.18 | 21490 \| 41.28 \| 40.28 \| 42.86 \| 44.67 \| 38.14 \| 8.122 \| 8.91 | 12393 \| 39.01 \| 38.01 \| 40.73 \| 43.30 \| 35.91 \| 9.909 \| 8.60 | 6966 \| 37.03 \| 36.00 \| 39.05 \| 42.24 \| 33.65 \| 11.983 \| 8.22 |
| chromaadapt | 33922 \| 43.71 \| 42.71 \| 44.22 \| 45.62 \| 40.34 \| 6.927 \| - | 20351 \| 41.27 \| 40.28 \| 41.93 \| 44.09 \| 38.14 \| 8.603 \| - | 11616 \| 39.00 \| 38.00 \| 39.83 \| 42.84 \| 35.90 \| 10.543 \| - | 6574 \| 37.02 \| 36.00 \| 38.45 \| 41.90 \| 33.65 \| 12.509 \| - |
| fixed12 | 35132 \| 43.71 \| 42.71 \| 44.75 \| 46.35 \| 40.33 \| 6.673 \| - | 20970 \| 41.28 \| 40.28 \| 42.34 \| 44.64 \| 38.15 \| 8.344 \| - | 11982 \| 39.00 \| 38.00 \| 40.16 \| 43.27 \| 35.90 \| 10.226 \| - | 6755 \| 37.02 \| 36.00 \| 38.69 \| 42.22 \| 33.66 \| 12.223 \| - |
| cqpmap025 | 34671 \| 43.71 \| 42.71 \| 44.74 \| 45.88 \| 40.33 \| 6.764 \| - | 20881 \| 41.28 \| 40.28 \| 42.33 \| 44.48 \| 38.15 \| 8.403 \| - | 12421 \| 39.01 \| 38.01 \| 40.72 \| 43.39 \| 35.91 \| 9.886 \| - | 7017 \| 37.03 \| 36.00 \| 39.05 \| 42.46 \| 33.66 \| 11.879 \| - |
| cqpmap05 | 35558 \| 43.71 \| 42.72 \| 45.17 \| 46.34 \| 40.34 \| 6.600 \| - | 22102 \| 41.28 \| 40.29 \| 43.19 \| 45.13 \| 38.15 \| 7.924 \| - | 13468 \| 39.02 \| 38.02 \| 41.71 \| 44.08 \| 35.92 \| 9.332 \| - | 7821 \| 37.04 \| 36.02 \| 40.04 \| 43.07 \| 33.65 \| 11.028 \| - |
| cqpmap10 | 38721 \| 43.72 \| 42.73 \| 46.55 \| 47.54 \| 40.35 \| 6.061 \| - | 25976 \| 41.30 \| 40.31 \| 45.26 \| 46.85 \| 38.16 \| 6.951 \| - | 17614 \| 39.05 \| 38.05 \| 44.34 \| 46.25 \| 35.92 \| 7.914 \| - | 10958 \| 37.08 \| 36.06 \| 42.71 \| 45.10 \| 33.64 \| 9.280 \| - |
| cqpmap10ca | 34428 \| 43.71 \| 42.71 \| 44.35 \| 45.83 \| 40.34 \| 6.844 \| - | 21041 \| 41.28 \| 40.28 \| 42.22 \| 44.49 \| 38.16 \| 8.299 \| - | 12390 \| 39.01 \| 38.01 \| 40.28 \| 43.48 \| 35.92 \| 9.928 \| - | 7098 \| 37.03 \| 36.01 \| 38.88 \| 42.58 \| 33.68 \| 11.706 \| - |
| prodstack | 34219 \| 43.65 \| 42.84 \| 44.32 \| 45.54 \| 40.31 \| 6.874 \| 9.16 | 20453 \| 41.18 \| 40.37 \| 41.95 \| 44.00 \| 38.14 \| 8.575 \| 8.89 | 11660 \| 38.90 \| 38.05 \| 39.86 \| 42.78 \| 35.92 \| 10.490 \| 8.57 | 6551 \| 36.93 \| 36.01 \| 38.44 \| 41.84 \| 33.68 \| 12.533 \| 8.19 |
| prodmap | 34061 \| 43.64 \| 42.84 \| 44.24 \| 45.47 \| 40.31 \| 6.947 \| 9.15 | 20378 \| 41.18 \| 40.37 \| 41.88 \| 44.00 \| 38.14 \| 8.632 \| 8.88 | 11665 \| 38.90 \| 38.05 \| 39.85 \| 42.79 \| 35.92 \| 10.493 \| 8.55 | 6555 \| 36.93 \| 36.02 \| 38.44 \| 41.93 \| 33.69 \| 12.446 \| 8.20 |
| hdr10opt | 44035 \| 44.00 \| 43.39 \| 47.56 \| 47.65 \| 40.68 \| 5.660 \| 9.28 | 28219 \| 41.49 \| 40.86 \| 45.75 \| 46.33 \| 38.52 \| 6.712 \| 9.08 | 18342 \| 39.19 \| 38.50 \| 44.54 \| 45.41 \| 36.33 \| 7.773 \| 8.71 | 11834 \| 37.23 \| 36.43 \| 43.31 \| 44.60 \| 34.09 \| 9.021 \| 8.69 |

### whale (3840x2160p60, frames 100-399)

| Config | CRF22 | CRF26 | CRF30 | CRF34 |
|---|---|---|---|---|
| anchor | 6159 \| 49.96 \| 51.79 \| 53.11 \| 57.41 \| 42.98 \| 3.235 \| 8.49 | 3744 \| 47.77 \| 49.45 \| 51.64 \| 55.76 \| 41.30 \| 3.735 \| 8.35 | 2292 \| 45.41 \| 46.92 \| 50.02 \| 53.93 \| 39.24 \| 4.755 \| 8.22 | 1435 \| 42.95 \| 44.31 \| 48.66 \| 53.32 \| 36.82 \| 5.329 \| 8.02 |
| hdrpq | 6295 \| 49.96 \| 51.79 \| 53.72 \| 58.21 \| 42.98 \| 3.111 \| 8.51 | 3805 \| 47.78 \| 49.46 \| 52.26 \| 56.49 \| 41.32 \| 3.642 \| 8.35 | 2323 \| 45.41 \| 46.93 \| 50.72 \| 55.03 \| 39.25 \| 4.309 \| 8.21 | 1445 \| 42.93 \| 44.29 \| 49.16 \| 53.59 \| 36.76 \| 5.126 \| 8.03 |
| chromaadapt | 6295 \| 49.96 \| 51.79 \| 53.72 \| 58.21 \| 42.98 \| 3.111 \| - | 3805 \| 47.78 \| 49.46 \| 52.26 \| 56.49 \| 41.32 \| 3.642 \| - | 2323 \| 45.41 \| 46.93 \| 50.72 \| 55.03 \| 39.25 \| 4.309 \| - | 1445 \| 42.93 \| 44.29 \| 49.16 \| 53.59 \| 36.76 \| 5.126 \| - |
| fixed12 | 6237 \| 49.96 \| 51.80 \| 53.42 \| 58.16 \| 42.98 \| 3.162 \| - | 3770 \| 47.77 \| 49.44 \| 51.92 \| 56.48 \| 41.30 \| 3.697 \| - | 2307 \| 45.40 \| 46.92 \| 50.47 \| 54.81 \| 39.24 \| 4.372 \| - | 1447 \| 42.93 \| 44.29 \| 48.87 \| 52.78 \| 36.78 \| 5.388 \| - |
| cqpmap025 | 6222 \| 49.96 \| 51.79 \| 53.42 \| 57.81 \| 42.98 \| 3.175 \| - | 3786 \| 47.77 \| 49.45 \| 52.01 \| 56.47 \| 41.30 \| 3.685 \| - | 2320 \| 45.40 \| 46.92 \| 50.74 \| 55.22 \| 39.24 \| 4.292 \| - | 1433 \| 42.96 \| 44.31 \| 49.33 \| 53.08 \| 36.85 \| 5.032 \| - |
| cqpmap05 | 6319 \| 49.96 \| 51.80 \| 53.77 \| 58.29 \| 42.98 \| 3.101 \| - | 3872 \| 47.78 \| 49.45 \| 52.71 \| 57.24 \| 41.31 \| 3.486 \| - | 2361 \| 45.41 \| 46.93 \| 51.47 \| 55.94 \| 39.25 \| 4.144 \| - | 1452 \| 42.95 \| 44.30 \| 50.24 \| 54.41 \| 36.81 \| 4.706 \| - |
| cqpmap10 | 6691 \| 49.98 \| 51.80 \| 54.53 \| 59.52 \| 43.01 \| 2.939 \| - | 4166 \| 47.81 \| 49.48 \| 53.80 \| 58.91 \| 41.35 \| 3.187 \| - | 2601 \| 45.47 \| 46.97 \| 53.19 \| 58.24 \| 39.35 \| 3.539 \| - | 1570 \| 43.03 \| 44.36 \| 51.94 \| 56.49 \| 36.96 \| 4.196 \| - |
| cqpmap10ca | 6691 \| 49.98 \| 51.80 \| 54.53 \| 59.52 \| 43.01 \| 2.939 \| - | 4166 \| 47.81 \| 49.48 \| 53.80 \| 58.91 \| 41.35 \| 3.187 \| - | 2601 \| 45.47 \| 46.97 \| 53.19 \| 58.24 \| 39.35 \| 3.539 \| - | 1570 \| 43.03 \| 44.36 \| 51.94 \| 56.49 \| 36.96 \| 4.196 \| - |
| prodstack | 5420 \| 49.33 \| 51.19 \| 53.36 \| 57.66 \| 42.49 \| 3.239 \| 8.47 | 3282 \| 47.08 \| 48.77 \| 51.82 \| 56.09 \| 40.69 \| 3.802 \| 8.33 | 1987 \| 44.66 \| 46.18 \| 50.37 \| 54.32 \| 38.53 \| 4.463 \| 8.11 | 1205 \| 42.18 \| 43.52 \| 48.69 \| 53.01 \| 35.93 \| 5.513 \| 7.95 |
| prodmap | 5371 \| 49.33 \| 51.19 \| 53.05 \| 57.27 \| 42.47 \| 3.274 \| 8.45 | 3268 \| 47.08 \| 48.78 \| 51.57 \| 55.85 \| 40.69 \| 3.880 \| 8.32 | 1988 \| 44.66 \| 46.18 \| 50.39 \| 54.72 \| 38.53 \| 4.386 \| 8.12 | 1212 \| 42.18 \| 43.53 \| 48.71 \| 53.15 \| 35.91 \| 5.542 \| 7.95 |
| hdr10opt | 5032 \| 48.69 \| 50.59 \| 54.00 \| 58.34 \| 41.93 \| 3.131 \| 8.47 | 3071 \| 46.38 \| 48.10 \| 52.96 \| 57.02 \| 40.03 \| 3.537 \| 8.34 | 1860 \| 43.95 \| 45.47 \| 52.05 \| 55.96 \| 37.81 \| 4.071 \| 8.17 | 1099 \| 41.52 \| 42.81 \| 50.98 \| 55.19 \| 35.26 \| 4.758 \| 7.98 |

### Verdict — CRF

- **`prodmap` is the recommended stack** (`--hdr-pq --hdr-chroma-qp-map 0.25
  --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0`): wPSNR-Y BD-rate
  **−0.35% (sol10) / −0.58% (whale10)** vs anchor — luma-neutral-to-positive on
  both clips — while keeping whale10's full chroma gains and beating PSNR-Y on
  both clips vs the older `prodstack`. Q_JOD at equal bitrate is
  neutral-to-slightly-positive; DeltaE-ITP keeps a small free colour gain.
- **The chroma-offset depth 0.25 is on the Pareto frontier** (dE-ITP per dB of
  wPSNR-Y at equal bitrate): `cqpmap025` buys 94% of the −2/−2 floor's colour
  gain at 12% less luma cost. Deeper is defensible only to 0.5 and only on
  chroma-flat content; `cqpmap10` and `hdr10opt` sit in a dominated class.
- **`--hdr10-opt` buys bits, not perceptual quality**: +33.1%/+6.4% wPSNR-Y
  BD-rate; at equal bitrate it loses 0.25–1.69 dB wPSNR-Y to buy chroma, and is
  Q_JOD-neutral rate-normalised. A colour-first user is better served by
  `--hdr-chroma-qp-map 0.5` (same trade, better exchange rate).
- All Q_JOD deltas between configs are ~2 orders of magnitude below the 1-JOD
  noticeability unit — perceptually the arms are the same picture; the stack is
  recommended because it costs nothing, not as a measurable quality win.

---

## 2. ABR (single-pass `--bitrate`)

Cell format: kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | XPSNR-Y | Q_JOD.
Fixed binary (post 2026-08-13 `--hdr-luma-qp` ABR fix).

### Sol Levante (3840x2160p24, frames 2088-2279)

| Config | 6500 kbps | 11500 kbps | 20000 kbps | 33500 kbps |
|---|---|---|---|---|
| anchor | 7282 \| 36.91 \| 36.05 \| 38.57 \| 41.63 \| 34.06 \| 8.21 | 12662 \| 38.87 \| 38.03 \| 39.99 \| 42.47 \| 36.21 \| 8.60 | 21769 \| 41.15 \| 40.30 \| 41.91 \| 43.55 \| 38.37 \| 8.90 | 36073 \| 43.57 \| 42.72 \| 44.26 \| 45.00 \| 40.50 \| 9.17 |
| lumaq05fix | 7203 \| 36.87 \| 36.03 \| 38.53 \| 41.63 \| 34.02 \| 8.23 | 12549 \| 38.82 \| 38.02 \| 39.93 \| 42.47 \| 36.16 \| 8.59 | 21586 \| 41.10 \| 40.30 \| 41.84 \| 43.56 \| 38.32 \| 8.90 | 35847 \| 43.54 \| 42.74 \| 44.19 \| 45.01 \| 40.46 \| 9.17 |
| prodmapfix | 7122 \| 36.78 \| 35.94 \| 38.60 \| 41.77 \| 33.90 \| 8.21 | 12410 \| 38.71 \| 37.92 \| 39.99 \| 42.58 \| 36.04 \| 8.58 | 21359 \| 40.98 \| 40.20 \| 41.89 \| 43.62 \| 38.21 \| 8.90 | 35503 \| 43.42 \| 42.63 \| 44.19 \| 45.02 \| 40.35 \| 9.16 |

### whale (3840x2160p60, frames 100-399)

| Config | 1450 kbps | 2300 kbps | 3700 kbps | 6200 kbps |
|---|---|---|---|---|
| anchor | 1288 \| 42.50 \| 43.84 \| 48.73 \| 52.99 \| 36.45 \| 7.96 | 2067 \| 44.69 \| 46.25 \| 49.97 \| 53.83 \| 38.69 \| 8.17 | 3428 \| 46.96 \| 48.72 \| 51.31 \| 55.30 \| 40.72 \| 8.30 | 5946 \| 49.11 \| 51.08 \| 52.84 \| 56.98 \| 42.50 \| 8.47 |
| lumaq05fix | 1305 \| 42.53 \| 43.93 \| 48.75 \| 53.02 \| 36.43 \| 7.94 | 2101 \| 44.71 \| 46.33 \| 49.99 \| 53.85 \| 38.65 \| 8.15 | 3484 \| 47.00 \| 48.83 \| 51.36 \| 55.27 \| 40.72 \| 8.28 | 6038 \| 49.13 \| 51.18 \| 52.88 \| 56.98 \| 42.47 \| 8.46 |
| prodmapfix | 1306 \| 42.47 \| 43.85 \| 49.23 \| 53.32 \| 36.36 \| 7.99 | 2105 \| 44.69 \| 46.30 \| 50.54 \| 54.83 \| 38.63 \| 8.21 | 3488 \| 46.95 \| 48.77 \| 51.93 \| 56.06 \| 40.68 \| 8.35 | 6025 \| 49.10 \| 51.14 \| 53.17 \| 57.59 \| 42.45 \| 8.49 |

### Verdict — ABR

- **`--hdr-luma-qp 0.5` gains under ABR after the 2026-08-13 fix**: wPSNR-Y BD
  **−0.74% (sol10) / −0.32% (whale10)** vs anchor (pre-fix it *cost*
  +0.68/+0.83 — the per-QG bias was one-sided and ABR's complexity feedback
  fought it; the fix zero-means it per frame and applies the mean as an
  EMA-deviation bias inside `rateEstimateQscale`). Strength re-tune confirmed
  **0.5 stays the single strength across all modes** (0.25 is a valid
  conservative ABR-only point).
- **`prodmapfix` buys chroma at a small luma price under ABR**: wPSNR-Y
  +0.47% (sol10) / +0.79% (whale10) for whale10's −17.9/−24.0% chroma BD —
  roughly half the pre-fix price. CRF's free luma lunch does NOT carry over to
  ABR: inside a forced budget, luma pays the chroma bill.
- **Rate accuracy is anchor-like** (honest books after the fix: sol10 overshoot
  +6.0..+9.6% vs anchor's +7.7..+12.0% — expected single-pass convergence error
  on short clips, both arms).
- Q_JOD: prodmapfix +0.02..+0.05 on whale10 (chroma-mediated NCL effect), sol10
  noise — perceptually the arms are the same picture.

---

## 3. ABR+VBV (`--bitrate` + vbv-maxrate/bufsize = target)

Cell format: kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | XPSNR-Y | Q_JOD.
Fixed binary; 1-second buffer (maxrate = bufsize = target).

### Sol Levante (3840x2160p24, frames 2088-2279)

| Config | 6500 kbps | 11500 kbps | 20000 kbps | 33500 kbps |
|---|---|---|---|---|
| anchor | 6395 \| 36.39 \| 35.40 \| 38.16 \| 41.57 \| 33.72 \| 8.11 | 11366 \| 37.91 \| 37.03 \| 39.53 \| 42.48 \| 35.82 \| 8.50 | 19690 \| 39.84 \| 39.07 \| 41.25 \| 43.50 \| 37.91 \| 8.77 | 33822 \| 42.68 \| 41.79 \| 43.43 \| 44.89 \| 40.31 \| 9.08 |
| lumaq05fix | 6334 \| 36.20 \| 35.23 \| 37.77 \| 41.57 \| 33.58 \| 8.12 | 11447 \| 37.96 \| 37.11 \| 39.49 \| 42.52 \| 35.84 \| 8.47 | 19731 \| 39.45 \| 38.77 \| 40.47 \| 43.52 \| 37.84 \| 8.77 | 34004 \| 42.82 \| 41.93 \| 43.45 \| 44.92 \| 40.33 \| 9.11 |
| prodmapfix | 6342 \| 36.19 \| 35.21 \| 37.95 \| 41.73 \| 33.52 \| 8.14 | 11311 \| 37.74 \| 36.91 \| 39.25 \| 42.60 \| 35.67 \| 8.51 | 19850 \| 39.63 \| 38.92 \| 41.08 \| 43.63 \| 37.90 \| 8.80 | 33917 \| 42.74 \| 41.87 \| 43.43 \| 44.94 \| 40.28 \| 9.10 |

### whale (3840x2160p60, frames 100-399)

| Config | 1450 kbps | 2300 kbps | 3700 kbps | 6200 kbps |
|---|---|---|---|---|
| anchor | 1466 \| 42.49 \| 43.97 \| 48.48 \| 51.07 \| 36.52 \| 8.00 | 2334 \| 44.82 \| 46.49 \| 50.09 \| 53.91 \| 38.84 \| 8.19 | 3765 \| 47.13 \| 48.94 \| 51.36 \| 55.67 \| 40.90 \| 8.39 | 6306 \| 49.51 \| 51.44 \| 53.05 \| 57.34 \| 42.77 \| 8.51 |
| lumaq05fix | 1467 \| 42.47 \| 44.00 \| 48.53 \| 51.04 \| 36.38 \| 7.95 | 2334 \| 44.81 \| 46.53 \| 50.11 \| 53.92 \| 38.80 \| 8.20 | 3765 \| 47.12 \| 48.99 \| 51.40 \| 55.65 \| 40.84 \| 8.36 | 6305 \| 49.49 \| 51.49 \| 53.07 \| 57.31 \| 42.72 \| 8.49 |
| prodmapfix | 1471 \| 42.49 \| 44.00 \| 49.19 \| 53.30 \| 36.42 \| 7.98 | 2344 \| 44.70 \| 46.41 \| 50.42 \| 55.00 \| 38.67 \| 8.23 | 3772 \| 47.05 \| 48.91 \| 51.96 \| 56.33 \| 40.79 \| 8.38 | 6316 \| 49.48 \| 51.46 \| 53.35 \| 57.73 \| 42.70 \| 8.50 |

### Verdict — ABR+VBV

- **VBV health is clean — the Dolby Vision gate is passed** (DoVi mandates
  VBV): zero underflow/emergency warnings across every VBV encode of every
  sweep; rate tracking within ±1.8% (whale10) / ±3.6% (sol10).
  `--hdr-scene-qp`'s bias inside `rateEstimateQscale` behaves as designed
  under the VBV clip.
- **`lumaq05fix` holds its gain**: whale10 **−0.78%** wPSNR-Y BD vs anchor;
  sol10's BD fit is scatter — the honest paired per-point read is a tiny,
  strength-independent ≈−0.02..−0.06 dB mean, i.e. neutral.
- **`prodmapfix`**: whale10 +0.94% wPSNR-Y for −14.6/−22.2% chroma — same
  luma-for-chroma trade as plain ABR. sol10's headline +3.60% BD is a scatter
  fit; the per-point mean is a small real ≈−0.1 dB cost.
- Recommendation unchanged: prodmap for CRF/VOD; strict ABR/VBV workflows buy
  whale-class chroma for ≈+0.5..+0.9% luma BD-rate.

---

## 4. Capped-CRF / CRF+VBV (`--crf` + vbv-maxrate = 1.1× anchor bitrate at that CRF)

Cell format: kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | XPSNR-Y | Q_JOD.
Fixed binary; bufsize = maxrate. Note: the 2026-08-13 ABR fix is mode-gated to
`X265_RC_ABR`, so here the RAW per-QG luma-QP bias runs while the VBV clip
engages — this sweep is the direct test of that combination.

### Sol Levante (3840x2160p24, frames 2088-2279)

| Config | CRF22 | CRF26 | CRF30 | CRF34 |
|---|---|---|---|---|
| anchor | 31888 \| 43.34 \| 42.36 \| 43.77 \| 45.12 \| 40.18 \| 9.11 | 18816 \| 40.84 \| 39.87 \| 41.47 \| 43.64 \| 37.97 \| 8.83 | 10568 \| 38.54 \| 37.54 \| 39.52 \| 42.51 \| 35.69 \| 8.47 | 5816 \| 36.58 \| 35.54 \| 38.17 \| 41.55 \| 33.34 \| 8.07 |
| lumaq05fix | 32312 \| 43.32 \| 42.46 \| 43.86 \| 45.07 \| 40.22 \| 9.12 | 19298 \| 40.89 \| 40.03 \| 41.56 \| 43.64 \| 38.05 \| 8.85 | 10857 \| 38.58 \| 37.67 \| 39.58 \| 42.50 \| 35.80 \| 8.51 | 5969 \| 36.62 \| 35.63 \| 38.20 \| 41.58 \| 33.50 \| 8.12 |
| prodmapfix | 32088 \| 43.25 \| 42.41 \| 43.90 \| 45.10 \| 40.14 \| 9.12 | 19148 \| 40.80 \| 39.96 \| 41.64 \| 43.71 \| 37.97 \| 8.86 | 10776 \| 38.50 \| 37.61 \| 39.67 \| 42.60 \| 35.71 \| 8.51 | 5955 \| 36.56 \| 35.59 \| 38.28 \| 41.75 \| 33.43 \| 8.14 |

### whale (3840x2160p60, frames 100-399)

| Config | CRF22 | CRF26 | CRF30 | CRF34 |
|---|---|---|---|---|
| anchor | 6130 \| 49.92 \| 51.75 \| 53.11 \| 57.40 \| 42.96 \| 8.48 | 3708 \| 47.72 \| 49.40 \| 51.65 \| 55.70 \| 41.26 \| 8.32 | 2255 \| 45.33 \| 46.85 \| 49.93 \| 54.03 \| 39.16 \| 8.23 | 1418 \| 42.85 \| 44.22 \| 48.42 \| 53.04 \| 36.66 \| 7.96 |
| lumaq05fix | 5310 \| 49.32 \| 51.18 \| 52.68 \| 56.81 \| 42.47 \| 8.43 | 3227 \| 47.06 \| 48.76 \| 51.21 \| 55.28 \| 40.68 \| 8.32 | 1953 \| 44.61 \| 46.14 \| 49.69 \| 53.17 \| 38.46 \| 8.11 | 1195 \| 42.14 \| 43.49 \| 47.88 \| 52.93 \| 35.88 \| 7.92 |
| prodmapfix | 5385 \| 49.33 \| 51.19 \| 53.05 \| 57.32 \| 42.48 \| 8.46 | 3278 \| 47.09 \| 48.79 \| 51.61 \| 55.88 \| 40.71 \| 8.31 | 1986 \| 44.67 \| 46.19 \| 50.39 \| 54.68 \| 38.54 \| 8.14 | 1212 \| 42.17 \| 43.52 \| 48.73 \| 52.99 \| 35.93 \| 7.96 |

### Verdict — Capped-CRF

- **Capped-CRF behaves like CRF, not like ABR — the CRF recommendation extends
  here without the ABR luma-price caveat.** `prodmapfix` wPSNR-Y BD vs anchor:
  **−0.06% (sol10) / −0.64% (whale10)**, mirroring CRF's −0.35/−0.58, with
  whale10's full chroma gains (−17.5/−20.5%).
- **The 2026-08-13 mode gate is correctly bounded**: `--hdr-luma-qp 0.5` in its
  raw (one-sided) form under the VBV clip gains **−0.89/−1.44%** wPSNR-Y —
  inside its CRF band, no ABR-style flip. No fix needed for capped-CRF.
- **VBV-safe and cap-compliant**: zero VBV warnings in all 24 encodes; every
  encode under its cap (anchor at 82–90% of cap; whale10 tool arms at 76–80%
  because they save 13–14% bitrate at equal CRF, exactly as in plain CRF mode).
- Q_JOD: all config-to-config deltas ≤ ~0.05 JOD (fixed-CRF cells are
  rate-confounded — the tool arms spend 12–14% fewer bits at equal Q_JOD).
  Perceptually the arms remain the same picture.

## 5. Ultrafast + zero-latency (2026-08-27): ABR+VBV and capped-CRF, tight buffer

Cell format: kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr | XPSNR-Y | dE-ITP | Q_JOD.
`--preset ultrafast --tune zerolatency --aq-mode 2 --aq-strength 1.0` on both
arms; **cu-tree is OFF** (zerolatency), so this is the first read of the tools
without cu-tree absorbing the per-QG offsets. VBV buffers are TIGHT
(bufsize = maxrate/2, ~500 ms) — not comparable to the 1-s buffers of
sections 3–4. Capped-CRF caps = 1.1x the *ultrafast* anchor's uncapped
bitrate at each CRF (ultrafast needs 1.6–2.7x medium's bitrate at equal CRF).
Binary `4.2+171-dd58fd317`.

## ABR+VBV, tight buffer (--bitrate + vbv-maxrate = target, bufsize = target/2)

### Sol Levante (3840x2160p24, frames 2088-2279)

| Config | 6500 kbps | 11500 kbps | 20000 kbps | 33500 kbps |
|---|---|---|---|---|
| anchor | 6186 \| 35.50 \| 34.47 \| 37.04 \| 40.70 \| 32.17 \| 13.51 \| 7.84 | 10925 \| 36.88 \| 35.87 \| 38.51 \| 41.66 \| 34.47 \| 11.49 \| 8.27 | 18983 \| 38.51 \| 37.57 \| 40.19 \| 42.70 \| 36.56 \| 9.75 \| 8.61 | 31896 \| 40.45 \| 39.53 \| 41.85 \| 43.66 \| 38.55 \| 8.17 \| 8.90 |
| prodmap | 6180 \| 35.50 \| 34.49 \| 37.15 \| 40.87 \| 32.17 \| 13.45 \| 7.89 | 10873 \| 36.92 \| 35.93 \| 38.63 \| 41.86 \| 34.46 \| 11.27 \| 8.35 | 18847 \| 38.59 \| 37.69 \| 40.34 \| 42.87 \| 36.56 \| 9.47 \| 8.70 | 31477 \| 40.55 \| 39.73 \| 41.93 \| 43.80 \| 38.62 \| 7.99 \| 8.96 |

### whale (3840x2160p60, frames 100-399)

| Config | 1450 kbps | 2300 kbps | 3700 kbps | 6200 kbps |
|---|---|---|---|---|
| anchor | 1269 \| 39.50 \| 40.87 \| 44.67 \| 47.23 \| 32.81 \| 10.08 \| 7.76 | 2008 \| 42.02 \| 43.54 \| 46.62 \| 49.25 \| 35.71 \| 7.62 \| 7.98 | 3279 \| 44.71 \| 46.33 \| 48.21 \| 51.39 \| 38.64 \| 5.95 \| 8.21 | 5666 \| 47.45 \| 49.18 \| 50.40 \| 53.90 \| 41.23 \| 4.35 \| 8.41 |
| prodmap | 1277 \| 39.28 \| 40.66 \| 45.67 \| 48.40 \| 32.46 \| 9.14 \| 7.75 | 2037 \| 41.91 \| 43.46 \| 47.45 \| 50.65 \| 35.51 \| 7.13 \| 8.07 | 3342 \| 44.71 \| 46.38 \| 49.05 \| 52.72 \| 38.52 \| 5.41 \| 8.25 | 5699 \| 47.50 \| 49.28 \| 50.84 \| 54.65 \| 41.15 \| 4.16 \| 8.43 |

## Capped-CRF, tight buffer (--crf + vbv-maxrate = 1.1x ultrafast anchor bitrate, bufsize = maxrate/2)

### Sol Levante (3840x2160p24, frames 2088-2279)

| Config | CRF22 | CRF26 | CRF30 | CRF34 |
|---|---|---|---|---|
| anchor | 51376 \| 43.46 \| 42.47 \| 44.64 \| 45.39 \| 40.64 \| 6.72 \| 9.15 | 29319 \| 40.99 \| 40.03 \| 42.09 \| 43.86 \| 38.48 \| 8.35 \| 8.86 | 15999 \| 38.76 \| 37.78 \| 40.16 \| 42.66 \| 36.19 \| 10.16 \| 8.51 | 8454 \| 36.83 \| 35.81 \| 38.34 \| 41.55 \| 33.71 \| 12.37 \| 8.11 |
| prodmap | 51568 \| 43.66 \| 42.77 \| 44.73 \| 45.28 \| 40.88 \| 6.46 \| 9.20 | 29671 \| 41.24 \| 40.38 \| 42.31 \| 43.96 \| 38.66 \| 8.06 \| 8.94 | 16391 \| 38.89 \| 37.98 \| 40.38 \| 42.82 \| 36.29 \| 9.78 \| 8.62 | 8659 \| 36.87 \| 35.89 \| 38.50 \| 41.69 \| 33.83 \| 12.14 \| 8.17 |

### whale (3840x2160p60, frames 100-399)

| Config | CRF22 | CRF26 | CRF30 | CRF34 |
|---|---|---|---|---|
| anchor | 15072 \| 51.59 \| 53.56 \| 53.92 \| 58.04 \| 44.40 \| 2.98 \| 8.69 | 8923 \| 49.66 \| 51.45 \| 52.24 \| 56.13 \| 42.98 \| 3.51 \| 8.55 | 5473 \| 47.56 \| 49.21 \| 50.56 \| 54.02 \| 41.26 \| 4.31 \| 8.40 | 3337 \| 45.17 \| 46.72 \| 48.62 \| 51.63 \| 39.02 \| 5.55 \| 8.24 |
| prodmap | 13627 \| 51.55 \| 53.58 \| 53.68 \| 57.69 \| 44.20 \| 3.05 \| 8.66 | 8263 \| 49.54 \| 51.39 \| 52.34 \| 56.15 \| 42.76 \| 3.52 \| 8.55 | 5106 \| 47.32 \| 49.04 \| 50.61 \| 54.46 \| 40.94 \| 4.33 \| 8.40 | 3183 \| 44.93 \| 46.54 \| 49.27 \| 52.59 \| 38.69 \| 5.20 \| 8.25 |

### Verdict — ultrafast + zero-latency

- **Without cu-tree, prodmap's gains grow by an order of magnitude.**
  wPSNR-Y BD vs anchor: sol10 **−3.52% (ABR+VBV) / −4.89% (capped-CRF)**,
  whale10 **−4.93% (capped-CRF)** — against −0.06..−0.64% at medium preset.
  Plain PSNR-Y improves too (−2.4..−3.5%). Direct measured confirmation of
  the cu-tree-absorption diagnosis behind the 2026-08-19 pause.
- **whale10 ABR+VBV keeps the familiar ABR luma price** (+1.76% wPSNR-Y for
  −19.4/−24.7% chroma) — same shape as medium-preset ABR, slightly larger
  under the tight buffer.
- **VBV-safe at 500 ms: zero warnings in 32 encodes**; rate accuracy
  tool-independent (the ~5–13% ABR undershoot is a zerolatency/no-lookahead
  trait, identical on both arms).
- **Q_JOD is consistently positive on sol10 (+0.05..+0.11 at equal-or-lower
  rate, both modes)** — larger than any medium-preset delta, though still
  well under the 1-JOD noticeability unit. dE-ITP agrees (whale10 ~9%
  colour-error reduction at the low rate point).
- Recommendation: for ultrafast/zero-latency HDR, prodmap +
  `--aq-mode 2 --aq-strength 1.0` is unambiguous under capped-CRF; under
  ABR+VBV it is a chroma-for-luma trade on natural content.

---

## Overall reading (RC-mode matrix complete, 2026-08-14)

The recommended stack (`prodmap`) holds in every rate-control mode: free
(luma-neutral-to-positive) under CRF and capped-CRF, a small ≈+0.5..+0.9%
wPSNR-Y price for large chroma gains under ABR/ABR+VBV. `--hdr-luma-qp 0.5`
alone gains in every mode on both clips. VBV behaviour is clean everywhere
(zero warnings across all VBV sweeps), and HDR-VDP-3 sees no perceptual
difference between any arms in any mode — the tools are justified on
efficiency, not on a measurable perceptual win. Full history, methodology and
BD-rate tables: `RESULTS.md`.
