"""航天器真实数据集 (SPEED 风格) 解析与分析。

数据集结构：
  spacecraft/<target>-1-close/
    frames/NNNNN_rgb.png, NNNNN_event.png   成对 rgb / 事件累积帧
    events/events.txt                        原始事件流 t,x,y,p
    timestamps.txt                           帧时间戳 name, ts
    test.json                                landmarks_3d, intrinsics, annotations[pose,keypoints,bbox]
  spacecraft/models/<target>/               STL 零件 + dense.json 点云

提供：目标/帧/模型清单、真实 PnP 验证(对比真值姿态)、事件统计、事件累积帧。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from app.settings import settings


def _root() -> Path:
    return settings.spacecraft_root


def _targets() -> list[str]:
    root = _root()
    if not root.exists():
        return []
    out = []
    for d in sorted(root.iterdir()):
        if d.is_dir() and d.name != "models" and (d / "test.json").exists():
            out.append(d.name)
    return out


def _target_dir(target: str) -> Path:
    return _root() / target


def _load_test(target: str) -> dict:
    p = _target_dir(target) / "test.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _model_dir(target: str) -> Path:
    base = target.replace("-1-close", "")
    return _root() / "models" / base


def list_targets() -> dict:
    targets = []
    for t in _targets():
        tj = _load_test(t)
        nframes = len(tj.get("annotations", []))
        nlm = len(tj.get("landmarks_3d", []))
        mdir = _model_dir(t)
        stls = list(mdir.rglob("*.st[lL]")) if mdir.exists() else []
        dense = 0
        dj = mdir / "dense.json"
        if dj.exists():
            try:
                dense = len(json.loads(dj.read_text()).get("dense_points", []))
            except Exception:
                pass
        targets.append({
            "target": t,
            "frames": nframes,
            "landmarks_3d": nlm,
            "wireframe_points": len(tj.get("wireframe_points", [])),
            "stl_parts": len(stls),
            "dense_points": dense,
        })
    return {"source": "spacecraft", "targets": targets}


def list_frames(target: str, limit: int = 60) -> dict:
    tj = _load_test(target)
    anns = tj.get("annotations", [])[:limit]
    frames = []
    for a in anns:
        pose = np.asarray(a.get("pose", []), float)
        t = pose[:3, 3] if pose.shape == (4, 4) else np.zeros(3)
        frames.append({
            "frame": a.get("filename_rgb", "")[:5],
            "rgb": a.get("filename_rgb"),
            "event": a.get("filename_event"),
            "translation_mm": [round(float(v), 1) for v in t.tolist()],
            "depth_mm": round(float(np.linalg.norm(t)), 1),
            "bbox": a.get("bbox"),
            "n_keypoints": len(a.get("keypoints", [])),
        })
    return {"target": target, "count": len(anns), "frames": frames}


def frame_info(target: str, idx: int) -> dict:
    tj = _load_test(target)
    anns = tj.get("annotations", [])
    a = next((x for x in anns if x.get("filename_rgb", "")[:5] == f"{idx:05d}"), None)
    if a is None:
        return {"error": f"frame {idx} not found in {target}"}
    pose = np.asarray(a["pose"], float)
    K = np.asarray(tj["intrinsics"], float).reshape(3, 3) if len(tj["intrinsics"]) == 9 else None
    return {
        "target": target,
        "frame": f"{idx:05d}",
        "rgb": a.get("filename_rgb"),
        "event": a.get("filename_event"),
        "pose_R": pose[:3, :3].tolist(),
        "pose_t": pose[:3, 3].tolist(),
        "keypoints": a.get("keypoints"),
        "bbox": a.get("bbox"),
        "intrinsics": tj.get("intrinsics"),
        "n_landmarks": len(tj.get("landmarks_3d", [])),
    }


def pnp_validate(target: str, idx: int) -> dict:
    """用该帧的 landmarks_3d + keypoints + intrinsics 跑 solvePnP，与真值姿态对比。"""
    from app.domain import cv as _cv

    tj = _load_test(target)
    anns = tj.get("annotations", [])
    a = next((x for x in anns if x.get("filename_rgb", "")[:5] == f"{idx:05d}"), None)
    if a is None:
        return {"error": f"frame {idx} not found"}
    obj = np.asarray(tj["landmarks_3d"], float)
    img = np.asarray(a["keypoints"], float)
    if obj.shape[0] != img.shape[0]:
        return {"error": f"landmarks({obj.shape[0]}) != keypoints({img.shape[0]})"}
    K = np.asarray(tj["intrinsics"], float)
    if K.size == 4:  # [fx,fy,cx,cy]
        fx, fy, cx, cy = K.reshape(-1).tolist()
        K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], float)
    else:
        K = K.reshape(3, 3)
    res = _cv.solve_pnp(obj, img, K)
    if not res.get("ok"):
        return {"target": target, "frame": idx, "ok": False}
    R_pred = np.asarray(res["R"], float)
    t_pred = np.asarray(res["tvec"], float).reshape(3)
    pose_gt = np.asarray(a["pose"], float)
    R_gt = pose_gt[:3, :3]
    t_gt = pose_gt[:3, 3]
    # rotation error (deg): angle of R_gt^T R_pred
    Re = R_gt.T @ R_pred
    c = float(np.clip((np.trace(Re) - 1) / 2, -1, 1))
    rot_deg = float(np.degrees(np.arccos(c)))
    trans_err = float(np.linalg.norm(t_gt - t_pred))
    # relative translation error (% of GT depth)
    depth = float(np.linalg.norm(t_gt))
    rel_t = trans_err / depth * 100 if depth > 1e-9 else None
    return {
        "target": target,
        "frame": idx,
        "ok": True,
        "n_points": int(obj.shape[0]),
        "rot_err_deg": round(rot_deg, 3),
        "trans_err_mm": round(trans_err, 2),
        "gt_depth_mm": round(depth, 1),
        "rel_trans_err_pct": round(rel_t, 2) if rel_t is not None else None,
        "pred_t": [round(float(v), 2) for v in t_pred.tolist()],
        "gt_t": [round(float(v), 2) for v in t_gt.tolist()],
    }


def pnp_sequence(target: str, step: int = 1) -> dict:
    """对保留的全部帧批量 PnP 验证，汇总旋转/平移误差统计。"""
    tj = _load_test(target)
    anns = tj.get("annotations", [])
    rot, tr, rel = [], [], []
    for a in anns[::step]:
        r = pnp_validate(target, int(a["filename_rgb"][:5]))
        if r.get("ok"):
            rot.append(r["rot_err_deg"])
            tr.append(r["trans_err_mm"])
            if r.get("rel_trans_err_pct") is not None:
                rel.append(r["rel_trans_err_pct"])
    if not rot:
        return {"target": target, "n": 0}
    rot = np.asarray(rot)
    tr = np.asarray(tr)
    return {
        "target": target,
        "n": int(len(rot)),
        "rot_mean_deg": round(float(rot.mean()), 3),
        "rot_median_deg": round(float(np.median(rot)), 3),
        "rot_max_deg": round(float(rot.max()), 3),
        "trans_mean_mm": round(float(tr.mean()), 2),
        "trans_max_mm": round(float(tr.max()), 2),
        "rel_trans_mean_pct": round(float(np.mean(rel)), 2) if rel else None,
    }


def _load_events(target: str) -> np.ndarray:
    p = _target_dir(target) / "events" / "events.txt"
    if not p.exists():
        return np.zeros((0, 4), float)
    # 快速加载：逐行 split。文件可能数百万行，用 np.loadtxt 太慢，改用纯 python 解析。
    rows = []
    with open(p) as f:
        for line in f:
            parts = line.split(",")
            if len(parts) < 4:
                continue
            try:
                rows.append((float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])))
            except ValueError:
                continue
    return np.asarray(rows, float) if rows else np.zeros((0, 4), float)


def event_stats(target: str, max_lines: int = 200000) -> dict:
    """事件流统计（默认只读前 20 万行以快速给出概览）。"""
    p = _target_dir(target) / "events" / "events.txt"
    if not p.exists():
        return {"target": target, "error": "no events.txt"}
    t0 = t1 = None
    pos = 0
    n = 0
    xs = []
    ys = []
    with open(p) as f:
        for i, line in enumerate(f):
            if i >= max_lines:
                break
            parts = line.split(",")
            if len(parts) < 4:
                continue
            try:
                t, x, y, pol = float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])
            except ValueError:
                continue
            n += 1
            if t0 is None:
                t0 = t
            t1 = t
            pos += 1 if pol > 0 else 0
            xs.append(x)
            ys.append(y)
    if n == 0:
        return {"target": target, "n": 0}
    dur = t1 - t0 if t1 is not None and t0 is not None else 0
    return {
        "target": target,
        "sampled_events": n,
        "t_min": round(t0, 3) if t0 is not None else None,
        "t_max": round(t1, 3) if t1 is not None else None,
        "duration_us": round(dur, 3),
        "pos_ratio": round(pos / n, 3),
        "mean_rate_khz": round(n / max(dur, 1e-9) * 1000, 2),
        "sensor_size": [int(max(xs)) + 1, int(max(ys)) + 1],
    }


def event_accumulate_around(target: str, idx: int, window_us: float = 5000.0) -> np.ndarray:
    """围绕指定帧时间戳累积 window_us 微秒的事件，返回 RGB 累积图。"""
    from app.domain import events as _ev

    ev = _load_events(target)
    if len(ev) == 0:
        return np.zeros((240, 320, 3), np.uint8)
    # 取该帧时间戳
    tp = _target_dir(target) / "timestamps.txt"
    t_ref = None
    if tp.exists():
        for line in tp.read_text().splitlines():
            name, ts = line.split(",", 1)
            if name[:5] == f"{idx:05d}":
                t_ref = float(ts.strip())
                break
    if t_ref is None:
        t_ref = float(ev[:, 0].mean())
    w, h = _ev.sensor_size(ev)
    t0 = t_ref - window_us / 2
    t1 = t_ref + window_us / 2
    return _ev.accumulate(ev, w, h, t0, t1, "polarity")


def model_info(target: str) -> dict:
    mdir = _model_dir(target)
    if not mdir.exists():
        return {"target": target, "error": "no model dir"}
    stls = [str(p.relative_to(mdir)) for p in mdir.rglob("*.st[lL]")]
    dense = 0
    dj = mdir / "dense.json"
    if dj.exists():
        try:
            dense = len(json.loads(dj.read_text()).get("dense_points", []))
        except Exception:
            pass
    return {"target": target, "stl_parts": stls, "dense_points": dense}


# ---------- 高逼格可视化 ----------

# 让 matplotlib 能渲染中文（系统已装 Noto Sans CJK，但 matplotlib 字体缓存未收录，
# 故用 FontProperties(fname=) 直接加载，避免缺字形方块）
_CJK_FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def _cjk():
    import matplotlib.font_manager as fm
    try:
        return fm.FontProperties(fname=_CJK_FONT_PATH)
    except Exception:
        return None


def _fig_to_bgr(fig) -> np.ndarray:
    fig.canvas.draw()
    rgba = np.asarray(fig.canvas.buffer_rgba())
    img = rgba[:, :, :3][:, :, ::-1].copy()
    return img


def _K(target: str) -> np.ndarray:
    tj = _load_test(target)
    K = np.asarray(tj["intrinsics"], float)
    if K.size == 4:
        fx, fy, cx, cy = K.reshape(-1).tolist()
        return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], float)
    return K.reshape(3, 3)


def _annotation(target: str, idx: int) -> dict | None:
    anns = _load_test(target).get("annotations", [])
    return next((x for x in anns if x.get("filename_rgb", "")[:5] == f"{idx:05d}"), None)


def visualize_frame(target: str, idx: int) -> np.ndarray:
    """RGB 帧 + 2D 关键点(绿) + bbox(青) + 帧号叠加，返回 BGR。"""
    import cv2

    a = _annotation(target, idx)
    if a is None:
        return np.zeros((480, 640, 3), np.uint8)
    img = cv2.imread(str(_target_dir(target) / "frames" / a["filename_rgb"]))
    for (x, y) in a.get("keypoints", []):
        cv2.circle(img, (int(x), int(y)), 5, (0, 255, 0), -1, cv2.LINE_AA)
        cv2.circle(img, (int(x), int(y)), 5, (255, 255, 255), 1, cv2.LINE_AA)
    x1, y1, x2, y2 = a.get("bbox", [0, 0, 0, 0])
    cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (255, 200, 0), 2, cv2.LINE_AA)
    cv2.putText(img, f"{target} #{idx:05d}", (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    return img


def visualize_pnp_reprojection(target: str, idx: int) -> np.ndarray:
    """PnP 重投影：GT 关键点(绿) vs 重投影点(红)，连线显示误差，底部条形图显示每点像素误差。"""
    import cv2
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tj = _load_test(target)
    a = _annotation(target, idx)
    if a is None:
        return np.zeros((480, 640, 3), np.uint8)
    obj = np.asarray(tj["landmarks_3d"], float)
    img_pts = np.asarray(a["keypoints"], float)
    K = _K(target)
    res = cv2.solvePnP(obj.astype(np.float32), img_pts.astype(np.float32), K.astype(np.float32), np.zeros(5))
    ok, rvec, tvec = res
    if not ok:
        return visualize_frame(target, idx)
    proj, _ = cv2.projectPoints(obj.astype(np.float32), rvec, tvec, K.astype(np.float32), np.zeros(5))
    proj = proj.reshape(-1, 2)
    img = cv2.imread(str(_target_dir(target) / "frames" / a["filename_rgb"]))
    errs = []
    for (gx, gy), (px, py) in zip(img_pts, proj):
        cv2.circle(img, (int(gx), int(gy)), 5, (0, 255, 0), -1, cv2.LINE_AA)
        cv2.circle(img, (int(px), int(py)), 5, (0, 0, 255), -1, cv2.LINE_AA)
        cv2.line(img, (int(gx), int(gy)), (int(px), int(py)), (0, 200, 255), 1, cv2.LINE_AA)
        errs.append(float(np.hypot(gx - px, gy - py)))
    fig = plt.figure(figsize=(7, 2.4), dpi=100)
    plt.bar(range(len(errs)), errs, color="#4dd0a8")
    plt.title(f"PnP reprojection error per landmark (px)  mean={np.mean(errs):.3f}px  max={max(errs):.3f}px")
    plt.xlabel("landmark index"); plt.ylabel("px"); plt.tight_layout()
    bar = _fig_to_bgr(fig)
    plt.close(fig)
    h1 = img.shape[0]; h2 = bar.shape[0]
    canvas = np.zeros((h1 + h2 + 8, max(img.shape[1], bar.shape[1]), 3), np.uint8)
    canvas[:h1, : img.shape[1]] = img
    canvas[h1 + 8 :, : bar.shape[1]] = bar
    return canvas


def pose_trajectory(target: str) -> np.ndarray:
    """3D 真值平移轨迹 + 三视图，matplotlib 高质量图。"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    anns = _load_test(target).get("annotations", [])
    ts = np.array([np.asarray(a["pose"], float)[:3, 3] for a in anns])
    idx = np.arange(len(anns))
    fig = plt.figure(figsize=(9, 7), dpi=110)
    fig.patch.set_facecolor("#0a0e14")
    ax = fig.add_subplot(221, projection="3d")
    ax.plot(ts[:, 0], ts[:, 1], ts[:, 2], color="#4dd0a8", lw=2)
    ax.scatter(ts[:, 0], ts[:, 1], ts[:, 2], c=idx, cmap="viridis", s=30)
    ax.set_title("3D translation trajectory", color="#e6edf3")
    for s in ("x", "y", "z"):
        ax.set_facecolor("#111721")
    for ax2, (i, lab) in zip(
        [fig.add_subplot(222), fig.add_subplot(223), fig.add_subplot(224)],
        enumerate(["X (mm)", "Y (mm)", "Z (mm)"]),
    ):
        ax2.plot(idx, ts[:, i], color="#5b9cf0", lw=2, marker="o", ms=4)
        ax2.set_title(lab, color="#e6edf3"); ax2.set_facecolor("#111721")
        ax2.tick_params(colors="#9ba8b8")
        for sp in ax2.spines.values():
            sp.set_color("#252f3d")
    fig.suptitle(f"{target} — 真值姿态轨迹 ({len(anns)} 帧)", color="#e6edf3")
    fig._suptitle.set_fontproperties(_cjk())
    fig.tight_layout()
    img = _fig_to_bgr(fig)
    plt.close(fig)
    return img


def event_animation_frames(target: str, idx: int, n_frames: int = 16, window_us: float = 20000.0) -> list[np.ndarray]:
    """围绕指定帧时间戳，在 window_us 微秒内生成 n_frames 帧事件累积图（用于 GIF 动画）。"""
    from app.domain import events as _ev

    ev = _load_events(target)
    if len(ev) == 0:
        return []
    tp = _target_dir(target) / "timestamps.txt"
    t_ref = None
    if tp.exists():
        for line in tp.read_text().splitlines():
            name, ts = line.split(",", 1)
            if name[:5] == f"{idx:05d}":
                t_ref = float(ts.strip()); break
    if t_ref is None:
        t_ref = float(ev[:, 0].mean())
    w, h = _ev.sensor_size(ev)
    t0 = t_ref - window_us / 2
    dt = window_us / n_frames
    frames = []
    for i in range(n_frames):
        seg = ev[(ev[:, 0] >= t0 + i * dt) & (ev[:, 0] < t0 + (i + 1) * dt)]
        img = _ev.accumulate(seg, w, h, t0 + i * dt, t0 + (i + 1) * dt, "polarity")
        frames.append(img)
    return frames


def visualize_model_projection(target: str, idx: int, sample_step: int = 20) -> np.ndarray:
    """将 3D 密集点云用真值姿态投影到 RGB 帧上叠加（暖色点），返回 BGR。"""
    import cv2

    a = _annotation(target, idx)
    if a is None:
        return np.zeros((480, 640, 3), np.uint8)
    mdir = _model_dir(target)
    dj = mdir / "dense.json"
    if not dj.exists():
        return visualize_frame(target, idx)
    pts = np.asarray(json.loads(dj.read_text()).get("dense_points", []), float)[::sample_step]
    pose = np.asarray(a["pose"], float)
    R, t = pose[:3, :3], pose[:3, 3]
    K = _K(target)
    cam = (R @ pts.T).T + t
    z = cam[:, 2]
    valid = z > 1
    uv = (K @ cam.T).T
    uv = uv[valid][:, :2] / uv[valid][:, 2:3]
    img = cv2.imread(str(_target_dir(target) / "frames" / a["filename_rgb"]))
    for x, y in uv:
        xi, yi = int(x), int(y)
        if 0 <= xi < img.shape[1] and 0 <= yi < img.shape[0]:
            cv2.circle(img, (xi, yi), 1, (0, 180, 255), -1)
    cv2.putText(img, f"3D dense cloud projected ({len(uv)} pts)", (12, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return img


# ---------- 3D 模型 / 位姿 可视化 ----------

def _load_wireframe(target: str):
    """返回 (points Nx3, faces[list[int...]], landmarks Nx3)。"""
    tj = _load_test(target)
    pts = np.asarray(tj.get("wireframe_points", []), float)
    faces = tj.get("wireframe_faces", [])
    lm = np.asarray(tj.get("landmarks_3d", []), float)
    return pts, faces, lm


def _dark_3d_axes(ax, target: str, title: str):
    ax.set_facecolor("#0a0e14")
    for s in ax.spines.values():
        s.set_color("#252f3d")
    ax.tick_params(colors="#9ba8b8")
    ax.xaxis.label.set_color("#9ba8b8")
    ax.yaxis.label.set_color("#9ba8b8")
    ax.zaxis.label.set_color("#9ba8b8")
    ax.set_title(title, color="#e6edf3", fontsize=12)
    ax.set_xlabel("X (mm)"); ax.set_ylabel("Y (mm)"); ax.set_zlabel("Z (mm)")


def viz_3d_model(target: str, elev: float = 20, azim: float = 35) -> np.ndarray:
    """3D 模型可视化：wireframe 网格面 + 3D 关键点，可旋转视角，返回 BGR。"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    pts, faces, lm = _load_wireframe(target)
    if len(pts) == 0:
        return np.zeros((480, 640, 3), np.uint8)
    fig = plt.figure(figsize=(8, 7), dpi=110)
    fig.patch.set_facecolor("#0a0e14")
    ax = fig.add_subplot(111, projection="3d")
    polys = [pts[f] for f in faces if len(f) >= 3]
    if polys:
        pc = Poly3DCollection(polys, alpha=0.25, facecolor="#4dd0a8",
                              edgecolor="#5b9cf0", linewidths=0.3)
        ax.add_collection3d(pc)
    if len(lm):
        ax.scatter(lm[:, 0], lm[:, 1], lm[:, 2], c="#f59e0b", s=28, edgecolors="white", linewidths=0.5)
    allp = np.vstack([pts, lm]) if len(lm) else pts
    c, r = allp.mean(0), (allp.max(0) - allp.min(0)).max() / 2 + 1
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.view_init(elev=elev, azim=azim)
    _dark_3d_axes(ax, target, f"{target} — 3D 模型 (wireframe + 关键点)")
    ax.title.set_fontproperties(_cjk())
    fig.tight_layout()
    img = _fig_to_bgr(fig)
    plt.close(fig)
    return img


def viz_3d_pose(target: str, idx: int) -> np.ndarray:
    """3D 位姿可视化：模型 + 真值 6DoF 位姿坐标系(RGB 轴) + 相机视锥，返回 BGR。"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    a = _annotation(target, idx)
    if a is None:
        return np.zeros((480, 640, 3), np.uint8)
    pts, faces, lm = _load_wireframe(target)
    pose = np.asarray(a["pose"], float)
    R, t = pose[:3, :3], pose[:3, 3]
    # X_cam = R X_model + t  =>  相机在 model 坐标系的位置 C = -R^T t
    C = -R.T @ t
    # 相机三轴在 model 系的方向 = R^T 的列
    axes = R.T  # 3x3, 每列是相机 x/y/z 在 model 系方向
    fig = plt.figure(figsize=(8.5, 7), dpi=110)
    fig.patch.set_facecolor("#0a0e14")
    ax = fig.add_subplot(111, projection="3d")
    polys = [pts[f] for f in faces if len(f) >= 3]
    if polys:
        pc = Poly3DCollection(polys, alpha=0.18, facecolor="#4dd0a8",
                              edgecolor="#3a4a5a", linewidths=0.25)
        ax.add_collection3d(pc)
    if len(lm):
        ax.scatter(lm[:, 0], lm[:, 1], lm[:, 2], c="#f59e0b", s=20, edgecolors="white", linewidths=0.4)
    # 位姿坐标系（RGB 轴）画在相机处
    L = max((allp.max(0) - allp.min(0)).max() for allp in [pts] if len(pts)) * 0.25
    colors_ax = ["#ef4444", "#22c55e", "#3b82f6"]
    for k in range(3):
        end = C + axes[:, k] * L
        ax.plot([C[0], end[0]], [C[1], end[1]], [C[2], end[2]], color=colors_ax[k], lw=2.5)
    # 相机视锥（沿 -z 方向看模型）
    look = C + axes[:, 2] * (-L * 1.2)
    ax.plot([C[0], look[0]], [C[1], look[1]], [C[2], look[2]], color="#e6edf3", lw=1, ls="--")
    ax.scatter([C[0]], [C[1]], [C[2]], c="#e6edf3", s=60, marker="^", edgecolors="black")
    ax.text(C[0], C[1], C[2] + L * 0.1, "camera", color="#e6edf3", fontsize=9)
    allp = np.vstack([pts, lm, C[None]]) if len(lm) else np.vstack([pts, C[None]])
    c, r = allp.mean(0), (allp.max(0) - allp.min(0)).max() / 2 + 1
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.view_init(elev=18, azim=40)
    _dark_3d_axes(ax, target, f"{target} #{idx:05d} — 3D 真值位姿 (RGB 轴 · 相机:白)")
    ax.title.set_fontproperties(_cjk())
    fig.tight_layout()
    img = _fig_to_bgr(fig)
    plt.close(fig)
    return img


def viz_3d_rotate_frames(target: str, n_frames: int = 24, elev: float = 18) -> list[np.ndarray]:
    """3D 模型旋转动画：绕不同方位角生成 n_frames 帧，用于 GIF。"""
    frames = []
    for i in range(n_frames):
        azim = 360.0 * i / n_frames
        frames.append(viz_3d_model(target, elev=elev, azim=azim))
    return frames


# ---------- 光学图像同时可视化 ----------

def _overlay_frame(target: str, idx: int, with_kp: bool = True) -> np.ndarray:
    """加载某帧 RGB 并叠加关键点+bbox+帧号，返回 BGR。"""
    import cv2

    a = _annotation(target, idx)
    if a is None:
        return np.zeros((480, 640, 3), np.uint8)
    img = cv2.imread(str(_target_dir(target) / "frames" / a["filename_rgb"]))
    if with_kp:
        for (x, y) in a.get("keypoints", []):
            cv2.circle(img, (int(x), int(y)), 4, (0, 255, 0), -1, cv2.LINE_AA)
    x1, y1, x2, y2 = a.get("bbox", [0, 0, 0, 0])
    cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (255, 200, 0), 2, cv2.LINE_AA)
    cv2.rectangle(img, (0, 0), (160, 30), (0, 0, 0), -1)
    cv2.putText(img, f"#{idx:05d}", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    return img


def viz_optical_montage(target: str, n: int = 9, cols: int = 3) -> np.ndarray:
    """光学图像同时可视化：在一张大图里平铺多个 RGB 帧（含关键点+bbox+帧号），
    默认跨序列均匀采样 9 帧、3 列。返回 BGR。"""
    import cv2

    anns = _load_test(target).get("annotations", [])
    if not anns:
        return np.zeros((480, 640, 3), np.uint8)
    total = len(anns)
    n = max(1, min(int(n), total))
    idxs = [int(round(i * (total - 1) / max(n - 1, 1))) for i in range(n)]
    cells = [_overlay_frame(target, i) for i in idxs]
    # 统一尺寸到最小宽高，保证可拼接
    h = min(c.shape[0] for c in cells)
    w = min(c.shape[1] for c in cells)
    cells = [cv2.resize(c, (w, h)) for c in cells]
    pad = 8
    pad_color = (20, 24, 32)
    rows = (len(cells) + cols - 1) // cols
    # 补齐到完整网格
    while len(cells) < rows * cols:
        cells.append(np.full((h, w, 3), pad_color[0], np.uint8))
    grid_rows = []
    for r in range(rows):
        row_cells = cells[r * cols:(r + 1) * cols]
        row = row_cells[0]
        for c in row_cells[1:]:
            row = np.hstack([row, np.full((h, pad, 3), pad_color[0], np.uint8), c])
        grid_rows.append(row)
    grid = grid_rows[0]
    for gr in grid_rows[1:]:
        grid = np.vstack([grid, np.full((pad, grid.shape[1], 3), pad_color[0], np.uint8), gr])
    # 顶部标题条
    title_h = 34
    title = np.full((title_h, grid.shape[1], 3), pad_color[0], np.uint8)
    cv2.putText(title, f"{target} — optical frames montage ({n}/{total} frames, keypoints+bbox)",
                (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (230, 237, 243), 1, cv2.LINE_AA)
    grid = np.vstack([title, grid])
    return grid


def viz_optical_event_pair(target: str, idx: int) -> np.ndarray:
    """光学+事件同时可视化：同一帧的 RGB 与事件累积帧左右并排，返回 BGR。"""
    import cv2

    a = _annotation(target, idx)
    if a is None:
        return np.zeros((480, 640, 3), np.uint8)
    rgb = cv2.imread(str(_target_dir(target) / "frames" / a["filename_rgb"]))
    evt = cv2.imread(str(_target_dir(target) / "frames" / a["filename_event"]))
    if evt is None or evt.size == 0:
        evt = np.zeros_like(rgb)
    # 统一高度
    h = min(rgb.shape[0], evt.shape[0])
    rgb = cv2.resize(rgb, (int(rgb.shape[1] * h / rgb.shape[0]), h))
    evt = cv2.resize(evt, (int(evt.shape[1] * h / evt.shape[0]), h))
    gap = np.full((h, 10, 3), (20, 24, 32), np.uint8)
    cv2.putText(rgb, "RGB (optical)", (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(evt, "event", (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    pair = np.hstack([rgb, gap, evt])
    title = np.full((30, pair.shape[1], 3), (20, 24, 32), np.uint8)
    cv2.putText(title, f"{target} #{idx:05d} — optical vs event", (12, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (230, 237, 243), 1, cv2.LINE_AA)
    return np.vstack([title, pair])
