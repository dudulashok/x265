"""Orchestrate metric computation over the CRF sweep and emit results.json.

- wPSNR/PSNR: wpsnr.py per encode (sequential; ffmpeg-decode bound)
- HDR-VDP-3: prep 4 frames per encode, then Octave evals, 4 in parallel
- Bitrate from bitstream size (frames/fps known per clip)
Resumable: skips work whose outputs already exist in results.json.
"""
import os, sys, json, glob, subprocess
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
OCTAVE = os.path.join(HERE, "..", "octave-11.3.0-w64", "mingw64", "bin", "octave-cli.exe")
W, H = 3840, 2160
CLIPS = {"sol10": {"fps": 24.0, "frames": 192, "vdp_frames": [24, 72, 120, 168]},
         "whale10": {"fps": 60.0, "frames": 300, "vdp_frames": [37, 112, 187, 262]}}
CONFIGS = ["anchor", "hdrluma", "hdrpq", "wsse05", "wsse10", "wsse15", "dbk10",
           "lumaq025", "lumaq05", "lumaq075", "lumaq10", "lumaq15"]
CRFS = [22, 26, 30, 34]

results = {}
if os.path.exists("results.json"):
    results = json.load(open("results.json"))

def save():
    json.dump(results, open("results.json", "w"), indent=1)

# ---- wPSNR ----
for clip, meta in CLIPS.items():
    for cfg in CONFIGS:
        for crf in CRFS:
            key = f"{clip}_{cfg}_crf{crf}"
            hevc = f"{key}.hevc"
            if not os.path.exists(hevc):
                print("MISSING", hevc); continue
            ent = results.setdefault(key, {})
            ent["kbps"] = os.path.getsize(hevc) * 8 / (meta["frames"] / meta["fps"]) / 1000.0
            if "wpsnr_y" not in ent:
                out = subprocess.check_output(
                    [sys.executable, "wpsnr.py", f"{clip}.yuv", hevc, str(W), str(H)])
                ent.update(json.loads(out))
                print(key, "wPSNR-Y %.4f" % ent["wpsnr_y"])
                save()

if os.environ.get("WPSNR_ONLY"):
    print("METRICS_DONE (wpsnr only; run vdp_evals.sh + merge_vdp.py for HDR-VDP-3)")
    sys.exit(0)

# ---- HDR-VDP-3 prep ----
for clip, meta in CLIPS.items():
    idxs = ",".join(str(i) for i in meta["vdp_frames"])
    for cfg in CONFIGS:
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
    for cfg in CONFIGS:
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
