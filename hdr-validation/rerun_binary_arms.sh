#!/bin/bash
# 2026-08-08: put the hdr10opt and prodstack arms back on a binary that is
# reproducible from committed source.
#
# Background: the 2026-08-08 cmake re-run + rebuild (39806bf73, version
# 4.2+128-fb6839767) is NOT coding-identical to the binary that produced the
# published encodes -- anchor matches byte-for-byte (SEI aside) but hdr10opt
# and prodstack each differ by 11 bytes of coded data, and the tree was clean,
# so the old binary was built from uncommitted intermediate work. Impact on the
# numbers is ~1e-5 dB wPSNR, but the VTM lambda experiment will be compared
# against exactly these arms, so they must come from source in the repository.
#
# Old bitstreams are preserved as *.hevc.b20260807 (the *.prev files from the
# 2026-08-07 rerun are left alone). results.json and vdp_results.txt are backed
# up, then the 16 affected keys are purged and re-measured (wPSNR + 12-frame
# HDR-VDP-3), and the three-way reports are regenerated.
#
# Launch DETACHED (from PowerShell):
#   Start-Process -WindowStyle Hidden 'C:\Program Files\Git\bin\bash.exe' `
#     -ArgumentList '-c','C:/x265_github/x265/hdr-validation/rerun_binary_arms.sh'
# Progress: rerun_binary_arms.out ; done: rerun_binary_arms_done.marker
cd "$(dirname "$0")"
rm -f rerun_binary_arms_done.marker
{
set -u
X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
ANCHOR=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited)
PRODSTACK=(--hdr-pq --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0)
ARMS="hdr10opt prodstack"

echo "binary: $($X265 --version 2>&1 | head -1)"
echo "start: $(date)"

# ---- 0. back up the metric state we are about to invalidate ----
[ -f results-2026-08-08-prebinary.json ] || cp results.json results-2026-08-08-prebinary.json
[ -f vdp_results-2026-08-08-prebinary.txt ] || cp vdp_results.txt vdp_results-2026-08-08-prebinary.txt

# ---- 1. re-encode both arms with the current binary ----
for crf in 22 26 30 34; do
    for clipfps in "sol10.yuv 24" "whale10.yuv 60"; do
        set -- $clipfps
        clip=$1; fps=$2
        for arm in $ARMS; do
            out="${clip%.yuv}_${arm}_crf${crf}"
            if [ -f "$out.b0808.log" ] && grep -q encoded "$out.b0808.log"; then
                echo "skip $out"; continue
            fi
            [ -f "$out.hevc" ] && [ ! -f "$out.hevc.b20260807" ] && cp "$out.hevc" "$out.hevc.b20260807"
            case $arm in
                hdr10opt) ARGS=("${ANCHOR[@]}" --hdr10-opt) ;;
                prodstack) ARGS=("${PRODSTACK[@]}") ;;
            esac
            echo "=== $out $(date +%H:%M:%S)"
            "$X265" --input "$clip" --input-res 3840x2160 --fps "$fps" --input-depth 10 \
                --preset medium --crf "$crf" "${ARGS[@]}" -o "$out.hevc" 2>"$out.b0808.log"
            cp "$out.b0808.log" "$out.log"
            tail -1 "$out.b0808.log"
            echo -n "   vs previous bitstream: "
            if cmp -s "$out.hevc" "$out.hevc.b20260807"; then echo "identical"
            else echo "differs ($(stat -c%s "$out.hevc") vs $(stat -c%s "$out.hevc.b20260807") bytes)"; fi
        done
    done
done
echo "ALL_ENCODES_DONE $(date +%H:%M:%S)"

# ---- 2. purge the stale metrics for exactly these 16 keys ----
python - <<'PY'
import json, os, glob
arms = ("hdr10opt", "prodstack")
keys = [f"{c}_{a}_crf{q}" for c in ("sol10", "whale10") for a in arms for q in (22, 26, 30, 34)]
res = json.load(open("results.json"))
for k in keys:
    res.pop(k, None)
    for f in glob.glob(f"vdp/t_{k}_*.f32"):
        os.remove(f)
json.dump(res, open("results.json", "w"), indent=1)
lines = [l for l in open("vdp_results.txt") if l.split()[:1] and l.split()[0] not in keys]
open("vdp_results.txt", "w").writelines(lines)
print(f"purged {len(keys)} keys; vdp_results.txt now {len(lines)} lines")
PY

# ---- 3. wPSNR (+ kbps) ----
WPSNR_ONLY=1 python metrics.py
echo "WPSNR_DONE $(date +%H:%M:%S)"

# ---- 4. HDR-VDP-3, 12 frames per encode, 8-way parallel ----
CFGS="$ARMS" PAR=8 bash vdp_evals.sh
python merge_vdp.py
echo "VDP_DONE $(date +%H:%M:%S)"

# ---- 5. regenerate the reports (non-fatal if a script is picky) ----
python report_3way.py > report_3way_2026-08-08.txt 2>&1 || echo "report_3way FAILED"
echo "=== rate-matched (decision view) ==="
python rate_matched.py || echo "rate_matched FAILED"
echo "=== paired per-CRF Q_JOD ==="
python paired_jod.py || echo "paired_jod FAILED"

echo "ALL_RERUN_BINARY_ARMS_DONE $(date)"
} > rerun_binary_arms.out 2>&1 && touch rerun_binary_arms_done.marker
