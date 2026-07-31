"""内存级（非落盘）图片存储 — 用于 Agent 可视化产物。

可视化图/GIF 不再写入磁盘，只保留在进程内存中，供对话窗口内联展示。
用户需要持久化时，通过对话里的「保存」按钮自行下载。
后端重启即清空，与「对话本身不持久化」的策略保持一致。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

import numpy as np

_LOCK = threading.Lock()
_STORE: dict[str, dict[str, Any]] = {}
# 自动过期：约 6 小时后可被回收（仅在下次访问时惰性清理）
_TTL = 6 * 3600


def _gc() -> None:
    now = time.time()
    expired = [k for k, v in _STORE.items() if now - v["ts"] > _TTL]
    for k in expired:
        _STORE.pop(k, None)


def put(img_bgr: np.ndarray, title: str, fmt: str = ".png") -> str:
    """放入一张 BGR 图像，返回 id。编码为 PNG/JPG 字节存于内存。"""
    import cv2

    ok, buf = cv2.imencode(fmt, img_bgr)
    if not ok:
        raise RuntimeError("图像编码失败")
    content_type = "image/png" if fmt == ".png" else "image/jpeg"
    return put_bytes(buf.tobytes(), content_type, title)


def put_bytes(data: bytes, content_type: str, title: str) -> str:
    """放入任意二进制（如 GIF），返回 id。"""
    with _LOCK:
        _gc()
        iid = uuid.uuid4().hex[:12]
        _STORE[iid] = {
            "data": data,
            "content_type": content_type,
            "title": title,
            "ts": time.time(),
        }
        return iid


def get(img_id: str) -> tuple[bytes, str, str] | None:
    """返回 (bytes, content_type, title)，不存在返回 None。"""
    with _LOCK:
        item = _STORE.get(img_id)
        if not item:
            return None
        return item["data"], item["content_type"], item["title"]
