from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.domain import zotero
from app.settings import settings
from app.storage.kb import KnowledgeBase

router = APIRouter(prefix="/api/zotero", tags=["zotero"])


def _kb() -> KnowledgeBase:
    return KnowledgeBase(settings.root)


class ZoteroSearchIn(BaseModel):
    query: str = ""
    collection_key: str = ""
    limit: int = 20
    item_type: str = ""


class ZoteroIngestIn(BaseModel):
    item_key: str
    tags: str = ""
    use_full_text: bool = True


class ZoteroIngestCollectionIn(BaseModel):
    collection_key: str
    use_full_text: bool = True
    limit: int = 100


@router.get("/ping")
def ping():
    return zotero.ping()


@router.get("/collections")
def collections():
    return {"collections": zotero.collections()}


@router.post("/search")
def search(body: ZoteroSearchIn):
    return zotero.search(body.query, body.collection_key, body.limit, body.item_type)


@router.get("/items/{item_key}")
def get_item(item_key: str):
    return zotero.item(item_key)


@router.get("/items/{item_key}/attachments")
def get_attachments(item_key: str):
    return {"attachments": zotero.attachments(item_key)}


@router.post("/ingest")
def ingest(body: ZoteroIngestIn):
    """把一个 Zotero 条目入库到本地知识库。
    优先下载真实 PDF 并解析全文；若无可用 PDF 则回退到元数据+摘要+全文索引。"""
    kb = _kb()
    meta = zotero.item(body.item_key)
    tag_list = [t.strip() for t in body.tags.split(",") if t.strip()] + ["zotero", meta.get("itemType", "")]
    title = meta.get("title") or f"zotero-{body.item_key}"
    paper, mode = _ingest_item(kb, body.item_key, tag_list, title, body.use_full_text)
    return {"ok": True, "paper": paper.__dict__, "source_item": meta, "mode": mode}


def _ingest_item(kb: KnowledgeBase, item_key: str, tags: list[str], title: str, use_full_text: bool):
    """真正抓取 PDF 二进制并用 PyMuPDF 解析全文入库；失败则回退到元数据+全文索引。"""
    import tempfile
    from pathlib import Path

    try:
        att = zotero.best_pdf_attachment(item_key)
        if att and att.get("key"):
            data = zotero.download_attachment(att["key"])
            if data and data[:4] == b"%PDF":
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
                    tf.write(data)
                    tmp = Path(tf.name)
                try:
                    paper = kb.ingest(tmp, tags, title)
                finally:
                    tmp.unlink(missing_ok=True)
                return paper, "pdf"
    except Exception:
        pass
    # 回退：元数据 + 摘要 + Zotero 全文索引
    meta = zotero.item(item_key)
    ft = zotero.full_text(item_key) if use_full_text else ""
    text = _item_to_text(meta, ft)
    paper = kb.ingest_text(text, tags, title)
    return paper, ("fulltext" if ft else "metadata")


def _item_to_text(meta: dict, full_text: str) -> str:
    parts = [f"# {meta.get('title','')}", ""]
    if meta.get("creators"):
        parts.append(f"作者: {meta['creators']}")
    if meta.get("year"):
        parts.append(f"年份: {meta['year']}")
    if meta.get("publication"):
        parts.append(f"出处: {meta['publication']}")
    if meta.get("doi"):
        parts.append(f"DOI: {meta['doi']}")
    if meta.get("abstract"):
        parts.append(f"\n## 摘要\n{meta['abstract']}")
    if full_text:
        parts.append(f"\n## 全文\n{full_text}")
    return "\n".join(parts)


@router.post("/ingest-collection")
def ingest_collection(body: ZoteroIngestCollectionIn):
    """按收藏夹批量导入知识库（真正抓取 PDF 解析全文）。"""
    kb = _kb()
    res = zotero.search("", body.collection_key, body.limit)
    ingested, failed = [], []
    for it in res.get("items", []):
        key = it.get("key")
        if not key:
            continue
        try:
            meta = zotero.item(key)
            tags = ["zotero", it.get("itemType", ""), body.collection_key]
            title = meta.get("title") or f"zotero-{key}"
            paper, mode = _ingest_item(kb, key, tags, title, body.use_full_text)
            ingested.append({"key": key, "title": meta.get("title", ""), "paper_id": paper.id, "mode": mode})
        except Exception as exc:  # noqa: BLE001
            failed.append({"key": key, "error": str(exc)})
    return {"ok": True, "ingested": ingested, "failed": failed, "n": len(ingested)}
