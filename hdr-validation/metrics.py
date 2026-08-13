"""Orchestrate metric computation over the CRF sweep and emit results.json.

- wPSNR/PSNR: wpsnr.py per encode (sequential; ffmpeg-decode bound)
- XPSNR: xpsnr.py per encode (ffmpeg xpsnr filter; perceptual P0 metric)
- HDR-VDP-3: prep 4 frames per encode, then Octave evals, 4 in parallel
- Bitrate from bitstream size (frames/fps known per clip)
Resumable: skips work whose outputs already exist in results.json.
save() merges into the on-disk file rather than overwriting it, so a
concurrent merge_vdp.py (or a second metrics pass) is not clobbered.
"""
import os, sys, json, glob, subprocess
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
OCTAVE = os.path.join(HERE, "..", "octave-11.3.0-w64", "mingw64", "bin", "octave-cli.exe")
W, H = 3840, 2160
COMMON = ["anchor", "hdr10opt", "hdrluma", "hdrpq", "wsse05", "wsse10", "wsse15",
          "dbk10", "lumaq025", "lumaq05", "lumaq075", "lumaq10", "lumaq15",
          "chromaadapt", "prodstack",
          # 2026-08-08: VTM-derived tools (X265_BUILD 225, commit 96275df9c)
          "cascade05", "cascade10", "cascade15", "vtmlam05", "vtmlam10",
          "cqpmap10", "cqpmap10ca", "cqpmap05", "cqpmap025",
          "fixed12", "prodmap",
          # 2026-08-13: hdr-luma-qp ABR fix (zero-mean per-QG + frame bias);
          # CRF arm re-encoded to quantify the cu-tree interplay shift
          "lumaq05fix"]
# 2026-08-07: vdp_frames deepened 4 -> 12 per clip (supersets of the original
# grids sol10 24/72/120/168, whale10 37/112/187/262) so the config-to-config
# Q_JOD deltas clear the sampling noise that made the first round unusable.
CLIPS = {"sol10": {"fps": 24.0, "frames": 192,
                   "vdp_frames": [8, 24, 40, 56, 72, 88, 104, 120, 136, 152, 168, 184],
                   "configs": COMMON + ["chromaadapt05", "chromaadapt15"]},
         "whale10": {"fps": 60.0, "frames": 300,
                     "vdp_frames": [12, 37, 62, 87, 112, 137, 162, 187, 212, 237, 262, 287],
                     "configs": COMMON},
         # synthetic banding segment: judged with CAMBI (no HDR-VDP -- the
         # 4-frame Q_JOD sampling is noise on content this uniform)
         "band10": {"fps": 24.0, "frames": 96, "vdp_frames": [],
                    "configs": ["anchor", "bandp05", "bandp10", "slist",
                                "saoband10", "saoband30"],
                    "cambi": True}}
CRFS = [22, 26, 30, 34]

results = {}
if os.path.exists("results.json"):
    results = json.load(open("results.json"))


def encode_done(key):
    """True only when the encode finished (the sweep may still be writing)."""
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

# ---- wPSNR ----
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

# ---- CAMBI (banding; no-reference, decode only) ----
from cambi import cambi as cambi_one
for clip, meta in CLIPS.items():
    if not meta.get("cambi"):
        continue
    ent = results.setdefault(f"{clip}_source", {})
    if "cambi_mean" not in ent:
        ent.update(cambi_one(f"{clip}.yuv", W, H, meta["fps"]))
        print(f"{clip}_source", "CAMBI mean %.3f" % ent["cambi_mean"])
        save()
    for cfg in meta["configs"]:
        for crf in CRFS:
            key = f"{clip}_{cfg}_crf{crf}"
            if key in results and os.path.exists(f"{key}.hevc") \
                    and encode_done(key) and "cambi_mean" not in results[key]:
                results[key].update(cambi_one(f"{key}.hevc"))
                print(key, "CAMBI mean %.3f p95 %.3f" %
                      (results[key]["cambi_mean"], results[key]["cambi_p95"]))
                save()

# ---- DeltaE-ITP (BT.2124; sampled on the HDR-VDP frame grid) ----
# Chroma-relevant arms only: a 4K frame costs ~1 s in numpy so the full
# sweep is not tractable, and the luma-only arms are what wPSNR/XPSNR
# already judge. Per-frame values land in results[key]["deitp_frames"]
# keyed by frame index, pairable with the Q_JOD grid.
DEITP_CFGS = {"anchor", "hdr10opt", "hdrpq", "chromaadapt", "chromaadapt05",
              "chromaadapt15", "prodstack", "prodmap",
              "cqpmap10", "cqpmap10ca", "cqpmap05", "cqpmap025", "fixed12"}
for clip, meta in CLIPS.items():
    if not meta["vdp_frames"]:
        continue
    idxs = ",".join(str(i) for i in meta["vdp_frames"])
    for cfg in meta["configs"]:
        if cfg not in DEITP_CFGS:
            continue
        for crf in CRFS:
            key = f"{clip}_{cfg}_crf{crf}"
            if key in results and os.path.exists(f"{key}.hevc") \
                    and encode_done(key) and "deitp_mean" not in results[key]:
                out = subprocess.check_output(
                    [sys.executable, "deitp.py", f"{clip}.yuv", f"{key}.hevc",
                     str(W), str(H), idxs])
                results[key].update(json.loads(out))
                print(key, "dE-ITP %.4f" % results[key]["deitp_mean"])
                save()

if os.environ.get("WPSNR_ONLY"):
    print("METRICS_DONE (wpsnr+xpsnr+cambi only; run vdp_evals.sh + merge_vdp.py for HDR-VDP-3)")
    sys.exit(0)

# ---- HDR-VDP-3 prep ----
for clip, meta in CLIPS.items():
    idxs = ",".join(str(i) for i in meta["vdp_frames"])
    for cfg in meta["configs"]:
        for crf in CRFS:
            key = f"{clip}_{cfg}_crf{crf}"
            if not os.path.exists(f"{key}.hevc") or key not in results:
                continue
            missing = [i for i in meta["vdp_frames"]
                       if not os.path.exists(f"vdp/t_{key}_{i:04d}.f32")]
            if missing and "vdp_jod" not in results[key]:
                subprocess.check_call([sys.executable, "prep_frames.py", "hevc",
                                       f"{key}.hevc", str(W), str(H),
                                       f"vdp/t_{key}", idxs, "c1920x1080"])

# ---- HDR-VDP-3 evals (4 parallel octave processes) ----
def vdp_one(job):
    key, clip, i = job
    out = subprocess.check_output(
        [OCTAVE, "--no-init-file", "run_hdrvdp.m",
         f"vdp/t_{key}_{i:04d}.f32", f"vdp/ref_{clip}_{i:04d}.f32", "1920", "1080"],
        stderr=subprocess.DEVNULL).decode()
    line = [l for l in out.splitlines() if l.startswith("HDRVDP_Q_JOD=")][-1]
    return key, i, float(line.split()[0].split("=")[1])

jobs = []
for clip, meta in CLIPS.items():
    for cfg in meta["configs"]:
        for crf in CRFS:
            key = f"{clip}_{cfg}_crf{crf}"
            if key not in results or "vdp_jod" in results[key]:
                continue
            for i in meta["vdp_frames"]:
                if f"{key}|{i}" not in results[key].get("vdp_frames_done", {}):
                    jobs.append((key, clip, i))
print(f"{len(jobs)} hdrvdp evals to run")
with ThreadPoolExecutor(max_workers=4) as ex:
    for key, i, jod in ex.map(vdp_one, jobs):
        d = results[key].setdefault("vdp_frames_done", {})
        d[f"{key}|{i}"] = jod
        print(key, i, "Q_JOD %.4f" % jod)
        save()
for key, ent in results.items():
    d = ent.get("vdp_frames_done", {})
    if d and "vdp_jod" not in ent:
        ent["vdp_jod"] = sum(d.values()) / len(d)
        os.system(f'rm -f vdp/t_{key}_*.f32 2>/dev/null')
save()
print("METRICS_DONE")
