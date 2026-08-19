# Validation harness — general coding-efficiency tools (branch `efficiency`)

Slimmed 2026-08-19 from the HDR branch's `hdr-validation/` harness: the
PSNR/wPSNR/XPSNR + BD-rate + equal-bitrate machinery only. The perceptual
stack (CAMBI, DeltaE-ITP, HDR-VDP-3/Octave) stays on the HDR branch — if a
tool needs it, measure there. This branch's tools (ARF, TPL, LTR, …) are
judged on **PSNR/wPSNR/XPSNR BD-rate and the equal-bitrate view**.

## Corpus

The source segments live in `hdr-validation/` on this machine (untracked,
kept per the keep-all-test-setups directive — do NOT delete them; the
extraction commands are in `hdr-validation/README.md` on the HDR branch):

| key | file | frames | fps | content |
|---|---|---|---|---|
| `sol10` | `../hdr-validation/sol10.yuv` | 192 | 24 | Sol Levante 2088–2279: dark-graded anime, 4K HDR10 PQ |
| `whale10` | `../hdr-validation/whale10.yuv` | 300 | 60 | natural, dark throughout, 4K HDR10 PQ |

Symlink or copy them here (scripts expect `sol10.yuv` / `whale10.yuv` next
to `metrics.py`), 10-bit LSB-aligned yuv420p10le, 3840x2160.

Known corpus gap (inherited): both clips are single-shot and always-moving.
LTR and shot-level tools need static/repetitive and multi-shot material —
expand before measuring those (Netflix Open Content / CableLabs).

## Encodes

CRF sweep {22, 26, 30, 34}, `--preset medium`, single pass. Anchor:

```sh
x265 --input $CLIP --input-res 3840x2160 --fps $FPS --input-depth 10 \
     --preset medium --crf $CRF \
     --colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited \
     -o {clip}_{cfg}_crf{crf}.hevc 2> {clip}_{cfg}_crf{crf}.log
```

Naming: `{clip}_{cfg}_crf{crf}.hevc` + `.log`; the `.log` must contain
x265's "encoded" completion line before `metrics.py` trusts the encode.
Tool arms add their flags to the anchor command and register the config
name in `metrics.py` `CONFIGS`.

## Metrics

```sh
python metrics.py                    # kbps + PSNR/wPSNR + XPSNR -> results.json (resumable)
python bdrate.py  arf1               # BD-rate vs anchor, all metric columns
python rate_matched.py arf1          # equal-bitrate deltas vs anchor (the decision view)
python abs_table.py anchor arf1      # markdown absolute table for RESULTS.md
```

- `wpsnr.py` — JVET CTC weighted PSNR + plain PSNR (numpy, ffmpeg decode pipe).
- `xpsnr.py` — ffmpeg 8 `xpsnr` filter. **Do not remove the setparams tagging
  of both branches** — ffmpeg 8 negotiates color range/space across filter
  graphs and a silently inserted YUV matrix conversion costs ~7 dB (measured;
  see the docstring).
- ffmpeg: `C:/FFmpeg/bin/ffmpeg` (gyan.dev 8.1+; override with `FFMPEG` env).

## Methodology rules (inherited from the HDR project — don't relearn them)

1. **Decisions read at equal bitrate** (`rate_matched.py`), not from
   fixed-CRF tables (rate-confounded) and not from BD-rate alone.
2. **Baseline arms are measured once**: `anchor` depends on no branch code —
   reuse its rows; re-measure only after a rebase or metric change.
3. **Verify binary provenance on decoded pixels** (`ffmpeg -f md5`), never
   on bitstream bytes — the version SEI repeats at every keyframe. And
   `x265 --version` can be stale: re-run cmake after any feature commit.
4. **Detached runs on this machine**: PowerShell 5.1 `Start-Process` does
   not quote args with spaces — pass a single space-free script path and
   check for surviving orphan children before relaunching.
5. For ARF specifically: recon frames include hidden frames, decoded output
   excludes them — the recon-vs-decode check must map indices accordingly
   (see `ARF-SCOPING.md` §5). kbps from file size already charges
   hidden-frame bits to the displayed duration (correct accounting).
