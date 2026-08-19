"""Orchestrate metric computation over an encode sweep and emit results.json.

- PSNR/wPSNR: wpsnr.py per encode (sequential; ffmpeg-decode bound)
- XPSNR: xpsnr.py per encode (ffmpeg xpsnr filter; perceptual yardstick)
- Bitrate from bitstream size (frames/fps known per clip)
Resumable: skips work whose outputs already exist in results.json.
save() merges into the on-disk file rather than overwriting it, so a
concurrent metric pass is not clobbered.

Slimmed 2026-08-19 from the HDR branch's hdr-validation/metrics.py:
the CAMBI / DeltaE-ITP / HDR-VDP-3 stages are dropped -- this branch
judges general coding-efficiency tools on PSNR/wPSNR/XPSNR BD-rate and
the equal-bitrate view (rate_matched.py). If a tool needs the perceptual
stack, run it on the HDR branch's harness instead.

Encode keys are {clip}_{cfg}_crf{crf}; add new config names to CONFIGS
as arms are implemented. Encodes live next to this script as
{key}.hevc + {key}.log (the .log must contain "encoded" -- x265's
completion line -- before the encode is trusted).
"""
import os, sys, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
W, H = 3840, 2160
CONFIGS = ["anchor"]  # extend per experiment (e.g. "arf1" for hidden-ARF stage 2)
CLIPS = {"sol10": {"fps": 24.0, "frames": 192, "configs": CONFIGS},
         "whale10": {"fps": 60.0, "frames": 300, "configs": CONFIGS}}
CRFS = [22, 26, 30, 34]

results = {}
if os.path.exists("results.json"):
    results = json.load(open("results.json"))


def encode_done(key):
    """True only when the encode finished (a sweep may still be writing)."""
    try:
        return "encoded" in open(f"{key}.log").read()
    except OSError:
        return False

def save():
    cur = json.load(open("results.json")) if os.path.exists("results.json") else {}
    for k, v in results.items():
        cur.setdefault(k, {}).update(v)
    json.dump(cur, open("results.json.tmp", "w"), indent=1)
    os.replace("results.json.tmp", "results.json")

# ---- PSNR + wPSNR ----
for clip, meta in CLIPS.items():
    for cfg in meta["configs"]:
        for crf in CRFS:
            key = f"{clip}_{cfg}_crf{crf}"
            hevc = f"{key}.hevc"
            if not os.path.exists(hevc) or not encode_done(key):
                print("MISSING", hevc); continue
            ent = results.setdefault(key, {})
            ent["kbps"] = os.path.getsize(hevc) * 8 / (meta["frames"] / meta["fps"]) / 1000.0
            if "wpsnr_y" not in ent:
                out = subprocess.check_output(
                    [sys.executable, "wpsnr.py", f"{clip}.yuv", hevc, str(W), str(H)])
                ent.update(json.loads(out))
                print(key, "wPSNR-Y %.4f" % ent["wpsnr_y"])
                save()

# ---- XPSNR (perceptually weighted; see xpsnr.py for the setparams trap) ----
from xpsnr import xpsnr as xpsnr_one
for clip, meta in CLIPS.items():
    for cfg in meta["configs"]:
        for crf in CRFS:
            key = f"{clip}_{cfg}_crf{crf}"
            if key in results and os.path.exists(f"{key}.hevc") \
                    and encode_done(key) and "xpsnr_y" not in results[key]:
                results[key].update(
                    xpsnr_one(f"{clip}.yuv", f"{key}.hevc", W, H, meta["fps"]))
                print(key, "XPSNR-Y %.4f" % results[key]["xpsnr_y"])
                save()

print("METRICS_DONE")
