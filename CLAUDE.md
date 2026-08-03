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
6. Increment `X265_BUILD` in `source/CMakeLists.txt` (currently `216`)
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
implemented strictly inside HEVC-conformant syntax (no decoder changes). Six `x265_param`
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
  content (−0.8% BD-rate on whale) but **+7.3% on dark anime** (Sol Levante) — the JVET
  dQP model assumes a brightness distribution that dark/graded content violates. This is
  the main open luma-efficiency problem.
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

### TODO — HDR quality / efficiency investigation

- [ ] **Strength sweeps** for `--hdr-luma-qp` (0.25/0.5/0.75/1.0/1.5) on both clips;
      pick a BD-rate-optimal default instead of the untested 1.0.
- [ ] **Content-adaptive luma-dQP**: attenuate or re-center the JVET model when the frame
      APL histogram is dark-dominant (fixes the Sol Levante +7.3% regression without
      giving up the whale win). The lookahead already computes `hdrFrameAvgLuma`.
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
- [ ] **wSSE-weighted RDO** (new tool, highest-value of the 2026-08 idea review): apply the
      JVET luma-dependent weight as a *distortion weight* in the RD cost instead of (or on
      top of) the `--hdr-luma-qp` QP offset — finer-grained than per-QG QP, spends no
      QP-delta bits, directly optimizes wPSNR. Plumb as a third modified-cost flavor next
      to psy-rd / `--ssim-rd` in `RDCost` (`rdcost.h`, `analysis.cpp:326`). Keep the weight
      consistent between mode-decision lambda and RDOQ lambda, and cover the SATD-based
      early-out paths. Inherits the JVET dark-content model assumption — pair with the
      content-adaptive item above. Encoder-side only, fully conformant.
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
- [ ] **MCTF temporal pre-filter** (`--mctf`, biggest single item — plan separately before
      starting): port the *concept* of HM/VTM GOP-based motion-compensated temporal
      filtering (AV1 alt-ref filtering is the same idea) into the frame-input/lookahead
      path before `calcAdaptiveQuantFrame`. Typically 2-5% BD-rate on noisy sources,
      encoder-side only, zero syntax impact. Design questions to settle in its own plan:
      filter strength per temporal layer, ME reuse from lookahead vs dedicated search,
      HIGH_BIT_DEPTH paths, frame-latency interaction with `--frame-threads`.
- [ ] **Experiments** (cheap; keep only if they measure well on the harness):
      joint-chroma RD bias (zero the weaker chroma residual when Cb/Cr anti-correlate —
      the only conformant shadow of VVC JCCR); per-luma-band RDOQ lambda (HDR-tuned
      `--rdoq-level`, folds into the wSSE weighting item).
- [ ] **Upstream prep** when results justify it: 4-config CI build check, clang-format on
      the diff, CONTRIBUTING.md CLA flow (mailing list or PR).

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
