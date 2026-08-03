"""Extract selected frames from a 10-bit 4:2:0 PQ BT.2020 source (raw yuv)
or an HEVC bitstream, convert to linear BT.2020 RGB in absolute cd/m^2
(PQ EOTF, limited-range YCbCr, NCL matrix), write planar float32 (3,H,W).

Usage:
  python prep_frames.py yuv  <in.yuv>  <W> <H> <out_prefix> <idx,idx,...> [crop]
  python prep_frames.py hevc <in.hevc> <W> <H> <out_prefix> <idx,idx,...> [crop]
crop: 'cWIDTHxHEIGHT' center crop applied after conversion, e.g. c1920x1080
"""
import sys, subprocess
import numpy as np

mode, path, W, H, prefix, idxs = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sorted(int(i) for i in sys.argv[6].split(","))
crop = None
if len(sys.argv) > 7 and sys.argv[7].startswith("c"):
    crop = tuple(int(v) for v in sys.argv[7][1:].split("x"))
FRAME_BYTES = W * H * 3  # 10-bit in 16-bit words, 4:2:0 => W*H*1.5*2

def pq_eotf(e):
    m1, m2 = 2610 / 16384, 2523 / 4096 * 128
    c1, c2, c3 = 3424 / 4096, 2413 / 4096 * 32, 2392 / 4096 * 32
    ep = np.power(np.clip(e, 0, 1), 1 / m2)
    return 10000.0 * np.power(np.maximum(ep - c1, 0) / (c2 - c3 * ep), 1 / m1)

def to_linear_rgb(frame_u16):
    y = frame_u16[:W*H].reshape(H, W).astype(np.float64)
    cb = frame_u16[W*H:W*H + W*H//4].reshape(H//2, W//2).astype(np.float64)
    cr = frame_u16[W*H + W*H//4:].reshape(H//2, W//2).astype(np.float64)
    yn = np.clip((y - 64.0) / 876.0, 0, 1)
    cbn = np.clip((cb - 512.0) / 896.0, -0.5, 0.5).repeat(2, 0).repeat(2, 1)
    crn = np.clip((cr - 512.0) / 896.0, -0.5, 0.5).repeat(2, 0).repeat(2, 1)
    r = yn + 1.4746 * crn
    b = yn + 1.8814 * cbn
    g = (yn - 0.2627 * r - 0.0593 * b) / 0.6780
    rgb = np.stack([r, g, b])                     # (3,H,W) PQ-encoded
    lin = pq_eotf(rgb)                            # absolute cd/m^2
    return np.maximum(lin, 0.005)                 # avoid zeros for log-domain metric

def emit(i, frame_u16):
    lin = to_linear_rgb(frame_u16)
    if crop:
        cw, ch = crop
        x0, y0 = (W - cw) // 2, (H - ch) // 2
        lin = lin[:, y0:y0 + ch, x0:x0 + cw]
    np.ascontiguousarray(lin, dtype=np.float32).tofile(f"{prefix}_{i:04d}.f32")
    print(f"wrote {prefix}_{i:04d}.f32")

if mode == "yuv":
    with open(path, "rb") as f:
        for i in idxs:
            f.seek(i * FRAME_BYTES)
            emit(i, np.frombuffer(f.read(FRAME_BYTES), dtype=np.uint16))
else:
    dec = subprocess.Popen(["C:/FFmpeg/bin/ffmpeg", "-v", "error", "-i", path,
                            "-f", "rawvideo", "-pix_fmt", "yuv420p10le", "-"],
                           stdout=subprocess.PIPE, bufsize=FRAME_BYTES * 2)
    want = set(idxs)
    n = 0
    while want:
        buf = dec.stdout.read(FRAME_BYTES)
        if len(buf) < FRAME_BYTES:
            break
        if n in want:
            emit(n, np.frombuffer(buf, dtype=np.uint16))
            want.discard(n)
        n += 1
    dec.kill()
    assert not want, f"frames not found: {want}"
