#!/bin/bash
# Waits for the prodstack re-encode sweep, then purges the stale prodstack
# metrics and recomputes them (wPSNR + HDR-VDP-3) so all three arms of the
# three-way report come from one post-rebase binary. anchor and hdr10opt rows
# are left untouched -- they are already current (see verify_identity.out).
cd "$(dirname "$0")"
rm -f prodstack_metrics_done.marker
{
until [ -f prodstack_rerun_done.marker ]; do sleep 20; done
echo "=== encodes done, purging stale prodstack metrics $(date +%H:%M:%S)"

python - <<'PYEOF'
import json, glob, os, re
res = json.load(open("results.json"))
n = 0
for k in list(res):
    if "_prodstack_" in k:
        for f in ("kbps", "psnr_y", "psnr_cb", "psnr_cr",
                  "wpsnr_y", "wpsnr_cb", "wpsnr_cr", "vdp_jod", "vdp_n"):
            res[k].pop(f, None)
        n += 1
json.dump(res, open("results.json", "w"), indent=1)
print(f"purged metric fields from {n} prodstack rows")

keep = [l for l in open("vdp_results.txt") if "_prodstack_" not in l.split()[0]]
open("vdp_results.txt", "w").writelines(keep)
print(f"vdp_results.txt now {len(keep)} lines (prodstack entries dropped)")

g = glob.glob("vdp/t_*prodstack*.f32")
for p in g:
    os.remove(p)
print(f"removed {len(g)} stale prodstack frame dumps")
PYEOF

echo "=== wPSNR $(date +%H:%M:%S)"
WPSNR_ONLY=1 python metrics.py
echo "=== HDR-VDP-3 (prodstack only) $(date +%H:%M:%S)"
CFGS="prodstack" PAR=8 bash vdp_evals.sh
echo "=== merge + reports $(date +%H:%M:%S)"
python merge_vdp.py
{ python report_3way.py; echo; python rate_matched.py; echo; \
  python paired_jod.py; echo; python bootstrap_jod_bd.py; } \
  > report_3way_2026-08-07.txt 2>&1
echo ALL_PRODSTACK_METRICS_DONE
} > prodstack_metrics.out 2>&1 && touch prodstack_metrics_done.marker
