from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.settings import settings
from app.storage.kb import KnowledgeBase

router = APIRouter(prefix="/api/kb", tags=["knowledge"])


def _kb() -> KnowledgeBase:
    return KnowledgeBase(settings.root)


class AskIn(BaseModel):
    query: str
    top_k: int = 5


@router.get("/papers")
def list_papers():
    return {"papers": [p.__dict__ for p in _kb().list_papers()]}


@router.post("/papers")
async def ingest(file: UploadFile = File(...), tags: str = Form(""), title: str = Form("")):
    suf = Path(file.filename or "").suffix.lower()
    if suf not in {".pdf", ".md", ".txt"}:
        raise HTTPException(400, "仅支持 pdf/md/txt")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suf) as tmp:
        shutil.copyfileobj(file.file, tmp)
        path = Path(tmp.name)
    try:
        paper = _kb().ingest(path, [t.strip() for t in tags.split(",") if t.strip()], title or None)
    finally:
        path.unlink(missing_ok=True)
    return {"paper": paper.__dict__}


@router.post("/search")
def search(body: AskIn):
    hits = _kb().search(body.query, body.top_k)
    return {"hits": hits, "context": _kb().format_hits(hits)}


@router.delete("/papers/{paper_id}")
def delete_paper(paper_id: str):
    ok = _kb().delete_paper(paper_id)
    if not ok:
        raise HTTPException(404, "文献不存在")
    return {"ok": True, "paper_id": paper_id}
