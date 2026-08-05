"""Per-encode CAMBI (banding detector, libvmaf) via ffmpeg's libvmaf filter.

CAMBI is no-reference: it scores the DECODE alone (0 = no banding, >5 =
clearly visible; 0-24 scale). The libvmaf filter wants two inputs, so the
same stream is fed as both; the VMAF value that falls out of the self-
comparison is meaningless and discarded.

Usage:
    python cambi.py enc.hevc                     # bitstream
    python cambi.py raw.yuv 3840 2160 24         # yuv420p10le raw

Prints JSON: {"cambi_mean":, "cambi_p95":, "cambi_max":, "cambi_frames":}

Notes for this harness:
- ffmpeg must be a libvmaf-enabled build (the gyan.dev builds are).
- Default CAMBI options. To pass CAMBI options through ffmpeg's filter
  parser the colon needs quote-protection, e.g.
  feature='name=cambi\\:max_log_contrast=3' (as a literal process argument,
  no shell), and libvmaf then renames the output key (cambi_mlc_3).
"""
import json, os, subprocess, sys, tempfile

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")


def cambi(path, w=None, h=None, fps=None):
    if path.endswith(".yuv"):
        src = ["-f", "rawvideo", "-pix_fmt", "yuv420p10le",
               "-s", f"{w}x{h}", "-r", str(fps), "-i", path]
    else:
        src = ["-i", path]
    log = tempfile.mktemp(suffix=".json", dir=".")
    try:
        subprocess.check_call(
            [FFMPEG, "-hide_banner", "-nostats", "-y", *src, *src, "-lavfi",
             f"libvmaf=feature='name=cambi':log_fmt=json:log_path={os.path.basename(log)}:n_threads=16",
             "-f", "null", "-"], stderr=subprocess.DEVNULL)
        frames = json.load(open(log))["frames"]
    finally:
        if os.path.exists(log):
            os.remove(log)
    vals = sorted(f["metrics"]["cambi"] for f in frames)
    n = len(vals)
    return {"cambi_mean": round(sum(vals) / n, 4),
            "cambi_p95": round(vals[max(0, int(round(0.95 * n)) - 1)], 4),
            "cambi_max": round(vals[-1], 4),
            "cambi_frames": n}


if __name__ == "__main__":
    a = sys.argv[1:]
    print(json.dumps(cambi(a[0], *a[1:4]) if len(a) > 1 else cambi(a[0])))
