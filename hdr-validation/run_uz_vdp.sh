#!/bin/bash
# HDR-VDP-3 pass for the ultrafast+zerolatency sweep keys (2026-08-27):
# space-free Start-Process-safe wrapper around vdp_evals_modes.sh (the env
# must live in the script — PS 5.1 -ArgumentList does not quote args with
# spaces). Progress: vdp_modes_progress.out ; marker vdp_modes_done.marker
export CFGS="anchor prodmap"
export MODES="uzvbv uzccrf"
exec "$(dirname "$0")/vdp_evals_modes.sh"
