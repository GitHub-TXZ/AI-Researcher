"""领域发现 / 主动推送 — 聚合 arXiv 前沿论文 + GitHub 代码仓库。

为「推送」侧栏提供数据：围绕航天器/事件相机 6DoF 位姿估计，主动检索
最新 arXiv 预印本与高星 GitHub 仓库，统一成卡片流。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

UA = "PoseLab-ResearchAssistant/1.0 (discovery)"

# 预设检索词，覆盖本课题核心方向
ARXIV_QUERIES = [
    "spacecraft pose estimation",
    "satellite pose estimation",
    "6DoF pose estimation event camera",
    "neuromorphic event camera pose",
    "monocular spacecraft relative pose",
]
GITHUB_QUERIES = [
    "spacecraft pose estimation",
    "event camera pose estimation",
    "6DoF object pose estimation",
]


def _get(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def _arxiv_feed(queries: list[str], per_query: int = 4) -> list[dict[str, Any]]:
    from app.domain import academic

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for q in queries:
        try:
            res = academic.arxiv(q, limit=per_query)
        except Exception:
            continue
        for p in res.get("papers", []):
            aid = p.get("arxiv") or p.get("title", "")
            if aid in seen:
                continue
            seen.add(aid)
            out.append({
                "type": "paper",
                "source": "arXiv",
                "title": p.get("title", ""),
                "authors": p.get("authors", [])[:4],
                "year": (p.get("published") or "")[:4] or None,
                "abstract": (p.get("abstract") or "")[:240],
                "url": f"https://arxiv.org/abs/{p.get('arxiv', '')}" if p.get("arxiv") else "",
                "pdf": p.get("pdf", ""),
                "venue": "arXiv",
                "tags": [q],
            })
    return out


def _github_feed(queries: list[str], per_query: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for q in queries:
        url = (
            "https://api.github.com/search/repositories?"
            + urllib.parse.urlencode({"q": q, "sort": "stars", "order": "desc", "per_page": per_query})
        )
        try:
            data = json.loads(_get(url, timeout=15).decode("utf-8"))
        except Exception:
            continue
        for it in data.get("items", []):
            full = it.get("full_name", "")
            if full in seen:
                continue
            seen.add(full)
            out.append({
                "type": "repo",
                "source": "GitHub",
                "title": full,
                "authors": [it.get("owner", {}).get("login", "")],
                "year": (it.get("pushed_at") or "")[:4] or None,
                "abstract": (it.get("description") or "")[:240],
                "url": it.get("html_url", ""),
                "stars": it.get("stargazers_count", 0),
                "language": it.get("language") or "",
                "venue": "GitHub",
                "tags": [q],
            })
    # 按星数降序
    out.sort(key=lambda x: x.get("stars", 0), reverse=True)
    return out


def feed(papers_per_query: int = 4, repos_per_query: int = 5) -> dict[str, Any]:
    """聚合 arXiv + GitHub，返回推送信息流。"""
    papers = _arxiv_feed(ARXIV_QUERIES, papers_per_query)
    repos = _github_feed(GITHUB_QUERIES, repos_per_query)
    # 论文按年份降序
    papers.sort(key=lambda x: x.get("year") or "", reverse=True)
    return {
        "ok": True,
        "papers": papers,
        "repos": repos,
        "n_papers": len(papers),
        "n_repos": len(repos),
    }
