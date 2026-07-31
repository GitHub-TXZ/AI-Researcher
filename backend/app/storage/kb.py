from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

DIM = 256

try:
    import fitz
except ImportError:
    fitz = None


@dataclass
class Paper:
    id: str
    title: str
    filename: str
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    n_chunks: int = 0


def embed(text: str) -> np.ndarray:
    v = np.zeros(DIM, np.float32)
    toks = re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]{2,}", text.lower()) or list(text.lower())
    for tok in toks:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        v[h % DIM] += 1.0 if (h // DIM) % 2 == 0 else -1.0
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def chunk(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    out, i = [], 0
    while i < len(text):
        out.append(text[i : i + size])
        i += max(size - overlap, 1)
    return out


class KnowledgeBase:
    def __init__(self, root: Path):
        self.root = root
        self.papers_dir = root / "papers"
        self.index = root / "kb_index"
        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self.index.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.index / "papers.json"
        self.chunks_path = self.index / "chunks.jsonl"
        self.vec_path = self.index / "vectors.npy"
        self.papers: dict[str, Paper] = {}
        self.chunks: list[dict[str, Any]] = []
        self.vecs: np.ndarray = np.zeros((0, DIM), np.float32)
        self._load()

    def _load(self) -> None:
        if self.meta_path.exists():
            raw = json.loads(self.meta_path.read_text(encoding="utf-8"))
            self.papers = {k: Paper(**v) for k, v in raw.items()}
        if self.chunks_path.exists():
            self.chunks = [json.loads(l) for l in self.chunks_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if self.vec_path.exists() and self.chunks:
            self.vecs = np.load(self.vec_path)
        else:
            self._rebuild()

    def _save_meta(self) -> None:
        self.meta_path.write_text(json.dumps({k: asdict(v) for k, v in self.papers.items()}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _rebuild(self) -> None:
        if not self.chunks:
            self.vecs = np.zeros((0, DIM), np.float32)
            return
        self.vecs = np.vstack([embed(c["text"]) for c in self.chunks])
        np.save(self.vec_path, self.vecs)

    def list_papers(self) -> list[Paper]:
        return list(self.papers.values())

    def delete_paper(self, paper_id: str) -> bool:
        """删除一篇文献：移除元数据、其所有 chunks、重建向量；并删除落盘源文件。"""
        p = self.papers.pop(paper_id, None)
        if p is None:
            return False
        self.chunks = [c for c in self.chunks if c.get("paper_id") != paper_id]
        self._save_meta()
        with self.chunks_path.open("w", encoding="utf-8") as f:
            for c in self.chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        self._rebuild()
        try:
            fp = self.papers_dir / p.filename
            if fp.exists():
                fp.unlink()
        except Exception:
            pass
        return True

    def ingest(self, src: Path, tags: list[str] | None = None, title: str | None = None) -> Paper:
        suffix = src.suffix.lower()
        dest = self.papers_dir / f"{uuid.uuid4().hex}{suffix}"
        dest.write_bytes(src.read_bytes())
        if suffix == ".pdf":
            if fitz is None:
                raise RuntimeError("pymupdf required")
            doc = fitz.open(dest)
            text = "\n".join(p.get_text("text") for p in doc)
            ttl = title or (doc.metadata or {}).get("title") or src.stem
            doc.close()
        else:
            text = dest.read_text(encoding="utf-8", errors="ignore")
            ttl = title or src.stem
        pid = uuid.uuid4().hex
        rows = [{"chunk_id": f"{pid}_{i}", "paper_id": pid, "title": ttl, "text": c} for i, c in enumerate(chunk(text))]
        paper = Paper(pid, ttl, dest.name, tags or [], datetime.now(timezone.utc).isoformat(), len(rows))
        self.papers[pid] = paper
        self._save_meta()
        with self.chunks_path.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        self.chunks.extend(rows)
        self._rebuild()
        return paper

    def ingest_text(self, text: str, tags: list[str] | None = None, title: str | None = None) -> Paper:
        """直接从文本入库（不落盘源文件），用于 Zotero 等外部来源。"""
        ttl = title or "untitled"
        pid = uuid.uuid4().hex
        rows = [{"chunk_id": f"{pid}_{i}", "paper_id": pid, "title": ttl, "text": c} for i, c in enumerate(chunk(text))]
        paper = Paper(pid, ttl, f"{ttl}.txt", tags or [], datetime.now(timezone.utc).isoformat(), len(rows))
        self.papers[pid] = paper
        self._save_meta()
        with self.chunks_path.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        self.chunks.extend(rows)
        self._rebuild()
        return paper

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if len(self.chunks) == 0:
            return []
        scores = self.vecs @ embed(query)
        idx = np.argsort(-scores)[:top_k]
        out = []
        for i in idx:
            r = self.chunks[int(i)]
            out.append({**r, "score": float(scores[int(i)])})
        return out

    def format_hits(self, hits: list[dict[str, Any]]) -> str:
        if not hits:
            return "知识库无命中。"
        return "\n\n".join(f"[{i}] {h['title']} (score={h['score']:.3f})\n{h['text']}" for i, h in enumerate(hits, 1))
