from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.domain.pose import sequence_errors
from app.domain import academic
from app.settings import settings
from app.storage.assets import AssetStore
from app.storage.kb import KnowledgeBase
from app.tools.factory import build_tools

router = APIRouter(prefix="/api", tags=["meta"])


class PoseErrIn(BaseModel):
    gt: list[Any]
    pred: list[Any]


class ToolExecIn(BaseModel):
    tool: str
    params: dict[str, Any] = {}


class AcademicSearchIn(BaseModel):
    source: str = "semantic_scholar"
    keyword: str = ""
    field: str = ""
    year_from: str = ""
    year_to: str = ""
    author: str = ""
    category: str = ""
    max_results: int = 5


@router.get("/health")
def health():
    return {"status": "ok", "version": "0.3.0"}


@router.get("/tools")
def tools():
    return {"tools": build_tools(AssetStore(settings.root), KnowledgeBase(settings.root)).catalog()}


@router.post("/analyze/pose-error")
def pose_error(body: PoseErrIn):
    return sequence_errors(body.gt, body.pred)


@router.post("/tools/exec")
def exec_tool(body: ToolExecIn):
    """Run a tool directly without LLM — for UI quick actions."""
    reg = build_tools(AssetStore(settings.root), KnowledgeBase(settings.root))
    tool = reg.get(body.tool)
    if not tool:
        return {"ok": False, "error": f"unknown tool: {body.tool}"}
    try:
        result = tool.run(body.params)
        # try to parse JSON for structured display
        try:
            parsed = json.loads(result)
            return {"ok": True, "result": parsed, "raw": result}
        except Exception:
            return {"ok": True, "result": result, "raw": result}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


@router.post("/academic/search")
def academic_search(body: AcademicSearchIn):
    """Direct academic search without LLM — for the UI search page."""
    params = body.model_dump()
    res = academic.search(body.source, params)
    return {"ok": not res.get("error"), "result": res, "formatted": academic.format_results(res)}


@router.get("/spacecraft/targets")
def spacecraft_targets():
    """列出航天器真实数据集目标，供 UI 资源库展示。"""
    from app.domain import spacecraft as sc

    return sc.list_targets()


@router.get("/spacecraft/frames")
def spacecraft_frames(target: str, limit: int = 60):
    """列出某目标的保留帧清单，供 UI 浏览。"""
    from app.domain import spacecraft as sc

    return sc.list_frames(target, limit)


@router.get("/discovery/feed")
def discovery_feed(papers_per_query: int = 4, repos_per_query: int = 5):
    """领域主动推送：聚合 arXiv 前沿论文 + GitHub 高星仓库。"""
    from app.domain import discovery

    return discovery.feed(papers_per_query, repos_per_query)
