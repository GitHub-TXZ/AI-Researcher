from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np

Kind = Literal["image", "events", "pose", "other"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Asset:
    id: str
    kind: Kind
    filename: str
    path: str
    created_at: str
    tags: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


class AssetStore:
    def __init__(self, root: Path):
        self.root = root
        self.dir = root / "uploads" / "assets"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.catalog = root / "uploads" / "catalog.json"
        self.items: dict[str, Asset] = {}
        if self.catalog.exists():
            raw = json.loads(self.catalog.read_text(encoding="utf-8") or "{}")
            self.items = {k: Asset(**v) for k, v in raw.items()}

    def _save(self) -> None:
        self.catalog.write_text(
            json.dumps({k: asdict(v) for k, v in self.items.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list(self, kind: str | None = None) -> list[Asset]:
        xs = list(self.items.values())
        if kind:
            xs = [x for x in xs if x.kind == kind]
        return sorted(xs, key=lambda a: a.created_at, reverse=True)

    def get(self, asset_id: str) -> Asset:
        if asset_id not in self.items:
            raise FileNotFoundError(asset_id)
        return self.items[asset_id]

    def path(self, asset_id: str) -> Path:
        return Path(self.get(asset_id).path)

    def add(self, src: Path, kind: Kind, filename: str, tags: list[str] | None = None, meta: dict | None = None) -> Asset:
        aid = uuid.uuid4().hex[:12]
        dest = self.dir / f"{aid}{Path(filename).suffix.lower() or src.suffix}"
        shutil.copy2(src, dest)
        a = Asset(aid, kind, filename, str(dest), _now(), tags or [], meta or {})
        self.items[aid] = a
        self._save()
        return a

    def save_image(self, img_bgr: np.ndarray, prefix: str, tags: list[str] | None = None) -> Asset:
        import cv2

        aid = uuid.uuid4().hex[:12]
        dest = self.dir / f"{aid}_{prefix}.png"
        cv2.imwrite(str(dest), img_bgr)
        a = Asset(aid, "image", dest.name, str(dest), _now(), (tags or []) + ["tool_output"], {"from": prefix})
        self.items[aid] = a
        self._save()
        return a

    def load_image(self, asset_id: str) -> np.ndarray:
        import cv2

        img = cv2.imread(str(self.path(asset_id)))
        if img is None:
            raise ValueError(f"bad image {asset_id}")
        return img

    def load_events(self, asset_id: str) -> np.ndarray:
        p = self.path(asset_id)
        if p.suffix.lower() == ".npy":
            arr = np.load(p)
        else:
            arr = np.loadtxt(p, delimiter=",")
        arr = np.asarray(arr, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[1] < 4:
            raise ValueError("events Nx4 required")
        return arr[:, :4]

    def load_json(self, asset_id: str) -> Any:
        return json.loads(self.path(asset_id).read_text(encoding="utf-8"))
