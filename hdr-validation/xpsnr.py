"""XPSNR (Helmrich & Bosse, ITU-T H-series supplement) via ffmpeg's xpsnr filter.

XPSNR is a perceptually weighted PSNR with spatio-temporal activity
weighting -- the metric VVenC's QPA optimises, and the P0 yardstick for
perceptual tools that wPSNR penalises by construction (see the AV1/AV2
TODO). Full-reference: input 0 is the DECODE (main), input 1 the SOURCE
(reference), matching the filter's declared input order. Frame rate
matters (the temporal-activity term uses it), so the raw source must be
fed with the clip's true fps.

Usage: python xpsnr.py <source.yuv> <encoded.hevc> <width> <height> <fps>
Prints JSON: {"xpsnr_y":, "xpsnr_cb":, "xpsnr_cr":, "xpsnr_frames":}

Notes for this harness:
- ffmpeg must have the xpsnr filter (gyan.dev 7.1+ builds do; checked 8.1.1).
- The aggregate printed at the end of the stats file / stderr is the
  spec's pooled value (from summed weighted SSDs), NOT a mean of
  per-frame dB values -- parse that, don't re-average frames.
- BOTH branches are force-tagged with setparams before the metric.
  ffmpeg 8 negotiates color range/space across a filter graph: a decoded
  HDR stream (tv/bt2020nc/smpte2084 from the VUI) against an untagged raw
  reference gets a silent YUV matrix conversion inserted on one branch,
  which costs ~7 dB luma and ~11 dB Cr of pure conversion error (measured
  2026-08-11 against a numpy ground truth; frame pairing itself was
  correct). Tagging both identically makes the two-input pipeline
  byte-exact with the sequential-read python path.
"""
import json, os, re, subprocess, sys, tempfile

FFMPEG = os.environ.get("FFMPEG", "C:/FFmpeg/bin/ffmpeg")
TAG = "setparams=range=tv:colorspace=bt2020nc:color_primaries=bt2020:color_trc=smpte2084"


def xpsnr(src_yuv, hevc, w, h, fps):
    log = tempfile.mktemp(suffix=".log", dir=".")
    try:
        proc = subprocess.run(
            [FFMPEG, "-hide_banner", "-nostats", "-y",
             "-i", hevc,
             "-f", "rawvideo", "-pix_fmt", "yuv420p10le",
             "-s", f"{w}x{h}", "-r", str(fps), "-i", src_yuv,
             "-lavfi", f"[0:v]{TAG}[m];[1:v]{TAG}[r];"
                       f"[m][r]xpsnr=stats_file={os.path.basename(log)}",
             "-f", "null", "-"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        stderr = proc.stderr.decode(errors="replace")
        frames = sum(1 for line in open(log) if line.lstrip().startswith("n:"))
    finally:
        if os.path.exists(log):
            os.remove(log)
    # summary line: "XPSNR  y: 43.1234  u: 47.5678  v: 48.9012"
    m = re.search(r"XPSNR\s+y:\s*([0-9.inf]+)\s+u:\s*([0-9.inf]+)\s+v:\s*([0-9.inf]+)",
                  stderr)
    if not m:
        raise RuntimeError("no XPSNR summary in ffmpeg output:\n" + stderr[-2000:])
    return {"xpsnr_y": float(m.group(1)),
            "xpsnr_cb": float(m.group(2)),
            "xpsnr_cr": float(m.group(3)),
            "xpsnr_frames": frames}


if __name__ == "__main__":
    a = sys.argv[1:]
    print(json.dumps(xpsnr(a[0], a[1], int(a[2]), int(a[3]), float(a[4]))))
