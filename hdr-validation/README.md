# HDR tools — metric validation harness

Validates the `HDR`-branch coding tools (`--hdr-pq`, `--hdr-luma-qp`,
`--hdr-scene-qp`, `--hdr-banding-protect`, `--hdr-chroma-qp`,
`--hdr-scaling-list`) against default x265 on **real HDR10 PQ content**,
using the two metrics the project targets: JVET-CTC weighted PSNR (wPSNR)
and HDR-VDP-3.

Results: see [RESULTS.md](RESULTS.md).

## Test material

Real 3840x2160 10-bit 4:2:0 BT.2020 / SMPTE ST 2084 (PQ) sources:

| Segment | Source clip | Frames | fps | Character |
|---|---|---|---|---|
| `sol10` | Netflix Open Content *Sol Levante* (1000-nit master) | 2088–2279 (192) | 24 | Bright anime scene with a hard cut to a dark scene — exercises `hdr-scene-qp` re-baselining |
| `whale10` | Sony *Whale* demo | 100–399 (300) | 60 | Natural bright ocean content, smooth gradients |

The Sol Levante distribution file holds 16-bit samples; the segment is
converted to 10-bit LSB-aligned with ffmpeg before encoding
(`yuv420p16le` → `yuv420p10le`).

## Configurations

CRF sweep {22, 26, 30, 34}, `--preset medium`, single pass:

- **anchor** — default x265 + VUI signalling only
  (`--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited`)
- **hdrluma** — `--hdr-pq --hdr-luma-qp 1.0 --hdr-scene-qp 1.0`
  (the tools that target the luminance metrics being validated)
- **hdrfull** — hdrluma + `--hdr-banding-protect 1.0 --hdr-chroma-qp 1.0 --hdr-scaling-list`
  (adds the three tools that are *by construction* subjective/chroma
  trades and expected to lower luminance metrics)

Single-tool ablations at CRF 22 (48 frames, whale) are reported in
RESULTS.md alongside the sweep.

## Metrics

- **wPSNR** (`wpsnr.py`) — JVET HDR CTC luma-weighted PSNR: per-pixel weight
  `w = 2^(dQP/3)`, `dQP(Y) = clip3(-3, 6, 0.015*Y - 7.5)` on original
  10-bit luma; same-denominator wMSE as VTM's implementation. Chroma
  planes use the 2x2-averaged co-located luma weight.
- **HDR-VDP-3** (v3.0.7, `run_hdrvdp.m`, GNU Octave) — `quality` task,
  reporting mean Q_JOD over 4 evenly spaced frames per encode. Frames are
  converted to linear BT.2020 RGB in absolute cd/m² via the PQ EOTF
  (`prep_frames.py`), center-cropped to 1920x1080 (identically for
  reference and test) to keep CPU runtime tractable; 62 pixels/degree
  (BT.2100 recommended 1.6-picture-heights UHD viewing distance).
- **BD-rate** (`bdrate.py`) — classic Bjøntegaard cubic fit of log-rate vs
  metric over the overlapping quality interval. Negative = bitrate saving
  at equal quality.

## Reproducing

```sh
# 1. extract segments (see README paths) next to these scripts, then:
bash run_encodes.sh          # 24 encodes, resumable
python metrics.py            # wPSNR + HDR-VDP-3 (Octave), resumable -> results.json
python bdrate.py             # BD-rate tables from results.json
```

Requires: the HDR-branch x265 build, ffmpeg, Python 3 + numpy, GNU Octave
(image + statistics packages), and HDR-VDP-3.0.7 unzipped as
`hdrvdp-3.0.7/` (SourceForge; not vendored here — BSD-like research
license, see its `license.txt`).
