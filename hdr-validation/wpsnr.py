"""JVET CTC luma-weighted PSNR (wPSNR) for 10-bit 4:2:0 HDR PQ content.

Reference: JVET common test conditions for HDR (JVET-K0067 / VTM EncGOP
weighted-PSNR): per-pixel weight w = 2^(dQP/3) with
dQP(Y) = clip3(-3, 6, 0.015*Y - 1.5 - 6) for 10-bit luma Y (from the
ORIGINAL picture), wMSE = sum(w * diff^2) / N with the same N as plain
PSNR, wPSNR = 10*log10(1023^2 / wMSE). Chroma weights use the co-located
(2x2-averaged) luma weight, per VTM.

Usage: python wpsnr.py <source.yuv> <encoded.hevc> <width> <height>
Prints JSON: {frames, psnr_y, psnr_cb, psnr_cr, wpsnr_y, wpsnr_cb, wpsnr_cr}
"""
import sys, json, subprocess
import numpy as np

src_path, hevc_path, W, H = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
CW, CH = W // 2, H // 2
FRAME_WORDS = W * H * 3 // 2
FRAME_BYTES = FRAME_WORDS * 2
MAX2 = 1023.0 * 1023.0

dec = subprocess.Popen(
    ["C:/FFmpeg/bin/ffmpeg", "-v", "error", "-i", hevc_path,
     "-f", "rawvideo", "-pix_fmt", "yuv420p10le", "-"],
    stdout=subprocess.PIPE, bufsize=FRAME_BYTES * 2)

sse = np.zeros(3)   # plain SSE per plane
wsse = np.zeros(3)  # weighted SSE per plane
n = 0
with open(src_path, "rb") as srcf:
    while True:
        rec = dec.stdout.read(FRAME_BYTES)
        if len(rec) < FRAME_BYTES:
            break
        src = srcf.read(FRAME_BYTES)
        assert len(src) == FRAME_BYTES, "source shorter than reconstruction"
        s = np.frombuffer(src, dtype=np.uint16).astype(np.float64)
        r = np.frombuffer(rec, dtype=np.uint16).astype(np.float64)
        sy, scb, scr = s[:W*H], s[W*H:W*H+CW*CH], s[W*H+CW*CH:]
        ry, rcb, rcr = r[:W*H], r[W*H:W*H+CW*CH], r[W*H+CW*CH:]
        # weights from ORIGINAL luma
        dqp = np.clip(0.015 * sy - 1.5 - 6.0, -3.0, 6.0)
        wy = np.exp2(dqp / 3.0)
        # chroma weight: average of the 2x2 co-located luma weights
        wc = wy.reshape(H, W).reshape(CH, 2, CW, 2).mean(axis=(1, 3)).ravel()
        for i, (a, b, w) in enumerate(((sy, ry, wy), (scb, rcb, wc), (scr, rcr, wc))):
            d2 = (a - b) ** 2
            sse[i] += d2.sum()
            wsse[i] += (w * d2).sum()
        n += 1
dec.wait()
counts = np.array([W*H, CW*CH, CW*CH], dtype=np.float64) * n
psnr = 10 * np.log10(MAX2 * counts / sse)
wpsnr = 10 * np.log10(MAX2 * counts / wsse)
print(json.dumps({"frames": n,
                  "psnr_y": psnr[0], "psnr_cb": psnr[1], "psnr_cr": psnr[2],
                  "wpsnr_y": wpsnr[0], "wpsnr_cb": wpsnr[1], "wpsnr_cr": wpsnr[2]}))
