from __future__ import annotations

from typing import Any

import numpy as np


def ensure(ev: np.ndarray) -> np.ndarray:
    ev = np.asarray(ev, dtype=np.float64)
    if ev.ndim != 2 or ev.shape[1] < 4:
        raise ValueError("events need Nx4 [t,x,y,p]")
    return ev[:, :4]


def info(ev: np.ndarray) -> dict[str, Any]:
    ev = ensure(ev)
    if len(ev) == 0:
        return {"n": 0}
    t = ev[:, 0]
    return {
        "n": int(len(ev)),
        "t_min": float(t.min()),
        "t_max": float(t.max()),
        "duration": float(t.max() - t.min()),
        "pos_ratio": float(np.mean(ev[:, 3] > 0)),
        "mean_rate_hz": float(len(ev) / max(t.max() - t.min(), 1e-9)),
        "size_hint": [int(ev[:, 1].max()) + 1, int(ev[:, 2].max()) + 1],
    }


def sensor_size(ev: np.ndarray) -> tuple[int, int]:
    ev = ensure(ev)
    if len(ev) == 0:
        return 240, 180
    return max(int(ev[:, 1].max()) + 1, 64), max(int(ev[:, 2].max()) + 1, 64)


def accumulate(ev: np.ndarray, w: int, h: int, t0: float, t1: float, mode: str = "polarity") -> np.ndarray:
    ev = ensure(ev)
    img = np.zeros((h, w, 3), np.float32)
    sel = ev[(ev[:, 0] >= t0) & (ev[:, 0] < t1)]
    for t, x, y, p in sel:
        xi, yi = int(x), int(y)
        if not (0 <= xi < w and 0 <= yi < h):
            continue
        if mode == "count":
            img[yi, xi] += 1
        elif p > 0:
            img[yi, xi, 2] += 1
        else:
            img[yi, xi, 0] += 1
    if img.max() > 0:
        img = img / img.max() * 255
    return img.astype(np.uint8)


def time_surface(ev: np.ndarray, w: int, h: int, t_ref: float | None = None, tau: float = 0.03) -> np.ndarray:
    ev = ensure(ev)
    surf = np.zeros((h, w), np.float32)
    if len(ev) == 0:
        return np.zeros((h, w, 3), np.uint8)
    if t_ref is None:
        t_ref = float(ev[:, 0].max())
    recent = ev[ev[:, 0] >= t_ref - 5 * tau]
    for t, x, y, _ in recent:
        xi, yi = int(x), int(y)
        if 0 <= xi < w and 0 <= yi < h:
            v = np.exp(-(t_ref - t) / max(tau, 1e-6))
            if v > surf[yi, xi]:
                surf[yi, xi] = v
    g = (surf * 255).clip(0, 255).astype(np.uint8)
    return np.stack([g, g, g], -1)


def rate(ev: np.ndarray, t0: float, t1: float) -> dict[str, Any]:
    ev = ensure(ev)
    sel = ev[(ev[:, 0] >= t0) & (ev[:, 0] < t1)]
    dt = max(t1 - t0, 1e-9)
    return {
        "count": int(len(sel)),
        "rate_hz": float(len(sel) / dt),
        "pos_ratio": float(np.mean(sel[:, 3] > 0)) if len(sel) else 0.0,
    }
