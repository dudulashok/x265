# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

x265 is an open-source HEVC/H.265 video encoder: a C++ library (`libx265`) plus a CLI
front-end (`x265`), dual-licensed under GPL v2 and a commercial license. All code lives
under `source/`; the repository root holds documentation and, under `build/`, one folder of
generator scripts per toolchain.

## Building

CMake, always out-of-tree, always pointed at `source/` (not the repo root).

```sh
cd build/linux
cmake -G "Unix Makefiles" ../../source
make -j"$(nproc)"
```

`build/linux/make-Makefiles.bash` runs cmake then opens the curses config UI. On Windows,
use `build/vc17-x86_64/make-solutions.bat` (or another `build/vc*` folder) to generate
`x265.sln`. Cross-compile toolchain files live in `build/aarch64-linux`,
`build/aarch64-linux-clang`, `build/aarch64-darwin`, `build/riscv64-linux`, `build/arm-linux`,
and `build/msys`.

**NASM 2.13+ must be on `PATH`**, or assembly is silently omitted and the encoder is much
slower. Confirm with `x265 --version`: if it prints `using cpu capabilities: none!`, the
build has no assembly.

### The four configurations CI enforces

A change must build in all of these (`.github/workflows/ci.yml`); 8-bit alone is not enough.

| Config | Extra CMake flags |
|---|---|
| 8-bit (default) | — |
| 10-bit | `-DHIGH_BIT_DEPTH=ON` |
| 12-bit | `-DHIGH_BIT_DEPTH=ON -DMAIN12=ON` |
| multilib | see below |

Multilib builds 10-bit and 12-bit as components with `-DENABLE_CLI=OFF -DEXPORT_C_API=OFF`,
then links them into an 8-bit build:

```sh
cmake ../../../source -DENABLE_SHARED=ON -DENABLE_CLI=ON \
  -DEXTRA_LIB="x265_main10.a;x265_main12.a" -DEXTRA_LINK_FLAGS="-L." \
  -DLINKED_10BIT=ON -DLINKED_12BIT=ON
```

`build/linux/multilib.sh` (and `build/vc17-x86_64/multilib.bat`, `build/msys/multilib.sh`)
automate the whole three-stage sequence.

### Options worth knowing

`ENABLE_ASSEMBLY`, `ENABLE_SHARED`, `ENABLE_CLI`, `ENABLE_TESTS`, `ENABLE_PIC`,
`CHECKED_BUILD` (run-time sanity checks), `ENABLE_AGGRESSIVE_CHECKS` (stack protector,
`-ftrapv`), `WARNINGS_AS_ERRORS`, `DETAILED_CU_STATS` (internal profiling),
`ENABLE_LIBNUMA`, and the HEVC extension gates `ENABLE_ALPHA`, `ENABLE_MULTIVIEW`,
`ENABLE_SCC_EXT`, `ENABLE_HDR10_PLUS`.

## Testing

### TestBench — the primary harness

`TestBench` validates every optimized (SIMD/assembly) primitive against its C reference and
benchmarks it. Configure with `-DENABLE_TESTS=ON`, then:

```sh
./test/TestBench                      # all harnesses, correctness + benchmarks
./test/TestBench --testbench pixel    # one harness (names may be truncated)
./test/TestBench --nobench            # correctness only, no timing
./test/TestBench --cpuid list         # list detected SIMD architectures
./test/TestBench --cpuid avx2         # force an ISA level (must be <= detected)
```

Harness names are `pixel`, `transforms`, `interp`, and `intrapred`
(`source/test/pixelharness.cpp`, `mbdstharness.cpp`, `ipfilterharness.cpp`,
`intrapredharness.cpp`). A new optimized primitive must be added to one of these, and it
must report a match against C for every architecture it targets.

### CLI / regression descriptors

`source/test/*.txt` list encode command lines in the form `clip.y4m,<x265 args>`:
`smoke-tests.txt`, `regression-tests.txt`, `rate-control-tests.txt`, `save-load-tests.txt`,
plus `alpha.txt`, `multiview.txt`, `scc.txt` for the extensions. These are driven by an
external test harness against a clip corpus (bit-exact golden-output comparison). CI
additionally generates `ffmpeg testsrc` clips and sweeps presets, tune modes, rate-control
modes, encoding features, analysis save/load, threading, and 10/12-bit paths.

CI job order, for orientation: Code Quality → Build 8-bit / 10-bit / 12-bit → Build multilib
→ seven parallel functional test jobs → Linux + Windows smoke matrix → summary.

## Code style

`.clang-format` at the root: LLVM base, 4-space indent, no tabs, 120-column limit, Allman
braces. The CI "Code Quality" job checks **only the lines your diff touches** — against
clang-format, and against `cppcheck --enable=warning,performance,portability,style`. It also
flags CRLF line endings, trailing whitespace, tabs, and a missing final newline on changed
lines.

Format just your changes with `git clang-format origin/master`. Do not reformat surrounding
code and never mix whitespace changes with logic changes.

Commit subjects use the area prefixes already in the history: `AArch64:`, `x86:`, `RISC-V:`,
`LoongArch64:`, `CMake:`, `ci:`, `fix:`, `docs:`, `chore:`.

## Changing the public API

Adding an `x265_param` member requires **all seven** steps (see `CONTRIBUTING.md`):

1. Document the member in `source/x265.h`
2. Parse it in `x265_param_parse()` — `source/common/param.cpp`
3. Emit it in `x265_param2string()` — same file
4. Add the `getopt` entry and `--help` text in `source/x265cli.h` and `source/x265cli.cpp`
5. Document the CLI option in `doc/reST/cli.rst`
6. Increment `X265_BUILD` in `source/CMakeLists.txt` (currently `220`)
7. Add coverage to `source/test/smoke-tests.txt` and `source/test/regression-tests.txt`

`X265_BUILD` is the soname / API build number and is pasted textually into the exported
symbol names (`x265_encoder_open_216`, `x265_api_get_216`), so it must move whenever the ABI
does. The same expectations apply to any new or changed public function or struct.

## Architecture

### Bit depth is a compile-time property

`pixel` is `uint8_t` or `uint16_t` depending on `HIGH_BIT_DEPTH` (`source/common/common.h`),
so one build supports exactly one internal depth. To let several coexist in a binary, CMake
sets `X265_NS` — `x265` for the API-exporting build, `x265_8bit` / `x265_10bit` /
`x265_12bit` for linked components (`source/CMakeLists.txt:791`) — and passes the same
`-DX265_NS=` to the assembler. `x265_api_get(bitDepth)` in `source/encoder/api.cpp` selects
the right namespace at run time, falling back to `dlopen`ing `libx265_main10` /
`libx265_main12` when they were not statically linked.

**Consequence:** everything at file scope in `source/common` and `source/encoder` must sit
inside `namespace X265_NS`, and any new asm symbol needs the same prefixing.

### Layers

- `source/x265.cpp`, `source/x265cli.*` — CLI; the only consumer of `input/` (y4m, yuv) and `output/`
- `source/encoder/api.cpp` — public C API shim over the `Encoder` class
- `source/encoder/` — encoder core
- `source/common/` — shared data structures and the C reference primitives
- `source/common/{x86,aarch64,arm,riscv64,loongarch64,ppc,vec}/` — per-architecture SIMD
- `source/dynamicHDR10/` — HDR10+ dynamic metadata (opt-in via `ENABLE_HDR10_PLUS`)

### Encode pipeline

`Encoder::encode()` (`source/encoder/encoder.cpp:1487`) drives:

input picture → **Lookahead** (`slicetype.cpp`; slice-type decision, scenecut, cu-tree,
weighted prediction) → **`DPB::prepareEncode()`** reference-list construction → one of
`m_frameEncoder[]` (up to `X265_MAX_FRAME_THREADS`) → **RateControl** per-frame QP →
`FrameEncoder::compressFrame()` → **CTU analysis** (`Analysis : Search : Predict`;
`compressCTU()` recurses via `compressIntraCU()` / `compressInterCU_rd0_4()` /
`compressInterCU_rd5_6()`) → **Entropy** CABAC coding → **framefilter** deblock + SAO →
`NALList`. `FrameEncoder::getEncodedPicture()` retrieves finished frames in order.

### Threading

`doc/reST/threading.rst` is the canonical write-up. `ThreadPool` allocates one pool per NUMA
node (`ThreadPool::allocThreadPools`); idle workers scan the `JobProvider`s bound to their
pool. Two axes of parallelism compose:

- **Frame-parallel** — several `FrameEncoder`s in flight at once, each a `JobProvider`.
- **Wavefront** — `FrameEncoder : WaveFront, Thread` (`source/encoder/frameencoder.h:179`).
  CTU rows are gated by two dependency bitmaps: *internal* (neighbor block availability) and
  *external* (reference-frame reconstructed pixels). `enqueueRowEncoder` / `enqueueRowFilter`
  interleave the encode and filter passes as rows `row*2+0` and `row*2+1`.

Worker jobs must never block. A job that would block is expected to drop itself so the worker
returns to the pool and finds other work.

### SIMD dispatch

`EncoderPrimitives` (`source/common/primitives.h`) is a large struct of function pointers
indexed by `LumaPU` / `LumaCU` / `ChromaCB` enums. `x265_setup_primitives()`
(`source/common/primitives.cpp:250`) layers them:

```
setupCPrimitives(p) → setupIntrinsicPrimitives(p, cpuid) → setupAssemblyPrimitives(p, cpuid)
```

Each later layer overwrites only the entries whose CPU features are present at run time. To
add an optimized primitive: keep (or add) the C reference, write the kernel in the arch
folder, override the pointer in that arch's `asm-primitives.cpp` behind the correct
CPU-feature guard, and extend the matching `source/test/*harness.cpp` so `TestBench` compares
it against C.

## HDR tools project (branch `HDR`)

The `HDR` branch carries an experimental set of VVC/JVET-inspired HDR coding tools,
implemented strictly inside HEVC-conformant syntax (no decoder changes). Ten `x265_param`
members / CLI options, all documented in `doc/reST/cli.rst`:

- `--hdr-pq` — one-shot BT.2020/PQ VUI signalling + repeat-headers, SAO, chroma QP offsets.
  Note the VUI colour-description defaults are 2 ("unspecified"), so "user did not set it"
  checks must compare against 2, not 0.
- `--hdr-luma-qp <float>` — continuous JVET dQP model (per-QG luma-adaptive QP); requires AQ.
- `--hdr-scaling-list` — PQ-tuned quantization scaling lists (subjective tool; lowers
  PSNR-family metrics by construction).
- `--hdr-chroma-qp <float>` — frame-level chroma QP adaptation from average picture level
  (subjective tool; moves bits from luma to chroma).
- `--hdr-banding-protect <float>` — anti-banding QP protection for flat PQ regions; the
  lookahead pre-pass must re-zero `wp_sum`/`wp_ssd` afterwards because `acEnergyCu()`
  accumulates weightp statistics as a side effect.
- `--hdr-scene-qp <float>` — temporal APL-adaptive QP bias. The bias is computed once per
  frame by `RateControl::updateHdrSceneQpBias()` and applied *inside*
  `rateEstimateQscale()` so qpNoVbv, the VBV clip and the size predictors plan with it;
  single-pass only; the APL rolling average re-baselines at scene cuts.
- `--hdr-wsse-rd <float>` — wSSE-weighted RDO: the JVET wPSNR weight as a per-CTU *lambda*
  scale at `Search::setLambdaFromQP()`, covering mode-decision, ME and RDOQ lambdas
  consistently. Weight cache keyed by (poc, ctuAddr) — never derive it from the passed
  CUData's position/size (slave paths receive sub-CUs). RDOQ scales live on `Quant`, not
  `QpParam` (its setQpParam early-outs on unchanged QP and would go stale).
- `--hdr-deblock <float>` — per-frame slice-header beta/tc deblock overrides from frame
  APL (dark → stronger). The loop filter reads `Slice::m_deblockBeta/TcOffsetDiv2`, which
  are assigned unconditionally every frame in `compressFrame()` (Slice objects are
  recycled via the FrameData free list). Force-disabled with `--no-deblock` — signalling
  overrides without encoder-side filtering would desync encoder and decoder.
- `--hdr-chroma-adapt <float>` — per-frame content-adaptive scaling of the static PPS
  cb/cr QP offsets (the `--hdr-pq` −2/−2), added 2026-08-05 (`862809aed`). The lookahead
  HDR frame-stats scan (`hdrFrameStatsCu`, side-effect-free unlike `acEnergyCu`) measures
  the chroma share of frame AC energy; low share (whale-like smooth natural chroma,
  0.03-0.05) keeps the full offset, high share (sol-like flat-shaded animation, up to
  0.4) cancels it via a positive slice-level delta relative to the PPS offsets. Share
  mapped through [0.10, 0.30]. NOTE the mapping direction: the probe FALSIFIED
  "chroma-rich keeps the offset" — what the offset costs tracks the chroma share of
  residual work, so high share ⇒ cancel. Requires nonzero base offsets and AQ/weightp.
- `--hdr-sao-band <float>` — SAO banding-repair bias, added 2026-08-05 late-3
  (X265_BUILD 222): per-CTU source-variance classifier inside `SAO::rdoSaoUnitCu`
  scales the SAO RD lambda down in banding-prone CTUs so band/edge offsets survive
  their rate cost. Requires SAO; deterministic (source pixels only, no cross-CTU
  state). **Measured negative** (RESULTS.md late-3): engages hard but CAMBI does not
  improve — SAO's per-class constant offsets cannot re-step a plateau inside a
  32-code band, and EO touches only contour pixels. Off-by-default experiment, same
  policy as `--hdr-wsse-rd`.

Metric validation (wPSNR per JVET CTC, HDR-VDP-3 via Octave) against real HDR10 PQ content
lives in `hdr-validation/` on this branch: encode sweep + metric scripts + results
(`README.md` has the exact encode and metric commands; `RESULTS.md` the numbers, including
the `--hdr10-opt` baseline comparison). Local 4K HDR10 source clips are on this machine
under `C:\Videos\HDR\` (the Sol Levante file holds 16-bit samples despite the "10bit"-style
name; convert before use).

**The canonical home for this project is https://github.com/dudulashok/x265-hdr**
(default branch `HDR`). Push further HDR work there (`git push hdrproject HDR`); this
file plus that repo are the reference points for continuing development.

### What the 2026-08 validation established (start from here, don't re-derive)

- `hdrluma` set (`--hdr-pq --hdr-luma-qp --hdr-scene-qp`) is ~wPSNR-Y-neutral on natural
  content (−0.8% BD-rate on whale) but **+7.3% on dark anime** (Sol Levante).
  **2026-08-05 CORRECTION (decomposed with an `--hdr-pq`-alone config): that +7.3% is
  the `--hdr-pq` floor** — its fixed −2/−2 chroma offsets moving bits luma→chroma — not
  the JVET dQP model, which adds only ~+0.2% on Sol Levante and *gains* −2.2% on whale
  relative to the floor. The luma/chroma split is an allocation choice (JVET CTC reports
  Y/Cb/Cr separately); the open item is *adaptive chroma offsets*, not luma re-centering.
  Also: measured APL says whale10 is dark throughout (APL 108–131) and sol10 is
  bright-then-dark — the segment folklore ("bright ocean" / "dark anime") is wrong.
- The same set beats the in-tree `--hdr10-opt` on luminance metrics by a wide margin
  (hdr10-opt: +33.1%/+6.4% wPSNR-Y BD-rate) — the continuous model is the right base.
- Chroma wPSNR gains are large and cheap (−11..−21% BD-rate from `--hdr-pq`'s −2 offsets
  alone). There may be headroom in *adaptive* chroma offsets, but slice-level cb/cr offsets
  are the only HEVC-conformant knob (per-CU chroma QP offsets are a RExt feature).
- `--hdr-banding-protect` and `--hdr-scaling-list` lower PSNR-family metrics *by design*;
  they can only be judged with a banding metric (CAMBI) or subjectively. Neither has been.
- `--hdr-scene-qp` has never been exercised: both test segments are temporally steady.
- HDR-VDP-3 Q_JOD deltas between configs (< 0.1) are inside sampling noise at 4 frames per
  encode — deepen the sampling before trusting it for decisions.
- Per-QG QP offsets flow through `qpAqOffset`/`qpCuTreeOffset`/`invQscaleFactor`
  (`calcAdaptiveQuantFrame`); anything one-sided there corrupts the CRF complexity
  estimate — keep contributions zero-mean (see the banding-protect fix, `479426a59`).
- Only CRF was validated. ABR/VBV paths of `hdr-scene-qp` are plumbed but unmeasured.
- **2026-08-05, `--hdr-wsse-rd` measured: negative.** A pure per-CTU lambda scale
  (quantizer step unchanged) is off-hull and the damage grows with strength — whale
  +1.5/+5.4/+12.1% wPSNR-Y vs the hdrpq floor at strengths 0.5/1.0/1.5 (whale's uniform
  dark APL makes it the clean experiment: uniform lambda-vs-qstep mismatch, no
  redistribution benefit). The QP-domain `--hdr-luma-qp` stays on-hull and delivers what
  the lambda tool intended. Tool kept as an off-by-default experiment; any future wSSE
  work must pair the weight with a matching QP offset or weight mode-decision distortion
  only. Full numbers in `hdr-validation/RESULTS.md` (2026-08-05 section).
- `--hdr-deblock 1.0` is wPSNR-neutral-to-slightly-positive (+0.2 sol / −0.7 whale vs
  floor) with +2..+3 offsets engaged on dark content — no metric harm; value is
  subjective and still needs the HDR-display pass.
- **2026-08-05 bugfixes (round-trip verification found both; recon-vs-ffmpeg-decode is
  the test that catches them — ffmpeg's `trace_headers` bsf desyncs on these streams
  and is NOT reliable ground truth, use the real decoder):**
  (a) `--hdr-pq` at superfast/ultrafast emitted undecodable streams: the bHdrPq block
  forces SAO on AFTER configure()'s selective-sao harmonization has run, leaving
  bEnableSAO=1/selectiveSAO=0 (`3923cec8d`). Medium-preset streams (all sweeps) were
  never affected.
  (b) `hdr-chroma-qp` slice offsets accumulated across recycled Slice objects (only
  the constructor zeroed them; the block ADDS) — drifted −6→−12 pinned, and with the
  PPS −2 the signaled sum hit −14, outside the spec's [−12,12] (`71a593188`). Any
  slice-level chroma-offset writer must reset the fields unconditionally per frame,
  exactly like the hdr-deblock overrides.

### 2026-08-05 session log (items 1+2 of the agreed plan executed — BOTH MEASURED, see
### the RESULTS.md "2026-08-05 (late)" section for full numbers)

1. **`--hdr-luma-qp` strength sweep ran and settled the default: recommend 0.5**
   (0.5–0.75 is a BD-optimal plateau; means across clips −1.41/−1.42% wPSNR-Y; 1.0
   gives most of sol10's gain back, 1.5 reverses). Pure model (no `--hdr-pq`) gains on
   BOTH clips — sol10 −1.31%, whale10 −1.50% at 0.5 — confirming the luma model has no
   dark-content penalty; the old +7.3% was entirely the chroma-offset floor.
2. **Content-adaptive chroma offsets implemented AND validated** as
   `--hdr-chroma-adapt <float>` (`862809aed`, X265_BUILD 221; a new param, not an
   `--hdr-pq` revision, so the floor stays A/B-comparable). Measured at 1.0: sol10
   floor cost **+7.14 → +1.19% wPSNR-Y** (target was < +3%), whale10 numerically
   identical to the plain floor (full −17.5/−22.9 chroma gains kept; share mapping
   held factor 1.0 on every frame as designed). The production stack to try next is
   `--hdr-pq --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0` — unmeasured
   as a unit.
3. **Two pre-existing bugs found and fixed during verification** (details in the
   validation-established section): `--hdr-pq` at superfast/ultrafast produced
   undecodable streams (`3923cec8d`), and `hdr-chroma-qp` slice offsets accumulated
   across recycled Slice objects (`71a593188`).

### 2026-08-05 (late-2) session log — CAMBI harness, banding verdict, prodstack validated

All three priorities from the previous session executed; numbers in RESULTS.md
"2026-08-05 (late-2)".

1. **CAMBI is in the harness** — no new binaries: the local gyan ffmpeg's libvmaf
   computes it (`cambi.py`; metrics.py runs it for clips flagged `cambi`; bdrate.py
   prints the raw table — CAMBI is not BD-fittable and is NOT monotonic with rate).
   Feature options need quote-protection through ffmpeg's filter parser
   (`feature='name=cambi\:opt=val'` as a literal process arg; libvmaf renames the
   output key, e.g. `cambi_mlc_3`).
2. **Banding segment `band10`** (`gen_band10.py`, deterministic): synthetic 4K PQ
   sunset-sky gradients, TPDF-dithered to 10 bits. The dither is the load-bearing
   design choice: undithered, the SOURCE scores CAMBI ~4.0 and encodes score LOWER
   than the source; dithered, source = 0.005 and every encode bands ~3.2-3.7.
3. **`--hdr-banding-protect` measured: fails its design goal, do not enable.**
   +9.15/+22.57% wPSNR-Y BD-rate at strengths 0.5/1.0 on band10 with CAMBI unmoved
   (mean 3.2-3.7 in every config; p95 pinned ~3.8). The decisive control: CRF 12/16
   encodes score CAMBI 3.95/3.86 — HIGHER than CRF 34 and converging on the
   undithered source's 4.0. Banding on this content class is **dither-loss banding**
   (the encoder strips the master's dither at any practical rate; the reconstructed
   smooth gradient bands by itself) — unfixable by QP allocation at any strength,
   which redirects the anti-banding effort to the film-grain/dither-preservation and
   SAO band-offset TODO items. cli.rst updated with a "not recommended" note.
4. **`--hdr-scaling-list` is banding-neutral on pure gradients** (CAMBI unchanged,
   wPSNR ~-0.2%): its high-frequency ramp never engages when everything is DC. Its
   texture-retention case remains subjective-only.
5. **The production stack measured as a unit and validated — recommend it:**
   `--hdr-pq --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0` is
   wPSNR-Y −0.16% (sol10) / −0.26% (whale10) vs anchor — luma-neutral on the clip
   class where the plain floor costs +7.14% — keeping whale10's full chroma gains
   (−19.6/−20.6) and −2.9/−2.4 on sol10. Strictly better than `--hdr-pq` alone on
   every metric column of both clips. cli.rst `--hdr-pq` section now recommends it.
6. **`--hdr-chroma-adapt` strength sweep (sol10 only — whale10 is bit-identical at
   all strengths, share below the 0.10 knee): 1.0 is the knee, keep it.** 0.5 →
   +4.09% wPSNR-Y (too much floor left), 1.5 → +0.71% but chroma residual halves
   again (−1.5/−4.2). Docs updated.

### 2026-08-05 (late-3) session log — `--hdr-sao-band` implemented and measured

The SAO band-offset bias TODO executed same-day (user directive): implemented as
`--hdr-sao-band <float>` (X265_BUILD 222, full 7-step checklist, default path
byte-verified bit-identical), measured on band10 with the new CAMBI harness, and
the verdict is **negative — see the [x] TODO entry and RESULTS.md late-3**. The
one-line takeaway: SAO's operator space (one constant per class) cannot re-step a
banded plateau; combined with the banding-protect result, HEVC-conformant
encoder-side banding repair on dither-loss content is now a closed question —
grain/dither preservation (FGC) or display-side debanding are the only levers left.

### 2026-08-07 session log — three-way HDR-VDP-3 report (default vs hdr10opt vs prodstack)

Closed the last open validation gap: the production stack had never been measured
on HDR-VDP-3 and `--hdr10-opt` had no post-rebase Q_JOD data. Full numbers in
RESULTS.md "2026-08-07" (read the **Addendum** section — it carries the corrected
provenance and the equal-bitrate verdict); report scripts `report_3way.py`,
`rate_matched.py`, `paired_jod.py`, `bootstrap_jod_bd.py`, `verify_binary_identity.sh`
(saved output `report_3way_2026-08-07.txt`).

1. **Verdict: HDR-VDP-3 confirms the wPSNR recommendation, it does not overturn
   it — but "confirms" means "agrees it is free", not "agrees it is better".** The
   production stack (`--hdr-pq --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5
   --hdr-scene-qp 1.0`) is the only arm luma-efficient on BOTH clips (wPSNR-Y
   −0.16% sol10 / −0.26% whale10) and is Q_JOD-neutral-to-slightly-positive. At
   equal bitrate it is luma-neutral with a small free chroma gain — see item 3,
   which is the honest reading of whether the target scores improved.
2. **`--hdr10-opt` buys bits, not perceptual quality**: its significant sol10 Q_JOD
   gain (+0.15…+0.33 JOD) costs **+31…+82% bitrate at the same CRF**; rate-normalised
   it is Q_JOD-neutral (+0.40%) while costing +33.1% wPSNR-Y. On whale it is
   Q_JOD-indistinguishable from default at every CRF while spending ~18–23% fewer bits.
   The production stack dominates it on every luminance column of both clips.
3. **New methodology rule — read the EQUAL-BITRATE deltas (`rate_matched.py`).**
   Fixed-CRF tables are rate-confounded and Q_JOD BD-rate has a CI wider than any
   effect we can measure, which is exactly why the first pass of this report read as
   ambiguous. The decision view interpolates the anchor curve to the config's own
   bitrate and reports the score difference there (Q_JOD per-frame, so the pairing
   and a t-test survive; extrapolated rows flagged). Read at equal bitrate:
   **neither arm significantly improves wPSNR-Y or Q_JOD.** hdr10opt *loses*
   0.25–1.69 dB wPSNR-Y to buy +1.4…+3.5 dB chroma; the production stack is
   luma-neutral (±0.03 dB sol10, 0.00…+0.19 whale10) with a small free chroma gain
   (+0.06…+0.83 dB) and a consistent-but-ns +0.015…+0.021 Q_JOD on sol10. All ΔQ_JOD
   are ~2 orders of magnitude below the 1-JOD noticeability unit — on this corpus the
   three configs are perceptually the same picture. **The production stack is the right
   default because it costs nothing, not because it is a measurable quality win.**
   Consequence: chroma-QP allocation is close to exhausted; raising the target scores
   needs the untried coding-efficiency items (VTM PQ lambda tables / temporal-layer
   QP-lambda cascade are cheapest and measure directly on this harness).
4. **Binary provenance must be VERIFIED, not assumed** (`verify_binary_identity.sh`):
   re-encode one CRF point per arm with the current binary and compare **decoded
   pixels** (`ffmpeg -f md5`). **2026-08-08 CORRECTION: do NOT compare bitstream
   bytes and do NOT use the "first ~400 bytes are SEI" rule** — the version SEI
   repeats at every keyframe, so its second copy sits hundreds of KB in and gets
   mislabelled as coded data. That mistake produced the "coded data differs"
   findings in this item and in the 2026-08-08 rebuild item; both were
   metadata-only. Decoded pixels are the ground truth. The byte-level check is what
   flagged the 2026-08-05 `prodstack` encodes as "not reproducible (10 bytes of coded
   data)", attributed to the later `--hdr-sao-band` change perturbing SAO RD on configs
   that force SAO on. **That attribution is unsupported**: the archived pre-rebuild
   binary (which contains the sao-band change) decodes prodstack to pixels identical to
   both later builds, so for this arm the difference was metadata. Re-encoding changed
   the numbers by ~1e-5 dB wPSNR, i.e. nothing. What DID survive as a real lesson is
   the adjacent one: **`x265 --version` can be stale** (`4.2+119-808cbae9e` while the
   binary contains later code, because cmake had not been re-run), so the version string
   is not evidence of what a binary contains — rebuild via cmake after any feature commit
   to keep it honest.
5. wPSNR reproduced the archived pre-rebase `hdr10opt` numbers (+33.1 / +6.4 wPSNR-Y)
   to two decimals — independent confirmation the re-encoded baseline is consistent.
6. **Toolchain note (user directive): the HDR-VDP-3 setup must stay installed.**
   Octave 11.3.0 (`x265/octave-11.3.0-w64/`) and `hdr-validation/hdrvdp-3.0.7/` had
   both been deleted before this session and cost ~500 MB of re-download; restore
   commands are now in the harness README. `vdp/*.f32` frame dumps are regenerable
   scratch and may be deleted; those two trees may not.
7. **Baseline arms are measured once (user directive)**: `anchor` and `hdr10opt`
   depend on no HDR-branch code — reuse their rows, re-measure only after an upstream
   rebase or a metric-sampling change. Both drivers already skip completed keys.
   `run_hdr10opt_detached.sh` re-creates the hdr10opt arm if a rebase invalidates it.

### Remaining next-session priorities (agreed with user 2026-08-06)

**Anti-banding is CLOSED within this project.** The user decided (2026-08-06) that
banding — measured, documented and pushed through `47b3f77b7`: default x265 bands
visibly on real HDR content (whale10 anchor CAMBI 5.6-7.0 vs source 0.15), and
neither QP nor SAO tools can repair it — will be investigated in a **separate
project** (film-grain/dither-preservation pipeline) after the HDR improvement
feature is finished. Don't pick banding items from the TODO until then; the
CAMBI harness + band10 + the whale10 problem statement are ready when it starts.

**Re-ordered 2026-08-07 (user directive)** after the three-way report showed that
nothing in the current tool set moves luma wPSNR or Q_JOD at equal bitrate — the
allocation knobs are close to exhausted, so the next work must be *coding
efficiency*, not more allocation tuning. `--hdr-scene-qp` is explicitly deferred.

### 2026-08-08 session log — item 0 settled, VTM tools implemented

**Item 0's PREMISE WAS WRONG — the binaries were never differing in coded data.**
Read this before trusting any byte-level provenance claim in this file. x265
emits the version-string SEI **once per keyframe**, so a 300-frame clip at
keyint 250 carries two copies, the second one ~440 KB into the file. The
identity check's heuristic ("differences confined to the first ~400 bytes are
the SEI and cosmetic; deeper differences are real") therefore mislabelled the
*second SEI copy* as coded data. Measured 2026-08-08 with decoded-pixel MD5s:
the archived `4.2+119` pre-rebuild binary, `4.2+128-fb6839767` and
`4.2+131-96275df9c` all decode whale10 prodstack CRF34 to **identical pixels**
(MD5 `66746bc96f163ab24aed7ee14aacd42a`); the only differing bytes are the two
12-byte SEI regions (offsets 136–157 and 438658–438679), and a same-binary
double encode is byte-identical, so nothing is nondeterministic either.
Consequences: the "pre-rebuild binary must have been built from uncommitted
work" theory is unsupported and should not be re-derived; `--hdr-sao-band`
perturbing prodstack's SAO RD (the 2026-08-07 claim) is also unsupported for
this arm; and **provenance must be checked on decoded pixels**
(`ffmpeg -f md5`), which `verify_binary_identity.sh` now does. The re-encode
below was therefore unnecessary — harmless, and it did independently confirm
every number is unchanged, but the cost was avoidable.

**Item 0 is DONE (user chose re-encode).** `hdr10opt` and `prodstack` were
re-encoded on the committed-source binary `4.2+128-fb6839767` (16 encodes,
27 min, `rerun_binary_arms.sh`; old bitstreams kept as `*.hevc.b20260807`,
metric state backed up to `results-2026-08-08-prebinary.json` /
`vdp_results-2026-08-08-prebinary.txt`) and re-measured. **Every re-measured
wPSNR-Y matched the archived value to 4 decimals**, so the 11-byte coded-data
difference is confirmed inconsequential and no conclusion changes — but all
three report arms are now reproducible from the repository, which is what the
VTM comparison needed.

**Reading VTM corrected the premise of item 1 (worth knowing before more work).**
The TODO called for "VTM's PQ-tuned QP-to-lambda and chroma lambda weighting".
VTM has no PQ-specific lambda formula: with `LambdaFromQpEnable` (set in every
JVET CTC config) *every* slice uses λ = 0.57·2^((QP−12)/3) and the temporal-layer
weighting is carried entirely by the QP cascade. What VTM's HDR-PQ CTC actually
does differently (`cfg/per-class/classH1.cfg`) is:
- **signal a PQ chroma QP mapping table** (`QpInValCb/QpOutValCb`) that holds
  chroma QP far below the SDR/HEVC table as QP rises — about −3 QP at qPi 30,
  −5 at 36, −6 at 45. This is where "chroma lambda weighting" really lives: in
  x265 the chroma RD weight is already derived from the effective chroma QP
  (`RDCost::setQP`), so reproducing the QP gets the lambda for free.
- **LMCS with `LMCSSignalType=1`** — decoder-normative, not available in HEVC.
- **luma-adaptive dQP OFF** (`LumaLevelToDeltaQPMode: 0`); instead the JCTVC-X1020
  luma weight LUT is applied as a **per-pixel distortion weight** in RDO
  (`RdCost::initLumaLevelToWeightTable`, weight = 2^(clip(−3,6,0.015·Y−7.5)/3)).
  That is the same weight `--hdr-wsse-rd` used, but VTM applies it to the
  *distortion* at pixel granularity with lambda untouched — i.e. exactly
  candidate fix (b) of the wsse post-mortem, at a granularity our per-CTU
  lambda scale never had.

Three tools implemented today (X265_BUILD 225, all default-off, full 7-step
checklist, docs in cli.rst):
1. `--hdr-qp-cascade <float>` — the JCTVC-X0038 QP-offset model VTM uses in its
   random-access GOP table, as an extra hierarchical-B increment on top of
   x265's fixed `6·log2(pbratio)` cascade: `clip(0, 3, 0.22·q − 4.95)`, full on
   non-referenced B, half on referenced, and symmetrically undone in the
   reference-QP interpolation so it stays in P-level QP space. Nothing below
   QP ≈22, up to +3 QP at high QP. Applied inside `rateEstimateQscale` so
   qpNoVbv/VBV/predictors plan with it (same rule as `--hdr-scene-qp`).
   Single-pass only.
2. `--hdr-vtm-lambda <float>` — log-domain blend of x265's QP→lambda mapping
   toward VTM's. x265's λ2 is 10% higher at QP 12 rising to 21% higher at QP 42,
   with a slightly steeper slope. Implemented by rewriting the process-global
   lambda tables at `Encoder::configure` (the mechanism `--lambda-file` already
   uses, and an explicit `--lambda-file` still wins), with a pristine snapshot
   so repeated `encoder_open` calls assign rather than compound. This also
   *is* the "pure global lambda scale, quantizer untouched" arm the wsse
   post-mortem wanted — but consistent across RDO/ME/RDOQ/SAO/lookahead
   instead of per-CTU.
3. `--hdr-chroma-qp-map <float>` — VTM's HDR-PQ chroma QP mapping reproduced
   with slice-level offsets: for the frame's slice QP, pick the offset whose
   HEVC-table lookup lands nearest the VVC table's output, separately for Cb
   and Cr. It *assigns* the total PPS+slice offset (replacing `--hdr-pq`'s
   static −2/−2) and `--hdr-chroma-adapt` now scales whatever total is in
   place, so the two compose — deliberately, because the VVC table is
   content-blind and its full depth is deep: **Cb −5/Cr −7 at QP 32, Cb −9/Cr
   −12 at QP 40**. Expect a large chroma gain and a real luma cost on
   chroma-heavy content; the composition with chroma-adapt is the interesting
   arm. (`--hdr-chroma-adapt` with the map off is bit-identical to before.)

Sweep queued as `run_vtm_sweep.sh`: `cascade05/10/15`, `vtmlam05/10` on ANCHOR
flags (both are coding-efficiency models, so the chroma floor would only
confound the luma reading), wPSNR + BD-rate only — Q_JOD is reserved for
whichever arm wins, per the 2026-08-07 methodology rule.

0. **DONE 2026-08-08 — see the session log above. (2026-08-08 rebuild finding.)** cmake was re-run and
   the tree rebuilt at `fb6839767`, so the binary now reports `4.2+128-fb6839767`
   (build 222, assembly intact, deterministic) — the stale-version trap is fixed.
   But the rebuild is **not** coding-identical to the binary that produced the
   published encodes: the anchor matches byte-for-byte (SEI aside) while `hdr10opt`
   and `prodstack` each differ by 11 bytes of coded data. The tree was clean with no
   code commits after `e166ea110`, so the pre-rebuild binary must have been built
   from **uncommitted intermediate work** — i.e. from source that is not in the
   repository. Impact on numbers is nil (~1e-5 dB wPSNR, <0.001 Q_JOD, same as the
   earlier equivalent perturbation), so no conclusion changes, and the old binary is
   archived at `hdr-validation/bin-archive/x265-4.2+119-808cbae9e-prerebuild.exe` so
   the published bitstreams stay reproducible. Decide before the VTM work starts:
   re-encode `hdr10opt` + `prodstack` on the current binary (16 encodes + metrics,
   ~2.5 h) so the baseline is reproducible from source, or accept the archived
   binary as the reference. Recommended: re-encode, since the VTM lambda experiment
   will be compared against exactly these arms. Worth also identifying *what*
   differs — both affected configs manipulate chroma QP offsets while the plain
   anchor does not.
1. **DONE 2026-08-08 — VTM HDR lambda tables, all three pieces implemented and
   measured (X265_BUILD 225).** Verdicts (full tables in RESULTS.md "2026-08-08
   verdicts"): `--hdr-qp-cascade` **negative and monotone in strength** (+1.3…+5.6%
   sol10, +0.3…+7.7% whale10 wPSNR-Y) — under CRF, coarsening the unreferenced
   layer only removes bits, there is no reallocation to referenced frames, so
   x265's shallow spread is already better; don't pursue. `--hdr-vtm-lambda`
   **neutral** (−0.5% whale10 … +0.96% sol10 at strength 1.0) — x265's empirical
   lambda is already at the hull, and this **closes the wsse post-mortem**: a
   global, consistent lambda change costs nothing while the per-CTU one cost
   +1.5…+12.1%, so the damage was the per-block *inconsistency*, not the
   lambda-vs-quantizer decoupling per se. `--hdr-chroma-qp-map` at full strength
   is far too deep (+37.6% sol10 / +10.8% whale10 luma for −56…−68% chroma, i.e.
   `--hdr10-opt`'s class), but **at 0.25 it is a small Pareto win over the fixed
   −2/−2 floor on both clips** (luma 5.49 vs 7.14 sol10, 0.96 vs 1.37 whale10,
   with Cr *better*). `--hdr-chroma-adapt` moderates the deep map exactly as
   designed (sol10 +37.6 → +5.8) but the moderated point does not dominate
   cqpmap025 — not going too deep beats scaling back a too-deep offset.
   **The two deciding arms also ran (2026-08-08 23:47, `run_cqpmap_followup.sh`).**
   `fixed12` (a fixed −1/−2) has the LOWEST absolute luma cost (+4.22 sol10 /
   +0.87 whale10 vs the ramp's +5.49/+0.96), so **the ramp's win over the −2/−2
   floor was mostly DEPTH, not shape**. What the ramp adds is a better exchange
   rate — luma saved per point of Cb given up, relative to the floor, is 0.37 vs
   0.30 (sol10) and 0.19 vs 0.07 (whale10) — and on whale10 it *keeps* Cr
   (−23.56, better than the floor) where the fixed offset loses 4.8 points of it.
   Real, but second-order next to choosing the right depth.
   **`prodmap` is the new recommended stack:** `--hdr-pq --hdr-chroma-qp-map 0.25
   --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0` gives wPSNR-Y
   **−0.35% (sol10) / −0.58% (whale10)** against prodstack's −0.16%/−0.26%, PSNR-Y
   better on both, for 2.9 points of whale10 Cb (partly returned as Cr). First
   improvement to the recommended configuration since 2026-08-05. **RESOLVED
   2026-08-11: Q_JOD on `prodmap` measured — neutral at equal bitrate, same
   shape as prodstack; cli.rst now recommends prodmap** (see the 2026-08-11
   session log).
2. **LARGELY ANSWERED 2026-08-08 by `--hdr-vtm-lambda` (see item 1), and VTM
   shows the fix.** The global-lambda arm is neutral while the per-CTU arm cost
   +1.5…+12.1%, so the mechanism is per-block *inconsistency*, not
   lambda-vs-quantizer decoupling. And VTM's own HDR RDO is the remaining
   candidate: it applies the JCTVC-X1020 luma weight as a **per-pixel distortion
   weight** (`RdCost::initLumaLevelToWeightTable`, w = 2^(clip(−3,6,0.015·Y−7.5)/3))
   with lambda untouched and `LumaLevelToDeltaQPMode: 0`. That is candidate fix
   (b) at pixel granularity — the design is now concrete rather than
   hypothetical; the cost is weighted-SSE distortion kernels (a new cost flavor,
   the design previously rejected as invasive). Original note kept for context:
   post-mortem on why `--hdr-wsse-rd` does not help. Measured
   negative 2026-08-05 (whale +1.5/+5.4/+12.1% wPSNR-Y at 0.5/1.0/1.5, damage
   growing with strength). Working diagnosis to test, not assume: RD optimality
   needs lambda to equal the local −dD/dR *of the quantizer actually in use*, so
   scaling lambda while leaving the quantizer step untouched selects points off the
   convex hull, and the mismatch grows with the scale factor — which matches the
   monotone-with-strength damage. Whale is the clean case (uniform dark APL ⇒
   uniform mismatch, no redistribution benefit to mask it). Two candidate fixes to
   evaluate: (a) convert the wSSE weight into a matching **QP offset** so lambda and
   quantizer step move together — this is what `--hdr-luma-qp` already does, and it
   stays on-hull, which is itself evidence for the diagnosis; (b) apply the weight
   **only to the distortion term in mode decision**, leaving RDOQ and ME lambdas
   consistent with the quantizer. Worth confirming the mechanism before writing
   code — a cheap diagnostic is to sweep a pure QP-offset tool and a pure
   lambda-scale tool to the same average rate and compare hull positions.
3. **DONE 2026-08-12 — subjective HDR-display pass complete: no artifacts** in
   `--hdr-deblock` or `--hdr-scaling-list`; both kept as optional features
   (cli.rst updated).
4. **Deferred: exercise `--hdr-scene-qp`** (transient-rich segment; the only tool in
   the production stack never exercised by the corpus; needs a
   rate-control-tests.txt descriptor and the ABR/VBV paths checked). Still on the
   list, just not next.
5. **DONE 2026-08-12 — measured MaxCLL/MaxFALL → CLL SEI** implemented as
   `--hdr-measured-cll` (see the 2026-08-12 session log).

**Decomposition COMPLETE (2026-08-08, 480 evals, 0 failures)** — full table in
RESULTS.md, "Decomposition result". The `--hdr-chroma-adapt` hypothesis is
**falsified**: `prodstack` rate-matched ΔQ_JOD (+0.015…+0.021 on sol10) matches or
exceeds the `hdrpq` floor it is built on at every CRF, and is indistinguishable
from `hdrluma`. Two further findings worth carrying forward:
- **The entire Q_JOD effect comes from the chroma offsets; the luma tools add
  nothing measurable.** `hdrpq` alone (luma QP untouched) reproduces the whole
  gain and is the *only* arm reaching significance (p<0.05 at 3 of 4 CRFs, sem
  0.004–0.007 vs 0.021–0.040 for the luma arms — exactly what you expect when
  luma is untouched). `--hdr-luma-qp` at either 1.0 or 0.5 moves the Q_JOD mean by
  nothing while inflating variance.
- **That gain is chroma-mediated via non-constant-luminance leakage**, confirmed
  by a sign disagreement: at matched rate `hdrpq` is *worse* on luma (ΔwPSNR-Y
  −0.24…−0.34) yet *better* on Q_JOD. A metric with no chromatic channel can only
  do that if improved chroma reduces luminance error through the NCL matrix.
All of it sits at +0.015…+0.02 JOD, ~2 orders of magnitude below the 1-JOD
noticeability unit — so HDR-VDP-3's only measurable response to this tool set is a
chroma side-effect, not the luma work the tools were built to do. Further argument
for moving to coding-efficiency levers rather than allocation tuning.

### 2026-08-11 session log — prodmap Q_JOD gate passed (recommendation flipped),
### XPSNR + DeltaE-ITP in the harness (both P0 metric items)

1. **prodmap is the recommended stack, now with the Q_JOD gate passed.** The
   96-eval HDR-VDP-3 pass on the existing prodmap encodes (0 failures, 12/12
   frames per key) read at equal bitrate per the 2026-08-07 rule: sol10
   consistently positive-but-ns (+0.008…+0.019 JOD, prodstack band), whale10
   noise around zero with the same CRF-30 dip prodstack has. The paired
   fixed-CRF whale10 negatives (−0.098** at CRF30) coincide with 13–16%
   bitrate savings — the rate confound, same as prodstack. cli.rst flipped to
   recommend `--hdr-pq --hdr-chroma-qp-map 0.25 --hdr-chroma-adapt 1.0
   --hdr-luma-qp 0.5 --hdr-scene-qp 1.0`. Full table in RESULTS.md 2026-08-11.
2. **XPSNR in the harness** (P0 item 1) and it *agrees* with wPSNR on every
   standing verdict — see the [x] TODO entry; the load-bearing find is the
   ffmpeg-8 filter-graph colorspace-negotiation trap (setparams both branches,
   documented in xpsnr.py/README/RESULTS.md).
3. **DeltaE-ITP in the harness** (P0 item 2, `deitp.py`) — validated, wired
   into metrics.py for chroma-relevant arms on the Q_JOD-pairable 12-frame
   grid; backfill and the first chroma read are the open half.
4. Methodology note for whoever reads reports next: `rate_matched.py` now has
   dXP-Y/Cb/Cr columns; `bdrate.py` fits XPSNR BD-rates; metrics.py save() is
   merge-on-write so concurrent metric passes don't clobber results.json.

### 2026-08-12 session log — depth-series Pareto read (prodmap depth confirmed),
### subjective pass closed

1. **The cqpmap depth series read as a luma-vs-colour Pareto curve
   (`pareto_deitp.py`, RESULTS.md 2026-08-12): prodmap's 0.25 depth is ON
   the frontier — no change to the recommendation.** The exchange rate
   (dDEITP per dB of wPSNR-Y at equal bitrate) is concave in depth on both
   clips: sol10 ~2.9 → 1.84 (at 0.25) → 0.84 (full ramp); whale10 4.18 at
   0.25. cqpmap025 buys 94% of the −2/−2 floor's colour gain at 12% less
   luma cost. Deeper is defensible only to 0.5 and only on chroma-flat
   content; cqpmap10 and hdr10opt sit in a dominated class (~0.85–0.95
   dE/dB on sol10). A colour-first user should take `--hdr-chroma-qp-map
   0.5` over `--hdr10-opt` — same trade, better exchange rate. Also
   re-confirmed in dE terms: "don't go too deep" beats "go deep and scale
   back with chroma-adapt" corpus-wide (cqpmap10ca engages only on sol10).
2. **Absolute rate-quality table regenerated with the new metric columns**
   (`abs_table.py` now emits kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr
   | XPSNR-Y | dE-ITP | Q_JOD; saved `abs_table_2026-08-12.txt`, pasted in
   RESULTS.md). `rate_matched.py` now takes arm names as argv.
3. **Subjective HDR-display pass closed (user, 2026-08-12): no artifacts
   in `--hdr-deblock` or `--hdr-scaling-list`** — both kept as optional
   off-by-default features; cli.rst notes updated. Closes the last open
   item on both tools.
4. **Measured MaxCLL/MaxFALL → CLL SEI implemented** as
   `--hdr-measured-cll` (X265_BUILD 226, full 7-step checklist). Pass 1
   scans every source frame for the CTA-861.3 definition — per-pixel
   max(R,G,B) in linear light (BT.2020 NCL matrix; PQ EOTF is monotonic so
   only the per-pixel max needs it, via a 1024-entry lerp'd LUT in
   `PicYuv::copyFromPicture`) — and appends a `#cll:CLL,FALL` trailer to
   the stats file (after the last `;`, invisible to old parsers); pass 2
   parses it in `RateControl::init` (which runs before headers) and fills
   `maxCLL/maxFALL` + `bEmitHDR10SEI`; explicit `--max-cll` wins.
   Single-pass measures and logs only (the SEI precedes frame 0).
   Verified: measured values match an independent full-precision numpy
   reference exactly on 48 whale10 frames (MaxCLL 10000 — the clip really
   has clipped speculars — MaxFALL 52); SEI present in pass-2 stream and
   absent in pass 1 (ffprobe); `--max-cll 1000,100` precedence honored;
   default path decodes pixel-identical to the archived pre-rebuild
   binary. NOTE the luma-code-level `m_analyzeAll` CSV stats path is
   untouched and still underestimates saturated colors — only the new
   param uses the linear-light definition.
5. **ARF (`pic_output_flag`) scoped, then deferred** (user directive): full
   plan in `hdr-validation/ARF-SCOPING.md`; start there next time.
6. **ABR / ABR+VBV validation DONE (same day — sweep + metrics + verdict in
   RESULTS.md "2026-08-12 late").** The one-line verdict: **VBV-safe and
   rate-accurate, but CRF's free luma lunch does not carry over** — under
   ABR/VBV prodmap trades +1.5..+2.0% wPSNR-Y BD for whale10's −15..−24%
   chroma (sol10 VBV the one neutral cell, −0.13%). Zero VBV warnings in 16
   VBV encodes (`--hdr-scene-qp`'s rateEstimateQscale path behaves — the
   DoVi VBV gate is passed) and prodmap HALVES sol10's single-pass ABR
   overshoot (+2.8..+6.2% vs anchor's +7.7..+12.0%). prodmap stays the CRF
   recommendation; ABR/VBV users buy chroma at a small luma price.
   **Decomposition DONE (2026-08-13, 24 encodes, RESULTS.md): the ABR luma
   cost is carried by `--hdr-luma-qp`** — it flips from −1.3…−1.5% (CRF) to
   +0.7…+0.8% (ABR) on both clips, a consistent ~2.2% swing; the chroma
   offsets cost the SAME in both modes (no ABR-specific penalty) and
   `--hdr-scene-qp` is exonerated (neutral, the a-priori suspect was
   wrong). Hypothesis for the flip (untested): ABR's complexity feedback
   re-plans against the AQ-redistributed lookahead costs and fights the
   redistribution.
   **USER DIRECTIVE (2026-08-13, HIGH priority): FIX `--hdr-luma-qp` under
   ABR/ABR+VBV — RESOLVED same day, see the 2026-08-13 session log below**
   (mechanism traced, fixed and validated: sol10 ABR +0.68 → −0.74, whale10
   ABR +0.83 → −0.32% wPSNR-Y vs anchor; CRF decoded-pixel-preserved). The
   re-tune-the-stack half (step 5) remains open: re-measure prodmap under
   ABR/ABR+VBV with the fixed binary, then re-tune strengths.
7. **HDR10+ / Dolby Vision compatibility assessed (user question), code
   verified at `6a9905161`:**
   - **HDR10+: no changes required.** `--dhdr10-info` SEI pass-through is
     orthogonal to all our tools (QP allocation + static SEI only). The
     opportunity item remains `--dhdr10-auto` (already on the TODO), and the
     measured-CLL work just built its foundation — the linear-light
     max(R,G,B) scan in `PicYuv::copyFromPicture` is exactly the stats pass
     maxSCL/percentile computation needs.
   - **Dolby Vision 8.1 (HDR10 base layer): works as-is**, pending the
     ABR/VBV sweep since DoVi *mandates* VBV (`param.cpp:2003`). Genuine
     synergy found: profile 8.1 force-enables `bEmitHDR10SEI/bEmitCLL`
     (`encoder.cpp:4059`), so without user `--max-cll` it emits CLL **0,0**
     today — `--hdr-measured-cll` in 2-pass fills it with real values.
   - **Dolby Vision 5 (IPTPQc2) and 8.4 (HLG): our colour assumptions do
     not hold.** Profile 5 is not BT.2020 YCbCr — the chroma tools' stats
     and the VVC chroma-QP table were derived for YCbCr, measured-CLL's
     BT.2020 NCL matrix is simply wrong there, and profile 5 sets its own
     `crQpOffset=3` (`encoder.cpp:4063`) which `--hdr-chroma-qp-map` would
     overwrite (it assigns the total offset). 8.4 is HLG, not PQ. → new
     TODO: a configure()-time guard.

### 2026-08-13 session log — `--hdr-luma-qp` ABR flip FIXED (user directive),
### mode-gated; full story in RESULTS.md "2026-08-13"

Commits `cedc6485e` (fix) + `4a85f0835` (mode gate) + `c00793a0e` (harness).

1. **Mechanism (decomposition hypothesis corrected)**: the per-QG JVET dQP
   term was NOT zero-mean — it is one-sided per frame (~+1.5 QP whole-frame
   on dark content at 0.5, sign flips at sol10's transition), violating the
   project's own zero-mean AQ invariant. A new `rc-end` debug trace
   (`--log-level debug`, parsed by `hdr-validation/abr_qp_trace.py`) showed
   the mean reaches the coded stream type-dependently — **cu-tree recomputes
   from AQ-weighted intra costs and eats most of it on referenced frames**
   (realized: I +1.6 / P +0.66 / B +0.23) — so ABR's type-specific QP
   bookkeeping (P from cplxr, I from accumPQp, B interpolated from refs)
   lands on a compressed I/P/B cascade (whale10 I−P coded gap 5.2 → 3.7).
   CRF has no feedback, so the raw form is harmless there.
2. **Fix, rate-targeted modes only** (`X265_RC_ABR`, single-pass): zero-mean
   the per-QG term in `calcAdaptiveQuantFrame`, apply the removed mean in
   `rateEstimateQscale` as its **deviation from an EMA** of recent frame
   means (re-baselined at scene cuts); B interpolation undoes refs' applied
   biases (`m_lowres.hdrLumaQpBias` stores the applied value), `accumPQp`
   kept in unbiased space. Two dead ends measured, don't re-derive: an
   ABSOLUTE visible bias re-creates itself through the bits·qscale feedback
   (whale10 undershot −18.6%); zero-meaning UNDER CRF costs +2.11% wPSNR-Y
   on whale10 because the cu-tree type-asymmetry of the raw mean IS part of
   the CRF gain (the `lumaq05fix_crf*` rows in results.json are that
   rejected experiment).
3. **Verdict (lumaq05fix vs anchor, wPSNR-Y BD)**: sol10 ABR **−0.74** (was
   +0.68), whale10 ABR **−0.32** (was +0.83), whale10 ABR+VBV **−0.78**,
   sol10 ABR+VBV neutral (mean −0.06 dB; its 4-point BD fit is scatter, do
   not quote +4.9%). PSNR-Y moves the same way; whale10 XPSNR-Y improves
   +2.87 → +2.23 but stays positive (only metric not flipping). Zero VBV
   warnings in 16 VBV encodes; rate accuracy unchanged. CRF verified
   decoded-pixel identical to pre-fix on both clips; anchor byte-identical.
4. **Verification pattern that did the work**: per-frame qpRc-vs-qpAq traces
   (dAQ per slice type) — the fixed arm's dAQ matches anchor within 0.08 QP
   per type. Trace line is a permanent debug-level log in rateControlEnd.
5. **prodmap re-measured on the fixed binary same session (`prodmapfix`,
   RESULTS.md): the stack's ABR luma price roughly halves** — sol10 ABR
   +1.86 → +0.47, whale10 ABR +1.47 → +0.79, whale10 ABR+VBV +2.00 → +0.94
   % wPSNR-Y vs anchor, full chroma gains kept; sol10 ABR+VBV is a small
   real ≈−0.1 dB cost (the one cell to watch in the re-tune — sol10 is
   where the EMA bias actively fires under the VBV clip). Zero VBV
   warnings. Also: pre-fix prodmap's sol10 overshoot halving was partly
   the invisible offsets deflating the bits·qscale books — honest books
   converge anchor-like (+6.0..+9.6% vs anchor +7.7..+12.0%).
6. **Strength re-tune DONE same day (48 encodes, RESULTS.md late): keep
   0.5 as the single strength across all modes.** sol10 ABR keeps the
   CRF-style 0.5–0.75 plateau (−0.74/−0.71); whale10 ABR degrades
   monotonically with strength (0.25 best, 1.0 +0.80); VBV is
   strength-independent within ±0.06 dB per-point on both clips — the
   sol10-VBV concern resolved as a tiny constant interaction, not a
   tuning problem. 0.25 noted as a conservative ABR-only point (best
   whale10 ABR, gentlest on XPSNR). No cli.rst change needed.
7. **Open next**: design + measure the CRF+VBV harness arm (capped-CRF,
   never measured in any mode; proposal: CRF 22–34 with vbv-maxrate ≈
   1.1× the anchor bitrate at each CRF). The directive's re-tune half is
   otherwise closed — tool strengths hold at 0.5/1.0/0.25 in all modes.
   **DONE 2026-08-14 — see the session log below.**

### 2026-08-14 session log — capped-CRF (CRF+VBV) validated (RC-mode matrix
### complete), Q_JOD extended to every rate mode, absolute tables per mode

Full numbers in RESULTS.md "2026-08-14" (two sections); harness additions
`run_ccrf_sweep.sh`, `ccrf_metrics.py`, `vdp_evals_modes.sh`,
`abs_table_modes.py` (+ saved `abs_table_modes_2026-08-14.txt`).

1. **Capped-CRF verdict: behaves like CRF, not like ABR.** 24 encodes
   (anchor / lumaq05fix / prodmapfix, CRF 22–34, vbv-maxrate = 1.1× the
   anchor bitrate at that CRF, bufsize = maxrate). prodmap wPSNR-Y BD vs
   anchor **−0.06 (sol10) / −0.64 (whale10)** with whale10's full chroma
   gains (−17.5/−20.5) — the CRF recommendation extends to capped-CRF
   without the ABR luma-price caveat. Zero VBV warnings; all encodes under
   cap (whale10 tool arms at 76–80% of cap — they save 13–14% bitrate at
   equal CRF, same as plain CRF mode).
2. **The 2026-08-13 mode gate is correctly bounded**: under capped-CRF the
   RAW one-sided per-QG bias runs (gate is `X265_RC_ABR` only) while the
   VBV clip engages, and `--hdr-luma-qp 0.5` still lands in its CRF band
   (−0.89/−1.44% wPSNR-Y) — no ABR-style flip, no fix needed. The RC-mode
   matrix (CRF / ABR / ABR+VBV / capped-CRF) is now fully measured.
3. **Q_JOD now covers every rate mode** (user directive: Q_JOD column in
   the tables): `vdp_evals_modes.sh` ran HDR-VDP-3 over all 72 rate-mode
   encodes (864 evals, 12-frame grids, 0 failures; per-key prep→eval→delete
   keeps the f32 scratch ~300 MB — the disk cannot hold 72 keys' dumps).
   Read: all deltas ≤ ~0.05 JOD; prodmapfix is +0.02..+0.05 on whale10
   ABR/VBV (the chroma-mediated NCL effect), sol10 noise — perceptually the
   arms are the same picture in every RC mode, consistent with the CRF-mode
   decomposition.
4. **Absolute rate-quality tables per mode** (`abs_table_modes.py`; layout
   of abs_table.py with kbps | PSNR-Y | wPSNR-Y | wPSNR-Cb | wPSNR-Cr |
   XPSNR-Y | Q_JOD): ABR, ABR+VBV and capped-CRF, pasted into RESULTS.md.
5. Ops note for detached runs on this machine (harness background tasks
   were repeatedly killed this session; Start-Process survivors are the
   reliable pattern): PowerShell 5.1 `Start-Process -ArgumentList` does NOT
   quote args containing spaces — `bash -c 'PAR=4 script.sh'` reaches bash
   as two tokens and silently runs only the assignment. Pass a single
   space-free script path (wrap env in the script) and check for surviving
   orphan children before relaunching, or two instances race on the same
   output files.
6. **Plan agreed with user (2026-08-14)**: finish the small HDR items first
   — DoVi guard (**DONE same session, item 7 below**), `--hdr-scene-qp`
   transient segment — then **general (non-HDR) efficiency tools move to a
   separate new branch off master** (ARF first, per ARF-SCOPING.md stage 0).
   Branch setup checklist for that session: branch from the upstream master
   tip the HDR branch is rebased on; cherry-pick a slimmed metric harness
   (PSNR/XPSNR/bdrate/abs-table machinery — not the HDR-specific parts);
   move `ARF-SCOPING.md` over; own CLAUDE.md section; decide X265_BUILD
   policy (HDR branch is at 226 on upstream's 217 — parallel param
   additions will collide at merge time).
7. **DoVi guard implemented same session** (encoder.cpp, right after
   `configureDolbyVisionParams` so profile 5's `crQpOffset=3` survives):
   profiles 5/8.2/8.4 disable all HDR tools with a warning and take back
   `--hdr-pq`'s −2/−2 (8.2 added beyond the TODO's 5/8.4 scope — SDR BT.709
   base, same mismatch). Verified on 10-frame encodes: profile 5 stream
   signals ipt-c2/full-range with cbqpoffs=0 crqpoffs=3 and zero HDR tool
   strengths in the version SEI; 8.4 → 0/0; 8.1 keeps −2/−2 and all stack
   tools active with no warnings. cli.rst `--dolby-vision-profile` section
   documents the interaction. No X265_BUILD bump (no API change).
8. **`--hdr-scene-qp` exercised same session** (the last open HDR small item
   — see the [x] TODO entry and RESULTS.md 2026-08-14): `gen_flash10.py`
   transient segment + permanent `hdr-scene-qp:` debug trace. Mechanism
   verified sane in all modes; wPSNR-negative by construction on flash
   content (temporal masking); two upstream findings recorded (scenecut
   fires on full-frame flashes; fade-adjacent cut re-baselines one frame
   early → PQ-aware-scenecut TODO evidence). **Both HDR small items are now
   closed — next session starts the general-efficiency branch (item 6).**

### TODO — HDR quality / efficiency investigation

- [x] **Strength sweeps** for `--hdr-luma-qp` — measured 2026-08-05: BD-optimal
      plateau 0.5–0.75, recommend 0.5 (docs updated); 1.5 reverses the gain. Pure
      model gains on both clips (sol −1.31 / whale −1.50% wPSNR-Y at 0.5).
- [x] **Content-adaptive chroma offsets** — implemented 2026-08-05 as
      `--hdr-chroma-adapt <float>` (`862809aed`). Design differs from the sketch in one
      key way: the probe FALSIFIED "scale by chroma energy so chroma-flat frames drop
      the offset" — whale10 (where −2/−2 is cheap and valuable) is the chroma-FLAT clip
      (share 0.03-0.05) and sol10 (where it costs +7%) the chroma-heavy one (up to
      0.4): the offset's cost tracks the chroma share of residual-coding work. So the
      mapping is inverted: low share keeps the offset, high share cancels it (share
      through [0.10, 0.30], slice-level delta vs the PPS offsets). Measured 2026-08-05
      at strength 1.0: sol10 floor cost +7.14 → +1.19% wPSNR-Y (< +3% target met),
      whale10 identical to the floor with full chroma gains — working as designed.
- [x] **CAMBI into the harness** — done 2026-08-05 late-2 (`cambi.py` via the local
      ffmpeg's libvmaf, `gen_band10.py` dithered-gradient segment). The tuning half is
      MOOT: banding-protect measured +9/+23% wPSNR-Y BD-rate at 0.5/1.0 with CAMBI
      unmoved — band10's banding is dither-loss banding, unfixable by QP allocation
      (CRF12 control scores WORSE CAMBI than CRF34). Tool marked not-recommended in
      cli.rst; any redesign needs a coarse-gradient segment that isolates the
      QP-domain banding mode first.
- [x] **Exercise `--hdr-scene-qp`** — done 2026-08-14 (`gen_flash10.py` transient
      segment: lightning, hard cuts, fade, fireworks; permanent debug trace in
      `updateHdrSceneQpBias`; RESULTS.md 2026-08-14 scene-qp section). Mechanism
      sane: fade tracked, fireworks get the full designed bias cycle, VBV/ABR
      safe, deterministic across modes. Three findings: full-frame flashes fire
      the scenecut re-baseline rather than the bias; a fade-adjacent cut
      re-baselined one frame early (direct evidence for the PQ-aware-scenecut
      TODO); the APL EMA updates in coding order (bounded jitter, known
      behavior). wPSNR-Y −0.56 dB at strength 1.0 under ABR on flash content —
      the expected static-metric penalty for a temporal-masking tool; keep
      default-off, judge subjectively. VBV descriptor now carries it.
- [x] **Dolby Vision guard for the HDR tools** — implemented 2026-08-14 (see the
      session log): profiles 5 (IPTPQc2), **8.2 (SDR — added beyond the original
      scope, same mismatch)** and 8.4 (HLG) warn-and-disable every HDR tool and
      take back `--hdr-pq`'s −2/−2 offsets (profile 5's mandated `crQpOffset=3`
      preserved — the guard runs AFTER `configureDolbyVisionParams`). Profile 8.1
      untouched and verified fully working with the prodmap stack. No X265_BUILD
      bump (configure()-time behavior, no API change).
- [ ] **Derive `--hdr-scaling-list` from the PQ CSF** instead of the current arbitrary
      convex ramp; compare against HM's default intra lists as a baseline.
- [ ] **Cross-check wPSNR** against HDRTools/VTM's implementation (VTM checkout exists at
      `C:\VVCSoftware_VTM`); add DeltaE-ITP (BT.2124) as a color-aware metric.
- [x] **Deepen HDR-VDP-3** — done 2026-08-07 (4 → 12 frames/encode, 288 evals). The
      conclusion is a *methodology* result: deepening did NOT rescue the Q_JOD
      **BD-rate**, and can't — bootstrap 95% CIs over frames straddle zero for every
      arm (e.g. whale10 hdr10opt −10.19% with CI [−27.9, +6.1]) because Q_JOD spans
      only ~0.5–1.0 JOD across a 4–5x rate range, so the cubic fit amplifies ±0.03 JOD
      into double-digit percentages. **Do not tune on Q_JOD BD-rate.** What the deeper
      sampling *did* fix is the **paired per-CRF ΔQ_JOD** (same frames, same reference,
      so content variance cancels): sem drops 0.07–0.21 → 0.01–0.05 and differences
      become significant. Use `paired_jod.py` + `bootstrap_jod_bd.py`; full-frame and
      16+ frames remain optional refinements, not blockers.
- [ ] **cu-tree interaction**: verify the HDR per-QG offsets seeded into `qpCuTreeOffset`
      aren't double-propagated by cu-tree; test `--aq-mode 1` vs `3` with the tools on.
- [ ] **Corpus expansion**: probe `Regatta_3840x2160_HDR10_420_60p.yuv` (frame size is
      non-integral for 16-bit 4:2:0 at that resolution — format unknown), pull more
      Netflix Open Content / CableLabs 4K HDR clips; at least one natural-dark and one
      graded-bright clip per class.
- [x] **ABR + VBV sweep** mirroring the CRF one — done across 2026-08-12/13/14:
      ABR + ABR+VBV sweep and verdict (2026-08-12 late), luma-qp flip fix + re-tune
      (2026-08-13), capped-CRF arm + per-mode absolute tables with Q_JOD
      (2026-08-14). The RC-mode matrix is fully measured; prodmap holds everywhere,
      with a small luma price only under ABR/ABR+VBV.
- [ ] **Subjective pass on an HDR display** for the two subjective tools before any
      further metric-driven tuning of them.
- [x] **wSSE-weighted RDO** — implemented 2026-08-04 as `--hdr-wsse-rd <float>`
      (`c859ad181`). Design differs from the original sketch after review: instead of a
      fourth cost flavor at ~24 sites, the weight is applied as a per-CTU *lambda* scale
      at the single choke point `Search::setLambdaFromQP()` (argmin-equivalent, reaches
      mode-decision + ME + RDOQ lambdas consistently, leaves distortion stats and
      analysis-reuse untouched). Weight cache is keyed by (poc, ctuAddr) for determinism.
      **Measured 2026-08-05: negative** — lambda decoupled from the quantizer step is
      off-hull; whale +1.5/+5.4/+12.1% wPSNR-Y vs floor at 0.5/1.0/1.5 (see the
      validation-established section and RESULTS.md). Kept off-by-default; don't pursue
      as implemented.
- [x] **Measured MaxCLL/MaxFALL → CLL SEI** — implemented 2026-08-12 as
      `--hdr-measured-cll` (X265_BUILD 226): pass 1 measures the CTA-861.3
      linear-light max(R,G,B) definition per frame and writes a `#cll:` stats-file
      trailer; pass 2 reads it and emits the CLL SEI; explicit `--max-cll` wins;
      single-pass measures and logs only. Validated against a full-precision numpy
      reference (exact match on whale10). See the 2026-08-12 session log.
- [ ] **VTM HDR lambda tables**: try VTM's PQ-tuned QP-to-lambda and chroma lambda
      weighting in x265's lambda setup, plus the temporal-layer lambda/QP cascade models
      (x265's fixed ipratio/pbratio vs VTM's QP-adaptive ones); cheap to test with the
      existing wPSNR harness. Reimplement the concept, don't port code (BSD→GPLv2 is fine
      but the commercial dual-license makes copied code a relicensing problem).
- [ ] **MCTF temporal pre-filter** — RE-SCOPED 2026-08-04: the rebase onto v4.3 master
      brought a full upstream MCSTF implementation (`--mcstf`, `--selective-mcstf`,
      AVX2 kernels, multithreaded ME, HM-equivalent lowres averaging), which covers the
      original "port HM/VTM MCTF" idea. New scope: *evaluate and HDR-tune upstream
      MCSTF* — measure it on the PQ corpus with the wPSNR harness, check the
      interaction with the HDR lookahead stats (its HM-averaging lowres path is gated
      on `bEnableTemporalFilter`, so HDR stats are unaffected unless enabled —
      untested combination), and consider PQ-aware filter strength (noise in PQ
      near-blacks is the expensive case).
- [ ] **Experiments** (cheap; keep only if they measure well on the harness):
      joint-chroma RD bias (zero the weaker chroma residual when Cb/Cr anti-correlate —
      the only conformant shadow of VVC JCCR); per-luma-band RDOQ lambda (HDR-tuned
      `--rdoq-level`, folds into the wSSE weighting item).
- [ ] **Auto-generated HDR10+ dynamic metadata** (`--dhdr10-auto`): today x265 only
      *inserts* user-supplied ST 2094-40 JSON (`--dhdr10-info`). Compute the per-scene
      statistics the SEI carries (maxSCL, average maxRGB, luminance-distribution
      percentiles, optionally bezier anchors) from the pixels during encode and emit the
      SEI natively — the largest perceived-quality lever on mid-range HDR displays, which
      tone-map far better with dynamic metadata. Reuses the `dynamicHDR10/` SEI writer
      (`ENABLE_HDR10_PLUS`) and shares the linear-light stats pass with the measured-CLL
      item. SEI-only, conformant.
- [ ] **Grain-aware HDR pipeline**: estimate grain from the source, lightly denoise, and
      signal Film Grain Characteristics SEI for display-side re-synthesis (the AV1-proven
      flow; x265's `--film-grain`/`--aom-film-grain` only pass through hand-authored
      files today). Noise in PQ near-blacks is extremely expensive to code; large
      compression win on grainy masters. Non-supporting decoders simply show the denoised
      video. The grain-estimation stage is the real work; plan separately like MCTF.
- [x] **SAO banding-repair bias** — implemented 2026-08-05 late-3 as
      `--hdr-sao-band <float>` (X265_BUILD 222), **measured negative, keep off**:
      per-CTU SAO lambda bias in banding-prone CTUs (source-variance classifier in
      `rdoSaoUnitCu`). Engages hard (+7..+26% rate) but CAMBI does not improve
      (worse at low CRFs, noise at CRF34) — SAO's per-class constant offsets are the
      wrong operator space: EO touches only 1-px contour pixels (plateau interiors
      are the no-offset "flat" class), BO shifts whole plateaus without changing the
      steps inside a 32-code band. With banding-protect and the CRF12 control this
      CLOSES the conformant encoder-side banding question: neither QP nor SAO can
      repair dither-loss banding — the levers are grain/dither preservation (FGC
      pipeline) or display-side debanding. Full numbers in RESULTS.md late-3.
- [x] **Luma-adaptive deblocking offsets** — implemented 2026-08-04 as
      `--hdr-deblock <float>` (`93610f195`): per-frame slice-header beta/tc overrides
      from `hdrFrameAvgLuma`, delta = round(strength · clip3(−2, 3, (400 − APL)/150)),
      on top of `--deblock` base offsets. x265 previously never used slice deblock
      overrides (PPS flag was hard-coded 0); the loop filter now reads per-slice fields.
      Verified: default path bit-identical, recon byte-equal to ffmpeg decode with
      overrides engaged. Measured 2026-08-05: wPSNR-neutral-to-slightly-positive
      (+0.2 sol / −0.7 whale vs floor). Subjective dark-frame pass done
      2026-08-12: no artifacts — tool closed, kept optional.
- [ ] **Linear-light weighted-prediction analysis**: weightp fits gain/offset on PQ code
      values, but real light fades are linear in nits — PQ non-linearity gives HDR fades
      poor weights and expensive residuals. Fit weights in linear light via LUT, map
      back; check weightp denominator precision at 10-bit. Helps the same content class
      `--hdr-scene-qp` targets.
- [ ] **PQ-aware scenecut detection**: SDR-tuned SAD thresholds under-fire in dark PQ
      scenes (tiny code-value deltas, large perceptual change) — misplaced IDRs and
      missed `hdr-scene-qp` re-baselining. Weight lookahead scenecut costs by the wSSE
      luma factor, or run `--hist-scenecut` on linear-light histogram bins.
- [ ] **Per-luma-band adaptive rounding offsets**: bias the quantizer rounding offset per
      luma band (H.264 JM "adaptive rounding" lineage) — round up more aggressively in
      shadows to keep the low-amplitude texture PQ makes visible, with no QP/lambda
      change. Tiny footprint in `Quant`, orthogonal to RDOQ, cheap to sweep.
- [ ] **Upstream prep** when results justify it: 4-config CI build check, clang-format on
      the diff, CONTRIBUTING.md CLA flow (mailing list or PR).

### TODO — CNN-assisted HDR tools (encoder-side only; a decoder never runs a network)

Integration constraints that apply to every item below: HEVC Main10 conformance rules out
anything in-loop — CNNs may only analyze, pre-process, or generate metadata. Inference
must be deterministic (CPU int8, fixed threading — one session per lookahead TLD,
intra-op threads = 1) so encodes stay reproducible. Runtime behind a CMake gate
(`ENABLE_CNN_ANALYSIS`, following the `ENABLE_HDR10_PLUS` optional-component pattern):
ONNX Runtime CPU EP, or hand-rolled int8 conv kernels on x265's own SIMD primitives
(dependency-free, TestBench-verifiable against a C reference). Lookahead worker jobs must
never block — models must be small enough to run inline on lowres (~1-5 ms/frame).
Training labels come from the `hdr-validation/` harness (CAMBI maps for banding, oracle
per-block QP sweeps for sensitivity); train offline in Python, export ONNX. New params
(`--cnn-aq <model>`, `--cnn-aq-strength`) follow the 7-step API checklist.

- [ ] **CNN perceptual sensitivity maps in the lookahead** (highest value, lowest risk):
      small int8 CNN (<100k params) on the half-res `m_lowres` luma inside
      `calcAdaptiveQuantFrame()`, emitting per-QG maps — banding-proneness (learned
      replacement for the `--hdr-banding-protect` variance gate), PQ-aware texture
      masking / dark-detail visibility (learned form of the JVET dQP model), saliency.
      Output is an additive `qp_adj` term through the existing
      `qpAqOffset`/`qpCuTreeOffset`/`invQscaleFactor` plumbing — subject to the same
      zero-mean constraint as every other AQ contribution.
- [ ] **Per-frame content classifier driving tool strengths**: tiny model (pooled lowres
      features) classifying dark-graded vs natural-bright, fades, grain level; modulates
      `--hdr-luma-qp` / `--hdr-scene-qp` / deblock-offset strengths per frame. The
      learned version of the content-adaptive re-centering item; consumed in
      `RateControl` and per-frame parameter decisions.
- [ ] **CNN-assisted HDR10+ curve generation**: better bezier tone-map anchors than raw
      percentiles for the `--dhdr10-auto` item's SEI writer. Pure metadata, zero
      conformance risk; depends on `--dhdr10-auto` existing first.
- [ ] **CNN pre-filters (denoise/deband) and CU-split prediction** (later tier, plan
      separately): full-res pre-filtering pairs with MCTF and the grain-aware FGC
      pipeline; split prediction in `Analysis::compressCTU()` buys speed that converts
      to quality via slower presets at equal encode time.

### TODO — AV1/AV2 and research-literature tools worth adapting (added 2026-08-08)

**Why this list is separate.** The VVC/JVET list above is close to exhausted on the
metric this project targets: `--hdr-luma-qp` is the only allocation tool that gains,
the chroma tools are a luma-for-chroma trade, and the three VTM-derived tools measured
2026-08-08 came out negative (`--hdr-qp-cascade`), neutral (`--hdr-vtm-lambda`) and
"only worth it shallow" (`--hdr-chroma-qp-map`). What remains in the VVC direction is
mostly decoder-normative. So the next round should come from **AV1/AV2 encoder
technology and the coding literature**, where the biggest wins are in *what the
encoder decides* — dependency-aware RDO, reference management, bit allocation across
frames and shots — rather than in how QP is sprinkled within a frame.

**Ground rules, same as before.**
- HEVC Main10 conformance: encoder-side decisions, conformant syntax (scaling lists,
  PPS/slice offsets, deblock overrides, SAO, weightp, RPS including **long-term
  references**), or SEI. No decoder changes.
- **Reimplement from papers/specs; do not port code.** libaom and SVT-AV1 are
  BSD-2/BSD-3 with patent grants, and AVM likewise — permissive, but x265's commercial
  dual-license makes *copied* code a relicensing problem exactly as with VTM.
- **Most items here are NOT HDR-specific.** `hdr-validation/` measures wPSNR/Q_JOD on
  two PQ clips; these tools need standard PSNR/SSIM BD-rate on broader material, so the
  corpus-expansion item above becomes a prerequisite rather than a nice-to-have.
  Several also need *multi-shot* and *static-background* content, which the current
  corpus does not contain.

#### P0 — metric prerequisites, or the rest of this list is unmeasurable

The 2026-08-07/08 sessions established the core problem: **wPSNR and Q_JOD cannot
see the tools we are building.** Every perceptual tool so far measured neutral or
negative on wPSNR by construction, and Q_JOD moves by ~0.02 JOD — two orders of
magnitude under the noticeability unit. Perceptually-motivated tools (QPA,
variance boost, per-pixel wSSE, grain) therefore cannot be *judged* on the current
harness, only penalised by it. Fix the metrics first.

- [x] **XPSNR in the harness** — done 2026-08-11 (`xpsnr.py` via the local
      ffmpeg 8.1 filter, columns in results.json/bdrate.py/rate_matched.py,
      backfilled across the sweep). First read agrees with wPSNR on every
      standing verdict (hdr10opt trades 0.8–1.9 dB XPSNR-Y for chroma;
      prodstack/prodmap XPSNR-neutral at equal rate). **Trap for any future
      two-input ffmpeg metric: ffmpeg 8 negotiates color range/space across
      filter graphs — force-tag BOTH branches with setparams or a silent YUV
      matrix conversion (~7 dB Y error) lands on one branch. Verified
      byte-exact against numpy after the fix.** Original rationale kept:
      The perceptually weighted PSNR
      variant designed exactly for this gap — spatio-temporal activity weighting,
      much better subjective correlation than PSNR, and the metric VVenC's QPA
      optimises, so it is the natural yardstick for the QPA item below. **Cheap:
      the local ffmpeg already has the filter** (`ffmpeg -filters | grep xpsnr`
      confirms `xpsnr VV->V`), so this is the same zero-new-binaries route CAMBI
      took via libvmaf — add an `xpsnr.py` alongside `wpsnr.py`/`cambi.py` and a
      column in `results.json`. Do this first; it is hours, not days, and it
      changes what every later item is allowed to conclude.
- [x] **DeltaE-ITP (BT.2124)** — done 2026-08-11 (`deitp.py`: PQ→LMS→ICtCp per
      BT.2100-2/BT.2124, validated structurally, float32; sampled on the
      HDR-VDP 12-frame grid so per-frame values pair with Q_JOD; in metrics.py
      for the chroma-relevant arms, `DEITP_CFGS`; backfilled, 96 keys). **First
      read (RESULTS.md 2026-08-11): the chroma tools finally have a metric that
      sees them — hdr10opt buys 7–20% colour-error reduction at equal bitrate
      (for its known luma price), prodstack/prodmap keep a smaller free
      +0.08…+0.54 ΔE. Natural next read: the cqpmap depth series as a
      luma-vs-ΔE Pareto curve.** Original rationale: the colour-aware companion, already listed in the
      HDR TODO above under the wPSNR cross-check item. Promoted here because the
      2026-08-08 decomposition showed the chroma tools' only measurable effect
      reaches Q_JOD through NCL luminance leakage: without a colour metric, every
      chroma decision is being judged by a luminance proxy.

#### P1 — highest expected value

- [ ] **Alt-ref / hidden frames via `pic_output_flag` — AV1's ARF, and HEVC can do
      it.** **SCOPED 2026-08-12 — read `hdr-validation/ARF-SCOPING.md` before
      starting.** Four-stage plan (syntax proof → POC-space doubling → ARF
      injection → tuning), ~3-4 sessions to first BD-rate number. The dominant
      cost is the POC audit: keep `Frame::m_poc` as the input frame number and
      add a bitstream-only coded POC (2n displayed / 2n−1 hidden), switching
      the slice header, RPS, DPB marking and every `cudata.cpp` MV-scaling POC
      read — miss one and quality silently degrades. Stage 0 (enable the flag
      + drop one frame, prove ffmpeg honours it) costs half a session and
      de-risks the rest. **Deferred to a coming session (user, 2026-08-12):
      it is a general coding-efficiency tool, not HDR-specific — start here
      when the HDR validation tail (ABR/VBV) is closed.** The slice header carries `pic_output_flag` (gated by the PPS
      `output_flag_present_flag`), so a frame can be coded, used as a reference, and
      **never displayed** — which is precisely AV1's alt-ref/hidden-frame
      mechanism, one of its largest structural advantages. `grep -rn pic_output_flag
      source/` returns **nothing**: x265 has no support at all. The generator for
      the frame content already exists in-tree — upstream MCSTF produces exactly the
      temporally-filtered picture an ARF wants — so the missing pieces are the PPS
      flag, the slice-header bit, DPB lifetime for a non-output picture, and rate
      control accounting for a frame that costs bits but displays nothing. Pairs
      with the LTR item below: `pic_output_flag` gives *hidden-ness*, LTR gives
      *lifetime*, and AV1's ARF is both. Strongest structural item on this list
      after TPL, and unlike LTR it should show up on ordinary moving content.
- [ ] **Dependency-aware RDO / temporal dependency model (AV1's TPL).** The single
      biggest known encoder-side lever, and a large part of why AV1 encoders beat HEVC
      at the same GOP structure. What x265 has: cu-tree (`estimateCUPropagate`,
      `slicetype.cpp:4002`) — the x264 lineage, propagating *lowres SATD cost
      fractions* backwards into a per-QG QP offset. What libaom's TPL does differently:
      a real per-block motion search, **transform-domain distortion and rate**
      estimates, recursion across the whole mini-GOP, and it derives **both** a
      per-block delta-q *and* a per-block rdmult (lambda) scale from how much future
      distortion depends on that block. Seam in x265: the lookahead already has lowres
      MVs and costs, and `qpAqOffset`/`qpCuTreeOffset`/`invQscaleFactor` already carry
      per-QG offsets into `calcAdaptiveQuantFrame`. **Stage it:** (1) calibrate by
      measuring cu-tree off vs on on the corpus so the baseline magnitude is known;
      (2) replace cost-fraction propagation with distortion propagation; (3) add the
      matching per-CTU lambda scale. Note the 2026-08-08 lesson: a lambda scale
      *without* the matching QP move is neutral at best, and negative when applied
      per-block — TPL works precisely because delta-q and rdmult move together. Keep
      contributions zero-mean (the banding-protect rule). Effort: large; stage it.
- [ ] **Long-term reference frames — HEVC supports them and x265 does not implement
      them at all.** (Companion to the `pic_output_flag` item above: that one gives a
      frame hidden-ness, this one gives it lifetime.) `grep -r longTerm source/` returns nothing; `dpb.cpp` builds a
      sliding window of short-term refs plus b-pyramid. AV1's GOLDEN/ALTREF and the
      HEVC background-modeling literature (static-background surveillance coding) both
      exploit a long-lived high-quality reference, and HEVC signals LTRs in the RPS
      (`used_by_curr_pic_lt_flag`, `poc_lsb_lt`) — fully conformant Main10. Two
      variants: (a) pin the shot's first or best frame as an LTR for the whole shot,
      helping occlusion recovery, periodic motion and static backgrounds; (b)
      synthesise a background frame from accumulated frames and code it as an LTR (the
      SBM papers report large gains on surveillance). Expect little on the current HDR
      corpus — both clips move throughout — so this needs static/repetitive material to
      show anything; pair it with corpus expansion. Effort: substantial (RPS signalling,
      DPB lifetime, reference lists, RC accounting) but self-contained, and the ceiling
      is high because nothing in x265 competes with it today.
- [ ] **Shot-level convex-hull bit allocation (Netflix "dynamic optimizer",
      Katsavounidis).** Encode each shot at several CRFs, then pick per-shot operating
      points on the sequence-level convex hull under a total bit budget. No encoder
      change and no conformance question — a driver-level wrapper — and x265 already has
      `--zones`/zonefile to *apply* a per-segment QP decision. Reliably several %
      BD-rate over fixed CRF on multi-shot content, and our harness already produces
      exactly the per-shot R-D data it consumes. Cheapest P1 item by far; needs a
      multi-shot clip.

#### P2 — solid, moderate effort

- [ ] **VVenC QPA — perceptually optimised QP adaptation (Helmrich et al.).** The
      reference implementation is **already in the local VTM checkout** under
      `ENABLE_QPA` (`source/Lib/EncoderLib/EncSlice.cpp`:
      `filterAndCalculateAverageEnergies()` computes a high-pass spatial activity
      measure, `lumaDQPOffset()` the luma-dependent term, and the QPA path derives
      per-CTU QP from spatio-temporal visual activity with a masking model). This is
      the mature, subjectively-validated version of what x265's `--aq-mode` does
      crudely and of what our per-QG HDR tools do heuristically — and it is the
      encoder side of the same model XPSNR measures, which is why the two belong
      together: implement XPSNR first, then QPA becomes measurable rather than a
      leap of faith. Reimplement the model from the papers, do not port the code.
      Probably the highest-value P2 item for perceptual quality.
- [ ] **Adaptive MCSTF strength (SVT-AV1-style).** Upstream MCSTF applies a fixed
      filter strength; SVT-AV1 modulates its temporal-filter strength per frame from
      noise, motion and prediction-error statistics. The evaluate-and-HDR-tune MCSTF
      item in the HDR TODO above covers measuring MCSTF as-is; this is the follow-on
      once that baseline exists, and it matters most for the case that item flags —
      noise in PQ near-blacks, which is the expensive content to code and where
      over-filtering costs detail.
- [ ] **Perceptual rdmult / variance boost (SVT-AV1 `--variance-boost`, libaom
      `--deltaq-mode` perceptual modes, and the SSIM-RDO literature).** Per-block
      lambda scaling from local variance in octaves, tuned for subjective/SSIM rather
      than PSNR. x265 has variance-based *QP* adaptation (`--aq-mode` 1-4) and
      `--ssim-rd`/`--psy-rd`, but no variance-driven *rdmult* scaling in the SVT-AV1
      sense, and AQ and lambda are not jointly tuned. Implement as a joint (QP offset,
      matching lambda) pair — see the 2026-08-08 lambda finding. Judge with
      SSIM/subjective, not wPSNR, or it will look negative by construction.
- [ ] **Per-frame RD search of deblocking (and SAO) parameters.** The infrastructure
      now exists: `--hdr-deblock` added the first use of HEVC slice-level beta/tc
      overrides in x265. Instead of a heuristic from APL, actually try a small set of
      (beta, tc) pairs on the reconstructed frame and pick by SSE/wSSE. The
      optimal-deblocking-parameter literature reports small but consistent gains; the
      cost is extra filter passes over a recon copy, cheap next to analysis. Same idea
      for SAO merge decisions.
- [ ] **Adaptive mini-GOP structure from lookahead statistics** (libaom
      `define_gf_group` chooses GF/ARF group length from firstpass noise, motion and
      coherence stats). x265 has `--b-adapt 2` (trellis B-count) and scenecut
      detection, but pyramid depth and mini-GOP length are essentially fixed by
      `--bframes`/`--b-pyramid`. Deep pyramids for static scenes, shallow for high
      motion. Conformant, cheap to try, and it is the *bit-neutral* version of what
      `--hdr-qp-cascade` got wrong: that tool coarsened the deepest layer under CRF,
      which only removes bits because CRF has no reallocation mechanism, whereas
      choosing the *structure* changes what gets referenced.
- [ ] **R-λ (λ-domain) rate control — Li et al., JCTVC-K0103, HM's default.**
      x265's RC is q-domain
      (`getQScale`, an empirical cplxr model). λ-domain RC is more rate-accurate and
      better behaved at low rates and under VBV. Contained change, clear measurement
      (rate accuracy + BD-rate in ABR/VBV), and it composes with the ABR+VBV sweep item
      above.

#### P3 — speculative, narrow, or blocked on something else

- [ ] **ICtCp / DeltaE-ITP-aware distortion in RDO** (HDR-specific). Replace
      per-component SSE weighting with a perceptual colour-difference weighting in
      ICtCp. Encoder-side only, conformant. This is the principled version of what the
      chroma-QP tools do bluntly, and the 2026-08-08 decomposition gives it a motive:
      chroma changes reach Q_JOD through NCL luminance leakage, which a colour-aware
      distortion metric would model directly. Depends on the DeltaE-ITP metric item
      above for validation.
- [ ] **Per-pixel wSSE distortion in mode decision** — VTM's actual HDR RDO
      (`RdCost::initLumaLevelToWeightTable`: the weight applied to distortion at pixel
      granularity, lambda untouched). Cross-referenced from the wsse post-mortem; the
      cost is weighted-SSE distortion kernels, i.e. the "fourth cost flavor" design
      previously rejected as invasive. Better motivated now: the per-CTU lambda version
      failed and the global lambda version is neutral, so granularity is the untested
      variable.
- [ ] **Cyclic intra refresh (VP9/AV1 low-delay `aq-mode=3`)**: refresh a fraction of
      blocks per frame at lower QP to build a clean reference without an IDR.
      Conformant and valuable for low-delay/RTC streaming, orthogonal to HDR — only
      worth it if the project's scope widens beyond VOD-style HDR.
- [ ] **AV1 quantizer matrices (`--enable-qm`) analogue** — already covered by the
      "derive `--hdr-scaling-list` from the PQ CSF" item; AV1's qm tables are a second
      reference point for what a perceptually-tuned matrix set looks like.
- [ ] **ML partition pruning / early termination** — already in the CNN list; buys
      speed that converts to quality via slower presets at equal wall-clock.

#### Not portable — decoder-normative in AV1/AV2 (don't re-derive)

CDEF, loop restoration (Wiener / self-guided), superres, switchable transform kernels
and the extended intra mode set, chroma-from-luma (CfL), palette and IntraBC (HEVC has
these only in the SCC extension, not Main10), and AV1's film-grain *synthesis*
normativity — HEVC's FGC SEI is advisory, which is why the grain item above is a
pipeline rather than a coding tool. Same category as JCCR / LMCS / dependent
quantization on the VVC side.

### Evaluated and rejected (2026-08 idea review — don't re-derive)

- **JCCR** (VVC joint chroma residual coding): bitstream syntax an HEVC decoder cannot
  parse; no encoder-side emulation exists. Slice-level cb/cr QP offsets remain the only
  conformant chroma-allocation knob.
- **Dependent Quantization** (VVC): the two-quantizer state machine is decoder-normative;
  HEVC Main10 has one dequantizer. Impossible in a conformant stream. RDOQ
  (`--rdoq-level`) is the conformant cousin and already exists.
- **Sign Data Hiding**: already an HEVC tool and already on by default in x265
  (`bEnableSignHiding`, `param.cpp:250`). Nothing to build.
- **VMAF-in-the-loop RDO**: frame-level metric with temporal features; cannot decompose
  to a per-block cost at RDO call rates. (Mode-decision metrics are encoder-side and
  decoder-safe in general — the objection is cost, not conformance.)

## Further reading

- `CONTRIBUTING.md` — a signed CLA is mandatory before any patch can be merged; covers both
  the GitHub PR flow and the `x265-devel@videolan.org` mailing-list patch flow.
- `SECURITY.md` — memory-safety issues (crash, OOB, hang on crafted input) are reported
  privately, never as a public issue.
- `doc/reST/` — user documentation: `cli.rst`, `api.rst`, `presets.rst`, `threading.rst`.
- `build/README.txt` — prerequisites and the AArch64 SVE/SVE2/DotProd/I8MM cross-compile flags.
