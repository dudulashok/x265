"""Generate flash10.yuv -- a synthetic transient-rich PQ segment to exercise
--hdr-scene-qp (2026-08-14; the tool had never seen non-steady content: both
corpus clips are temporally steady).

1920x1080 yuv420p10le, BT.2020 / SMPTE ST 2084 (PQ), limited range, 24 fps,
192 frames (8 s). Deliberately small (1080p): the tool consumes only
hdrFrameAvgLuma, so this is a rate-control testbed, not a metric-corpus clip.

Timeline (APL in 10-bit code values, targets in comments):

  f0-63    S0 night scene   ~1 nit base + small practical lights (APL ~105)
  f30-32     LIGHTNING: full-frame ~800 nits for 3 frames (APL ~650)
             -> expected bias: clipped max negative (-2 x strength), then a
             few positive frames while the polluted EMA decays back down
  f64      HARD CUT (dark->bright) -> lookahead scenecut -> re-baseline
  f64-95   S1 day scene     ~300 nits (APL ~570)
  f96-127    fade-out to ~40 nits over 32 frames (APL ~570 -> ~330)
             -> expected: small positive biases tracking the fade
  f128     HARD CUT (bright->dark, plus full spatial change)
  f128-191 S2 night scene   ~1 nit with FIREWORKS: colored expanding discs
           (~2000 nits) at f140-146, f158-164, f176-182 (APL swings ~110->250)
             -> expected: negative bias while a burst grows, positive as it
             dies, EMA recovering between bursts

All content is deterministic (seeded RNG); texture = moving sinusoids +
per-frame noise so encodes are non-trivial. TPDF dither like gen_band10.py.
"""
import numpy as np
import sys

W, H, FRAMES = 1920, 1080, 192
OUT = sys.argv[1] if len(sys.argv) > 1 else "flash10.yuv"

M1, M2 = 2610.0 / 16384, 2523.0 / 4096 * 128
C1, C2, C3 = 3424.0 / 4096, 2413.0 / 4096 * 32, 2392.0 / 4096 * 32


def pq_inv_eotf(nits):
    y = np.clip(nits / 10000.0, 0.0, 1.0)
    ym = np.power(y, M1)
    return np.power((C1 + C2 * ym) / (1.0 + C3 * ym), M2)


RNG = np.random.default_rng(20260814)


def to10b_limited(v):
    tpdf = RNG.random(v.shape) - RNG.random(v.shape)
    return np.clip(np.round(64.0 + 876.0 * v + tpdf), 0, 1023).astype(np.uint16)


yy = np.linspace(0.0, 1.0, H, dtype=np.float64)[:, None]
xx = np.linspace(0.0, 1.0, W, dtype=np.float64)[None, :]
Xp = np.arange(W, dtype=np.float64)[None, :]
Yp = np.arange(H, dtype=np.float64)[:, None]

BURSTS = [(140, 0.30, 0.35), (158, 0.65, 0.30), (176, 0.45, 0.55)]  # start, cx, cy


def scene_nits(t):
    """luma in nits + chroma offsets (cb_off, cr_off in code values, full res)"""
    cb_off = np.zeros((H, W))
    cr_off = np.zeros((H, W))
    if t < 64:                                        # S0: night
        tex = 0.4 * np.sin(2 * np.pi * (6 * xx + 0.02 * t)) * np.sin(2 * np.pi * (4 * yy))
        nits = 1.0 + 0.5 * tex + 0.3 * RNG.random((H, W))
        for (lx, ly) in [(0.2, 0.3), (0.7, 0.6), (0.5, 0.8)]:   # practical lights
            r2 = (Xp - lx * W) ** 2 + (Yp - ly * H) ** 2
            nits += 100.0 * np.exp(-r2 / (2.0 * 25.0 ** 2))
        if 30 <= t <= 32:                             # lightning
            nits = np.maximum(nits, 800.0 * (0.7 + 0.3 * RNG.random((H, W))))
            cb_off += 10.0                            # bluish flash
    elif t < 128:                                     # S1: day, fade from f96
        tex = np.sin(2 * np.pi * (3 * xx - 0.015 * t)) * np.sin(2 * np.pi * (5 * yy + 0.01 * t))
        nits = 300.0 * (1.0 + 0.25 * tex) + 20.0 * RNG.random((H, W))
        if t >= 96:
            k = (t - 96) / 31.0
            nits *= (1.0 - k) + k * (40.0 / 300.0)
        cr_off += 15.0 * (1.0 - yy)                   # warm sky
    else:                                             # S2: night + fireworks
        tex = 0.4 * np.sin(2 * np.pi * (8 * xx + 0.03 * t)) * np.cos(2 * np.pi * (6 * yy))
        nits = 1.0 + 0.5 * tex + 0.3 * RNG.random((H, W))
        for (t0, cx, cy) in BURSTS:
            if t0 <= t < t0 + 7:
                age = t - t0
                radius = 40.0 + 55.0 * age            # expanding shell
                decay = np.exp(-age / 3.0)
                r2 = (Xp - cx * W) ** 2 + (Yp - cy * H) ** 2
                disc = np.exp(-((np.sqrt(r2) - radius) ** 2) / (2.0 * 30.0 ** 2))
                nits += 2000.0 * decay * disc
                cr_off += 40.0 * decay * disc         # orange burst
                cb_off -= 25.0 * decay * disc
    return nits, cb_off, cr_off


with open(OUT, "wb") as f:
    for t in range(FRAMES):
        nits, cb_off, cr_off = scene_nits(t)
        f.write(to10b_limited(pq_inv_eotf(nits)).astype("<u2").tobytes())
        cb = 512.0 + cb_off[::2, ::2] + 4.0 * np.sin(2 * np.pi * (2 * xx[:, ::2] + yy[::2, :]))
        cr = 512.0 + cr_off[::2, ::2] - 3.0 * np.cos(2 * np.pi * (3 * xx[:, ::2] - yy[::2, :]))
        for plane in (cb, cr):
            tpdf = RNG.random(plane.shape) - RNG.random(plane.shape)
            f.write(np.clip(np.round(plane + tpdf), 64, 960).astype("<u2").tobytes())
        if t % 32 == 0:
            print(f"frame {t}/{FRAMES}", flush=True)
print(f"wrote {OUT}: {W}x{H} yuv420p10le, {FRAMES} frames")
