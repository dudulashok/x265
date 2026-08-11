"""DeltaE-ITP (ITU-R BT.2124) between source and decode, sampled frames.

The colour-aware companion to wPSNR/XPSNR: a perceptually uniform colour
difference in ICtCp space, so chroma decisions stop being judged through a
luminance proxy (the 2026-08-08 decomposition showed chroma-QP effects
reach Q_JOD only via NCL luminance leakage).

Pipeline per BT.2124/BT.2100-2: 10-bit limited-range YCbCr 4:2:0 ->
(chroma replicated to 4:4:4) -> BT.2020 NCL R'G'B' -> linear via PQ EOTF,
normalized FD/10000 -> LMS (BT.2100 integer matrix, crosstalk included)
-> PQ-encode -> ICtCp; dE_ITP = 720*sqrt(dI^2 + (0.5*dCt)^2 + dCp^2).
1 dE_ITP ~ just-noticeable at threshold. Chroma upsampling is nearest
replication -- not the BT.2020 co-siting filter, but identical on both
sides so the residual bias largely cancels; do not compare absolute
values against HDRTools without checking that choice.

Computed on SAMPLED frames (pass the clip's HDR-VDP grid so per-frame
values pair with Q_JOD): a 4K frame costs ~1-2 s in numpy, so full-clip
is not tractable across the sweep.

Usage: python deitp.py <source.yuv> <encoded.hevc> <W> <H> <idx,idx,...>
Prints JSON: {"deitp_frames": {"<idx>": mean_dE, ...}, "deitp_mean":,
              "deitp_p95_mean":}  (p95 is per-frame p95, averaged)
"""
import json, subprocess, sys
import numpy as np

M1, M2 = 2610 / 16384, 2523 / 4096 * 128
C1, C2, C3 = 3424 / 4096, 2413 / 4096 * 32, 2392 / 4096 * 32
# BT.2100-2 table 4: linear RGB -> LMS (crosstalk folded in)
RGB2LMS = np.array([[1688, 2146, 262],
                    [683, 2951, 462],
                    [99, 309, 3688]]) / 4096.0
# PQ-encoded L'M'S' -> Ct, Cp rows (I is 0.5 L' + 0.5 M')
LMS2CTCP = np.array([[6610, -13613, 7003],
                     [17933, -17390, -543]]) / 4096.0


def pq_eotf(e):                      # code [0,1] -> FD/10000 [0,1]
    ep = np.power(np.clip(e, 0, 1), 1 / M2)
    return np.power(np.maximum(ep - C1, 0) / (C2 - C3 * ep), 1 / M1)


def pq_oetf(y):                      # FD/10000 [0,1] -> code [0,1]
    yp = np.power(np.clip(y, 0, 1), M1)
    return np.power((C1 + C2 * yp) / (1 + C3 * yp), M2)


def to_itp(frame_u16, W, H):
    # float32 throughout: dE precision needs ~1e-3, and 4K float64
    # temporaries double the runtime of the sweep-wide backfill
    y = frame_u16[:W * H].reshape(H, W).astype(np.float32)
    cb = frame_u16[W * H:W * H + W * H // 4].reshape(H // 2, W // 2).astype(np.float32)
    cr = frame_u16[W * H + W * H // 4:].reshape(H // 2, W // 2).astype(np.float32)
    yn = np.clip((y - 64.0) / 876.0, 0, 1)
    cbn = np.clip((cb - 512.0) / 896.0, -0.5, 0.5).repeat(2, 0).repeat(2, 1)
    crn = np.clip((cr - 512.0) / 896.0, -0.5, 0.5).repeat(2, 0).repeat(2, 1)
    r = yn + 1.4746 * crn
    b = yn + 1.8814 * cbn
    g = (yn - 0.2627 * r - 0.0593 * b) / 0.6780
    rgb = np.clip(np.stack([r, g, b], -1), 0, 1)     # (H,W,3) PQ code
    lms = pq_oetf(pq_eotf(rgb) @ RGB2LMS.T.astype(np.float32))  # PQ-encoded LMS
    i = 0.5 * lms[..., 0] + 0.5 * lms[..., 1]
    ctcp = lms @ LMS2CTCP.T.astype(np.float32)
    return i, 0.5 * ctcp[..., 0], ctcp[..., 1]       # I, T (=Ct/2), P


def main(src_path, hevc_path, W, H, idxs):
    FB = W * H * 3                                   # bytes per 10-bit 4:2:0 frame
    per_frame, p95s = {}, []
    dec = subprocess.Popen(
        ["C:/FFmpeg/bin/ffmpeg", "-v", "error", "-i", hevc_path,
         "-f", "rawvideo", "-pix_fmt", "yuv420p10le", "-"],
        stdout=subprocess.PIPE, bufsize=FB * 2)
    want, n = set(idxs), 0
    with open(src_path, "rb") as srcf:
        while want:
            buf = dec.stdout.read(FB)
            if len(buf) < FB:
                break
            if n in want:
                srcf.seek(n * FB)
                s = np.frombuffer(srcf.read(FB), dtype=np.uint16)
                r = np.frombuffer(buf, dtype=np.uint16)
                si, st, sp = to_itp(s, W, H)
                ri, rt, rp = to_itp(r, W, H)
                de = 720.0 * np.sqrt((si - ri) ** 2 + (st - rt) ** 2 + (sp - rp) ** 2)
                per_frame[str(n)] = round(float(de.mean()), 4)
                p95s.append(float(np.percentile(de, 95)))
                want.discard(n)
            n += 1
    dec.kill()
    assert not want, f"frames not found: {want}"
    return {"deitp_frames": per_frame,
            "deitp_mean": round(sum(map(float, per_frame.values())) / len(per_frame), 4),
            "deitp_p95_mean": round(sum(p95s) / len(p95s), 4)}


if __name__ == "__main__":
    a = sys.argv[1:]
    print(json.dumps(main(a[0], a[1], int(a[2]), int(a[3]),
                          sorted(int(i) for i in a[4].split(",")))))
