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
implemented strictly inside HEVC-conformant syntax (no decoder changes). Nine `x265_param`
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

### Remaining next-session priorities

1. **CAMBI into the harness + banding segment**: build/obtain libvmaf with CAMBI
   (no-reference — runs on the decode alone), add a gradient-heavy PQ segment
   (sunset/sky or synthetic ramp), then tune `--hdr-banding-protect` SCALE/clamp and
   judge `--hdr-scaling-list` / the SAO banding item with it.
2. Standing item: **subjective dark-frame pass for `--hdr-deblock`** on an HDR display.
3. If `--hdr-chroma-adapt 1.0` measures well, consider strength sweep + making it part
   of the `--hdr-pq` recommendation in the docs.

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
- [ ] **CAMBI into the harness** (libvmaf ships it) and a gradient-heavy PQ test segment
      (sunset/sky); then actually tune banding-protect's SCALE/clamp — its current ±6 QP
      at strength 1.0 costs 4 dB wPSNR-Y and is unjustified until banding is measured.
- [ ] **Exercise `--hdr-scene-qp`**: acquire or synthesize a transient-rich HDR segment
      (fireworks, flash cuts); verify the bias interacts sanely with VBV and ABR, and add
      a `rate-control-tests.txt` descriptor.
- [ ] **Derive `--hdr-scaling-list` from the PQ CSF** instead of the current arbitrary
      convex ramp; compare against HM's default intra lists as a baseline.
- [ ] **Cross-check wPSNR** against HDRTools/VTM's implementation (VTM checkout exists at
      `C:\VVCSoftware_VTM`); add DeltaE-ITP (BT.2124) as a color-aware metric.
- [ ] **Deepen HDR-VDP-3**: more sampled frames (16+), full-frame instead of 1080p crop,
      on a machine/runtime that tolerates it — current deltas are unusable for tuning.
- [ ] **cu-tree interaction**: verify the HDR per-QG offsets seeded into `qpCuTreeOffset`
      aren't double-propagated by cu-tree; test `--aq-mode 1` vs `3` with the tools on.
- [ ] **Corpus expansion**: probe `Regatta_3840x2160_HDR10_420_60p.yuv` (frame size is
      non-integral for 16-bit 4:2:0 at that resolution — format unknown), pull more
      Netflix Open Content / CableLabs 4K HDR clips; at least one natural-dark and one
      graded-bright clip per class.
- [ ] **ABR + VBV sweep** mirroring the CRF one (the RC paths differ; `hdr-scene-qp`
      applies in both B-slice and P/I branches of `rateEstimateQscale`).
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
- [ ] **Measured MaxCLL/MaxFALL → CLL SEI**: x265 already measures per-frame max/avg luma
      (`picyuv.cpp:515`, `planeClipAndMax`) and aggregates `m_maxCLL`/`m_maxFALL`
      (`encoder.cpp:3216`) but only for CSV; the SEI (`encoder.cpp:3490`) trusts user input.
      Close the loop via 2-pass (measure in pass 1, emit in pass 2 — SEI precedes frame 0).
      Fix the definition too: CTA-861.3 wants max over pixels of max(R,G,B) in *linear
      light* (nits via PQ EOTF), not max luma code level, which underestimates saturated
      colors. SEI-only, conformant, display-side benefit.
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
- [ ] **SAO banding-repair bias**: SAO band offsets can flatten a banding contour, but
      x265's SSE-driven SAO RD barely notices 1-codeword steps that glare on a PQ
      display. In banding-prone CTUs (classifier already exists in the lookahead for
      `--hdr-banding-protect`), lower SAO lambda / bias toward band-offset mode so SAO
      engages there — the post-quantization partner to the QP-side banding tool. Evaluate
      with the CAMBI item. Small, contained change in the SAO cost path.
- [x] **Luma-adaptive deblocking offsets** — implemented 2026-08-04 as
      `--hdr-deblock <float>` (`93610f195`): per-frame slice-header beta/tc overrides
      from `hdrFrameAvgLuma`, delta = round(strength · clip3(−2, 3, (400 − APL)/150)),
      on top of `--deblock` base offsets. x265 previously never used slice deblock
      overrides (PPS flag was hard-coded 0); the loop filter now reads per-slice fields.
      Verified: default path bit-identical, recon byte-equal to ffmpeg decode with
      overrides engaged. Measured 2026-08-05: wPSNR-neutral-to-slightly-positive
      (+0.2 sol / −0.7 whale vs floor). **Remaining: subjective dark-frame pass.**
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
