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

## Further reading

- `CONTRIBUTING.md` — a signed CLA is mandatory before any patch can be merged; covers both
  the GitHub PR flow and the `x265-devel@videolan.org` mailing-list patch flow.
- `SECURITY.md` — memory-safety issues (crash, OOB, hang on crafted input) are reported
  privately, never as a public issue.
- `doc/reST/` — user documentation: `cli.rst`, `api.rst`, `presets.rst`, `threading.rst`.
- `build/README.txt` — prerequisites and the AArch64 SVE/SVE2/DotProd/I8MM cross-compile flags.
