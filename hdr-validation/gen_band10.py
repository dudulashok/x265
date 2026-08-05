"""Generate band10.yuv -- a synthetic gradient-heavy PQ banding test segment.

3840x2160 yuv420p10le, BT.2020 / SMPTE ST 2084 (PQ), limited range, 24 fps,
96 frames (4 s). A "sunset sky" built entirely from smooth gradients in
linear light (nits), converted through the PQ inverse EOTF:

- vertical sky ramp, dark zenith (~0.05 nits) to bright horizon (~200 nits)
- wide radial sun glow (up to +300 nits, sigma ~900 px) drifting slowly
  horizontally (classic slow-pan banding case)
- dark "sea" below the horizon (~2-8 nits) with a horizontal gradient
- slow global brightness ramp (+/-5% over the segment, fade-like)
- gentle chroma gradients (bluish zenith -> orange horizon), small amplitude

The float image is TPDF-dithered (+/-1 code, seeded RNG -- deterministic)
before 10-bit rounding, like a real mastered deliverable: without dither the
10-bit source itself bands (measured CAMBI ~4.0, and a CRF34 encode scored
LOWER than the source). With dither the source scores near zero and lossy
encodes strip the dither and reintroduce banding -- that gap is what the
segment measures.
"""
import numpy as np
import sys

W, H, FRAMES = 3840, 2160, 96
OUT = sys.argv[1] if len(sys.argv) > 1 else "band10.yuv"

M1, M2 = 2610.0 / 16384, 2523.0 / 4096 * 128
C1, C2, C3 = 3424.0 / 4096, 2413.0 / 4096 * 32, 2392.0 / 4096 * 32


def pq_inv_eotf(nits):
    """linear cd/m^2 -> PQ non-linear value V in [0,1]"""
    y = np.clip(nits / 10000.0, 0.0, 1.0)
    ym = np.power(y, M1)
    return np.power((C1 + C2 * ym) / (1.0 + C3 * ym), M2)


RNG = np.random.default_rng(20260805)


def to10b_limited(v, lo=64.0, span=876.0):
    tpdf = RNG.random(v.shape) - RNG.random(v.shape)   # triangular, +/-1 code
    return np.clip(np.round(lo + span * v + tpdf), 0, 1023).astype(np.uint16)


yy = np.linspace(0.0, 1.0, H, dtype=np.float64)[:, None]   # 0 top -> 1 bottom
xx = np.linspace(0.0, 1.0, W, dtype=np.float64)[None, :]
HORIZON = 0.68                                             # sky/sea split

with open(OUT, "wb") as f:
    for t in range(FRAMES):
        ft = t / (FRAMES - 1.0)
        # sky: log-space ramp 0.05 -> 200 nits, zenith to horizon
        skypos = np.clip(yy / HORIZON, 0.0, 1.0)
        log_nits = np.log10(0.05) + (np.log10(200.0) - np.log10(0.05)) * skypos**1.6
        nits = 10.0**log_nits
        # sea: 2 -> 8 nits with a horizontal gradient, below the horizon
        sea = 2.0 + 6.0 * xx + 0.0 * yy
        below = (yy > HORIZON)
        depth = np.clip((yy - HORIZON) / (1.0 - HORIZON), 0.0, 1.0)
        nits = np.where(below, sea * (1.0 - 0.75 * depth), nits)
        # drifting sun glow centered on the horizon
        sun_x = (0.35 + 0.10 * ft) * W
        sun_y = HORIZON * H
        gx = (np.arange(W, dtype=np.float64)[None, :] - sun_x)
        gy = (np.arange(H, dtype=np.float64)[:, None] - sun_y)
        r2 = gx * gx + gy * gy
        glow = 300.0 * np.exp(-r2 / (2.0 * 900.0**2))
        nits = nits + glow
        # slow global fade: 1.05 -> 0.95 over the segment
        nits = nits * (1.05 - 0.10 * ft)

        y10 = to10b_limited(pq_inv_eotf(nits))
        f.write(y10.astype("<u2").tobytes())

        # chroma at half res: bluish zenith -> orange horizon, small amplitude
        cyy = yy[::2, :]
        cxx = xx[:, ::2]
        skyc = np.clip(cyy / HORIZON, 0.0, 1.0)
        cb = 512.0 + 55.0 * (1.0 - skyc) - 25.0 * skyc + 0.0 * cxx
        cr = 512.0 - 20.0 * (1.0 - skyc) + 45.0 * skyc + 0.0 * cxx
        seac = (cyy > HORIZON)
        cb = np.where(seac, 512.0 + 18.0 * (1.0 - cxx), cb)
        cr = np.where(seac, 512.0 - 10.0 + 0.0 * cxx, cr)
        for plane in (cb, cr):
            tpdf = RNG.random(plane.shape) - RNG.random(plane.shape)
            f.write(np.clip(np.round(plane + tpdf), 64, 960).astype("<u2").tobytes())
        if t % 16 == 0:
            print(f"frame {t}/{FRAMES}", flush=True)
print(f"wrote {OUT}: {W}x{H} yuv420p10le, {FRAMES} frames")
