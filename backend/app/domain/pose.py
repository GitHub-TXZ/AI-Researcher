from __future__ import annotations

import json
from typing import Any

import numpy as np


def qnorm(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=np.float64).reshape(4)
    n = np.linalg.norm(q)
    return q / n if n > 1e-12 else np.array([1.0, 0, 0, 0])


def quat_to_R(q: np.ndarray) -> np.ndarray:
    w, x, y, z = qnorm(q)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def parse_pose(obj: Any) -> tuple[np.ndarray, np.ndarray]:
    if isinstance(obj, str):
        obj = json.loads(obj)
    if isinstance(obj, (list, tuple)) and len(obj) >= 7:
        return qnorm(obj[:4]), np.asarray(obj[4:7], dtype=float)
    if isinstance(obj, dict):
        q = obj.get("quat") or obj.get("q")
        t = obj.get("t") or obj.get("translation") or obj.get("position")
        return qnorm(q), np.asarray(t, dtype=float)
    raise ValueError("bad pose")


def rot_err_deg(qg: np.ndarray, qp: np.ndarray) -> float:
    Re = quat_to_R(qg).T @ quat_to_R(qp)
    c = float(np.clip((np.trace(Re) - 1) / 2, -1, 1))
    return float(np.degrees(np.arccos(c)))


def sequence_errors(gt: list[Any], pred: list[Any]) -> dict[str, Any]:
    n = min(len(gt), len(pred))
    rot, trans = [], []
    for i in range(n):
        qg, tg = parse_pose(gt[i])
        qp, tp = parse_pose(pred[i])
        rot.append(rot_err_deg(qg, qp))
        trans.append(float(np.linalg.norm(tg - tp)))
    ra, ta = np.asarray(rot), np.asarray(trans)
    worst = int(np.argmax(ra)) if n else -1
    return {
        "n": n,
        "rot_mean": float(ra.mean()) if n else None,
        "trans_mean": float(ta.mean()) if n else None,
        "worst_idx": worst,
        "worst_rot_deg": float(ra[worst]) if n else None,
        "rot_err_deg": rot,
        "trans_err": trans,
    }
