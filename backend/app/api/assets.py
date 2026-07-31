from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
import tempfile
from typing import Any

from app.settings import settings
from app.storage.assets import AssetStore

router = APIRouter(prefix="/api/assets", tags=["assets"])


def _store() -> AssetStore:
    return AssetStore(settings.root)


@router.get("")
def list_assets(kind: str | None = None):
    return {"assets": [a.__dict__ for a in _store().list(kind)]}


@router.get("/{asset_id}/file")
def get_file(asset_id: str):
    try:
        return FileResponse(_store().path(asset_id))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/inline/{img_id}")
def get_inline(img_id: str):
    """从内存级 ephemeral 存储读取 Agent 可视化产物（不落盘）。"""
    from fastapi import Response
    from app.storage import ephemeral

    item = ephemeral.get(img_id)
    if not item:
        raise HTTPException(404, "图片已过期或不存在（内存级存储，重启后清空）")
    data, content_type, _title = item
    return Response(content=data, media_type=content_type)


@router.post("/upload")
async def upload(file: UploadFile = File(...), kind: str = Form(""), tags: str = Form("")):
    name = file.filename or "upload.bin"
    suf = Path(name).suffix.lower()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    if kind in {"image", "events", "pose"}:
        k = kind
    elif suf in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}:
        k = "image"
    elif suf in {".npy", ".csv"}:
        k = "events"
    elif suf == ".json":
        k = "pose"
    else:
        raise HTTPException(400, "支持: 图像 / 事件(.npy|.csv) / 姿态(.json)")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suf) as tmp:
        shutil.copyfileobj(file.file, tmp)
        path = Path(tmp.name)

    meta: dict[str, Any] = {}
    try:
        if k == "image":
            import cv2

            img = cv2.imread(str(path))
            if img is None:
                raise HTTPException(400, "无法解码图像")
            meta = {"h": int(img.shape[0]), "w": int(img.shape[1])}
        elif k == "events":
            import numpy as np

            arr = np.load(path) if suf == ".npy" else np.loadtxt(path, delimiter=",")
            arr = np.asarray(arr)
            if arr.ndim != 2 or arr.shape[1] < 4:
                raise HTTPException(400, "事件需 Nx4 [t,x,y,p]")
            meta = {"n": int(arr.shape[0])}
        a = _store().add(path, k, name, tag_list, meta)
    finally:
        path.unlink(missing_ok=True)
    return {"asset": a.__dict__}
