from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def stats(img: np.ndarray) -> dict[str, Any]:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return {
        "h": img.shape[0],
        "w": img.shape[1],
        "mean": float(g.mean()),
        "std": float(g.std()),
        "min": int(g.min()),
        "max": int(g.max()),
    }


def blur_score(img: np.ndarray) -> dict[str, Any]:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    v = float(cv2.Laplacian(g, cv2.CV_64F).var())
    level = "sharp" if v > 100 else ("moderate" if v > 30 else "blurry")
    return {"laplacian_var": v, "blur_level": level}


def canny(img: np.ndarray, low: int = 50, high: int = 150) -> np.ndarray:
    e = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), low, high)
    return cv2.cvtColor(e, cv2.COLOR_GRAY2BGR)


def orb(img: np.ndarray, n: int = 500) -> tuple[np.ndarray, dict[str, Any]]:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    det = cv2.ORB_create(nfeatures=n)
    kps, desc = det.detectAndCompute(g, None)
    vis = cv2.drawKeypoints(img, kps, None, flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
    return vis, {"n_keypoints": len(kps), "has_desc": desc is not None}


def orb_match(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    ga, gb = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(800)
    k1, d1 = orb.detectAndCompute(ga, None)
    k2, d2 = orb.detectAndCompute(gb, None)
    if d1 is None or d2 is None:
        return np.concatenate([a, b], 1), {"n_good_matches": 0}
    knn = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d1, d2, k=2)
    good = [m for m, n in knn if m.distance < 0.75 * n.distance][:80]
    vis = cv2.drawMatches(a, k1, b, k2, good, None, flags=2)
    return vis, {"n_good_matches": len(good), "n1": len(k1), "n2": len(k2)}


def flow(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    g1 = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    if g1.shape != g2.shape:
        g2 = cv2.resize(g2, (g1.shape[1], g1.shape[0]))
    f = cv2.calcOpticalFlowFarneback(g1, g2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    mag, ang = cv2.cartToPolar(f[..., 0], f[..., 1])
    hsv = np.zeros((*g1.shape, 3), np.uint8)
    hsv[..., 0] = ang * 90 / np.pi
    hsv[..., 1] = 255
    hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), {"mean_mag": float(mag.mean()), "p95": float(np.percentile(mag, 95))}


def solve_pnp(obj_pts: np.ndarray, img_pts: np.ndarray, K: np.ndarray) -> dict[str, Any]:
    ok, rvec, tvec = cv2.solvePnP(
        obj_pts.astype(np.float32),
        img_pts.astype(np.float32),
        K.astype(np.float32),
        np.zeros(5),
    )
    if not ok:
        return {"ok": False}
    R, _ = cv2.Rodrigues(rvec)
    return {"ok": True, "rvec": rvec.ravel().tolist(), "tvec": tvec.ravel().tolist(), "R": R.tolist()}
