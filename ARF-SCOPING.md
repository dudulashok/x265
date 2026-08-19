# Scoping: alt-ref / hidden frames via `pic_output_flag` (AV1-style ARF in HEVC)

2026-08-12. Scoping only — no implementation yet. Everything below was verified
against the tree at `6a9905161` (file:line references are to that commit).

## What is being built

AV1's alt-ref frame: a picture that is **coded and used as a reference but
never displayed**. The reference content is a motion-compensated temporal
average (denoised, stable), so every displayed frame in the group predicts
from a cleaner anchor than any real frame. It is one of AV1's largest
structural advantages over how HEVC encoders are usually driven, and HEVC
*syntax* supports it: the PPS `output_flag_present_flag` gates a per-slice
`pic_output_flag`; a picture with `pic_output_flag=0` is decoded into the DPB
and referenced but never output. Fully Main10-conformant; no decoder changes.

x265 today has **zero** support: `output_flag_present_flag` is hard-coded 0
(`entropy.cpp:648`), nothing models a non-output picture anywhere.

**The key inversion vs MCSTF**: upstream MCSTF already computes exactly the
picture an ARF wants (motion-compensated average over ±range frames,
`TemporalFilter`), but it codes the *filtered* picture as the *displayed*
frame (the original is backed up into `Frame::m_mcstffencPic`,
`encoder.cpp:1995`, then the filter overwrites `m_fencPic`). The viewer sees
filtered video. ARF flips it: the viewer sees the **original**; the filtered
picture becomes a **hidden reference**. Generator exists; only the plumbing
around it is new.

## The five work areas, hardest first

### 1. POC space (the audit — most of the total effort)

HEVC POC is *output order* and must be unique per picture in the DPB, but a
hidden frame representing time N collides with the displayed frame at N. The
standard fix is **POC-space doubling**: displayed frames get coded POC `2n`,
a hidden ARF anchored at frame n gets `2n−1`. MV scaling is safe by
construction — it uses *ratios* of POC deltas (`cudata.cpp:1761/2128`:
colPOC/curPOC differences), and a uniform ×2 cancels; the odd POCs of hidden
frames land *between* displayed frames, which is the temporally correct
distance.

The trap is that x265 uses `m_poc` as the *input frame number* everywhere
(`m_poc = ++m_pocLast`, `encoder.cpp:1760`): rate control (`rce->poc`, the
2-pass stats `in:%d`), lookahead/cu-tree indexing, CSV/stats, SEI user-data
insertion by POC, scenecut history. Therefore: **do not double `Frame::m_poc`**.
Keep it as the input frame number, and introduce a separate coded-order POC
(`m_codedPoc`) consumed ONLY by the bitstream-facing layer:

- slice header `pic_order_cnt_lsb` (`entropy.cpp:1016`)
- RPS construction: `DPB::computeRPS` deltas (`dpb.cpp:399-401`) and
  `Slice::m_refPOCList`
- temporal-MVP colocated POC checks and MV distance scaling (the
  `cudata.cpp` sites — these read `slice->m_poc`; they must read the coded
  POC, all of them, or MV scaling silently degrades ~2x)
- DPB marking/refresh logic that compares POCs (`dpb.cpp:430+`)

`log2MaxPocLsb` is auto-widened from `maxDeltaPOC` (`encoder.cpp:3839`), so
doubling only feeds a larger input to an existing computation.

The audit is: every `m_poc` read in `common/` and `encoder/` classified as
"frame number" (keep) vs "output/coded order" (switch to coded POC). This is
mechanical but broad, and a missed site is a silent quality or conformance
bug. Estimate: the bulk of one session, with `--hidden-arf 0` byte-identity
as the regression gate (with the tool off, codedPoc == 2*poc must NOT be
signalled — keep the old POC signalling entirely when disabled, so the
default path stays bit-exact).

### 2. Frame injection and lifetime

- Inject at GOP/scene heads first (v1): when the lookahead's decided picture
  is an IDR/CRA/scenecut anchor, synthesize a hidden Frame whose `m_fencPic`
  is the MCSTF-filtered anchor, encode it first (P or I, low QP), then encode
  the displayed anchor referencing it. Injection point is the
  `m_lookahead->getDecidedPicture()` → `m_dpb->prepareEncode()` seam in
  `Encoder::encode()` — after slice-typing, before DPB/RPS setup, so the
  lookahead never needs to know hidden frames exist.
- DPB pinning: `computeRPS` (`dpb.cpp:385`) keeps up to `maxDecPicBuffer−1`
  valid referenced pictures by walking the pic list — the ARF must be kept
  while its group lasts (pin it in the walk) and evicted at the next ARF/IDR.
  `sps_max_dec_pic_buffering` needs +1 (`encoder.cpp:3828`).
- Frame accounting: `m_outputCount`, `m_encodedFrameNum`, `--frames`, fps
  math, and the CSV must count displayed frames; NAL output includes hidden.

### 3. Rate control

A frame that costs bits and displays nothing. v1 scope: **single-pass CRF
only** (same restriction as the other HDR-branch tools; refuse 2-pass, VBV,
and analysis save/load with a warning). Budget: code the ARF with the
anchor's QP minus a boost (AV1's arf boost ~ the cu-tree logic's job, but a
fixed `--hidden-arf-qp-offset` is enough to measure the mechanism), and let
the displayed anchor become a cheap P referencing it. The `rce` sequence
gains synthesized entries — keyed by frame number, hidden frames need their
own IDs (negative or offset POCs in RC bookkeeping; contained in
`ratecontrol.cpp`).

### 4. Syntax (trivial)

`output_flag_present_flag=1` in the PPS when the tool is on
(`entropy.cpp:648`); `pic_output_flag` written right after `slice_type`
(`entropy.cpp:1012`, spec order: slice_type → pic_output_flag → POC lsb)
from a per-Slice flag. Cost: 1 bit/slice on every frame while enabled.

### 5. Downstream / API surface (flag now, solve later)

- ffmpeg's HEVC decoder honours `pic_output_flag=0` (drops the frame from
  output) — the recon-vs-decode harness must map recon frames (which include
  hidden) onto decoded output (which excludes them).
- Containers: a hidden frame has DTS but no PTS. Raw Annex-B (our harness
  and the CLI) is unaffected; the libx265 wrapper/MP4 path is out of scope
  for the experiment and must be documented as such.
- HRD/pic-timing SEI with non-output pictures: refuse `--hrd` in v1.

## Staging (each stage independently verifiable)

- **Stage 0 — syntax proof, no POC changes — DONE 2026-08-20, all three
  probes pass.** Temporary env-gated probe (`X265_ARF_STAGE0` in
  `entropy.cpp` `codePPS`/`codeSliceHeader`; default path writes the same
  bits as before — `base.hevc` is unaffected with the variable unset).
  48-frame whale10 encodes, veryfast CRF30, ffmpeg 8.1 `framemd5`:
  (a) *all-1 signalling*: 48 frames out, every per-frame hash identical to
  baseline; overhead exactly 1 bit/slice + the PPS flag (+8 bytes on a
  301,635-byte stream, ~0.003% at 3 Mbps — negligible even at low rate).
  (b) *hide a non-reference b* (`pic_output_flag=0` on TRAIL_N POC 2):
  ffmpeg outputs exactly 47 frames, zero decode errors, remaining 47
  hashes identical to baseline.
  (c) *hide a REFERENCED B* (POC 3, TRAIL_R — the real ARF case, beyond
  the original stage-0 scope): 47 frames out, zero errors, and the b's at
  POC 1/2/4 that predict FROM the hidden picture decode pixel-identical
  to baseline — decoded + referenced + never output, end to end.
  Lesson for later stages: at veryfast the mini-GOP is 5 (P5, B3
  referenced, b1/b2/b4 non-ref) — POC 3 is NOT a TRAIL_N; the probe's
  NAL-type guard caught the wrong first guess. The probe stays in the
  tree until stage 1's real param replaces it.
- **Stage 1 — POC-space doubling** behind the new param, byte-identity when
  off, decode-identity vs pre-change binary when on-but-no-hidden-frames.
- **Stage 2 — ARF injection**: MCSTF-filtered hidden frame at each
  IDR/scenecut anchor + DPB pinning + RC budget. First measurable BD-rate.
- **Stage 3 — tuning**: periodic ARFs inside long GOPs (every 16-32 frames,
  golden-frame-group style), boost sweep, b-pyramid interaction.

## Measurement plan and expectations

Harness as-is: kbps from file size already charges hidden-frame bits to the
displayed duration (correct accounting). Judge with wPSNR/XPSNR BD-rate and
the equal-bitrate view; this is a *coding-efficiency* tool, exactly what the
2026-08-07 re-prioritisation asked for, and unlike LTR it should show up on
ordinary moving content (whale10/sol10 are usable from day one). The clean
win condition for stage 2: BD-rate < −1% on at least one clip with none
worse than +0.3%. Noisy/grainy content is where the denoised-reference
effect is largest — the corpus-expansion item would strengthen the read but
does not block it.

## Params (sketch, full 7-step checklist when implemented)

`--hidden-arf <int>` (0 = off; 1 = ARF at GOP/scene anchors; N>1 reserved
for periodic groups in stage 3) and `--hidden-arf-qp-offset <int>` (default
~ −4, the boost). Not HDR-prefixed — the tool is not PQ-specific. Requires
`--mcstf` machinery (auto-enable the filter path for anchors), single-pass,
no HRD/VBV/analysis-reuse in v1.

## Effort estimate

Stage 0: half a session. Stage 1: 1-2 sessions (the audit dominates).
Stage 2: 1-2 sessions. Total to first BD-rate number: ~3-4 sessions —
consistent with "strongest structural item, large but self-contained" from
the P1 list.
