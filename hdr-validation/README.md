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
| `band10` | synthetic (`gen_band10.py`, deterministic) | 96 | 24 | Gradient-heavy PQ "sunset sky" banding segment: smooth dark-to-mid gradients built in linear light, TPDF-dithered to 10 bits like a real master (source CAMBI ≈ 0; a medium CRF34 encode scores ≈ 3.3). Judged with CAMBI, not wPSNR |

The Sol Levante distribution file holds 16-bit samples; the segment is
converted to 10-bit LSB-aligned with ffmpeg before encoding
(`yuv420p16le` → `yuv420p10le`).

## Configurations and exact commands

CRF sweep {22, 26, 30, 34}, `--preset medium`, single pass. The exact
encode command for every configuration (substitute `$CLIP` = `sol10.yuv`
or `whale10.yuv`, `$FPS` = 24 or 60, `$CRF` = 22/26/30/34):

```sh
# anchor -- default x265 CLI + VUI signalling only (no HDR coding tools)
x265 --input $CLIP --input-res 3840x2160 --fps $FPS --input-depth 10 \
     --preset medium --crf $CRF \
     --colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited \
     -o out.hevc

# hdr10opt -- anchor + x265's existing --hdr10-opt (the fixed JCTVC
#             luma-dQP staircase), the in-tree baseline HDR tool
x265 ... (anchor flags) ... --hdr10-opt -o out.hevc

# hdrluma -- the HDR-branch tools that target the luminance metrics
x265 --input $CLIP --input-res 3840x2160 --fps $FPS --input-depth 10 \
     --preset medium --crf $CRF \
     --hdr-pq --hdr-luma-qp 1.0 --hdr-scene-qp 1.0 -o out.hevc

# hdrfull -- all six HDR-branch tools (adds the subjective/chroma trades)
x265 --input $CLIP --input-res 3840x2160 --fps $FPS --input-depth 10 \
     --preset medium --crf $CRF \
     --hdr-pq --hdr-luma-qp 1.0 --hdr-scene-qp 1.0 \
     --hdr-banding-protect 1.0 --hdr-chroma-qp 1.0 --hdr-scaling-list -o out.hevc
```

(`--hdr-pq` supplies the same VUI signalling as the anchor flags, plus
repeat-headers, SAO and cb/cr QP offsets −2.)

`run_encodes.sh` runs the full sweep and is resumable.

### 2026-08-05 additions

New configs in `run_encodes.sh` / `metrics.py` / `bdrate.py` (hdr10opt and
hdrfull are commented out; their pre-rebase numbers are archived in
`results-2026-08-03-prerebase.json`):

- `hdrpq` — `--hdr-pq` alone, the floor that decomposes the tool sets
- `wsse05/10/15` — `--hdr-pq --hdr-wsse-rd 0.5/1.0/1.5`
- `dbk10` — `--hdr-pq --hdr-deblock 1.0`
- `lumaq025/05/075/10/15` — `--hdr-luma-qp` strength sweep on ANCHOR VUI
  flags (no `--hdr-pq`), measuring the JVET dQP model without the
  chroma-offset floor

### 2026-08-05 (late) additions

- `prodstack` — `--hdr-pq --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5
  --hdr-scene-qp 1.0`, the recommended production stack measured as a unit
- `chromaadapt05/15` — `--hdr-chroma-adapt` strength sweep, sol10 only
  (whale10's chroma share 0.03–0.05 sits below the 0.10 mapping knee, so
  every strength is bit-identical to 1.0 there)
- `band10` configs `bandp05/10` (`--hdr-banding-protect 0.5/1.0`) and
  `slist` (`--hdr-scaling-list`), on ANCHOR flags so the `--hdr-pq` chroma
  offsets don't confound the banding measurement
- `saoband10/30` — `--hdr-sao-band 1.0/3.0` (late-3; needs the X265_BUILD
  222 binary), the SAO banding-repair bias on ANCHOR flags

Segments and encode products are gitignored; re-extract per "Test
material" above (whale: `dd bs=24883200 skip=100 count=300` from the
source yuv; sol: `dd bs=24883200 skip=2088 count=192 | ffmpeg -f rawvideo
-pix_fmt yuv420p16le -s 3840x2160 -i - -pix_fmt yuv420p10le -f rawvideo
sol10.yuv`).

**Long sweeps on this machine**: it thermally throttles after ~1 h of
sustained 4K encoding (encodes go from ~45 s to >10 min) and session/tool
timeouts orphan the running x265. Use `run_sweep_detached.sh` (see its
header for the PowerShell detached-launch line); progress via
`grep -c encoded *.log`, completion via `sweep_done.marker`.

Single-tool ablations at CRF 22 (48 frames, whale) are reported in
RESULTS.md alongside the sweep.

## Exact metric commands

```sh
# wPSNR + PSNR for one encode (prints JSON; frames decoded via ffmpeg pipe)
python wpsnr.py sol10.yuv sol10_anchor_crf22.hevc 3840 2160

# whole sweep -> results.json (bitrates from file size; resumable)
WPSNR_ONLY=1 python metrics.py

# CAMBI (banding, no-reference; libvmaf via ffmpeg -- gyan.dev builds have it)
python cambi.py band10_anchor_crf34.hevc          # one encode
python cambi.py band10.yuv 3840 2160 24           # raw source baseline
# metrics.py runs CAMBI automatically for clips flagged "cambi" (band10)

# HDR-VDP-3: convert 4 sampled frames of source and encode to linear
# BT.2020 RGB (absolute cd/m^2, PQ EOTF), 1080p center crop...
python prep_frames.py yuv  sol10.yuv                  3840 2160 vdp/ref_sol10             24,72,120,168 c1920x1080
python prep_frames.py hevc sol10_anchor_crf22.hevc    3840 2160 vdp/t_sol10_anchor_crf22  24,72,120,168 c1920x1080
# ...then evaluate one pair (Q_JOD on stdout; 62 ppd, quality task):
octave-cli --no-init-file run_hdrvdp.m vdp/t_sol10_anchor_crf22_0024.f32 vdp/ref_sol10_0024.f32 1920 1080

# whole sweep, 4 octave workers, resumable -> vdp_results.txt
bash vdp_evals.sh
python merge_vdp.py        # fold per-frame Q_JODs into results.json

# BD-rate tables (all configs vs anchor)
python bdrate.py

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
- **CAMBI** (`cambi.py`) — Netflix's banding detector, computed by libvmaf
  through ffmpeg's `libvmaf` filter (default options, on the 10-bit decode;
  no-reference). 0 = no banding, ≳5 = clearly visible, scale tops at 24.
  Reported as per-encode mean and p95 over all frames. Not BD-fitted —
  `bdrate.py` prints the raw CAMBI-vs-bitrate table for `band10`.
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
