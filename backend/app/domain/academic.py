"""学术文献检索 — 对接公开学术 API。

参考 datawhalechina/hello-agents Co-creation-projects/chengH425-PaperAssistant 的模式，
适配本项目的工具框架（返回 JSON 字符串）。

数据源：
  - Semantic Scholar  全学科 2亿+  (graph/v1)
  - arXiv             CS/物理/数学 预印本 (Atom XML)
  - OpenAlex          全学科 2.5亿+  (REST)
  - CrossRef          期刊元数据 1.5亿+ (REST)
"""
from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

UA = "PoseLab-ResearchAssistant/1.0 (academic search)"


def _get(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def _retry(fn, retries: int = 4):
    last = None
    for i in range(retries):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < retries - 1:
                wait = _retry_after(e) or (2 ** (i + 1))
                time.sleep(min(wait, 30) + random.uniform(0, 1.5))
                continue
            if 500 <= e.code < 600 and i < retries - 1:
                time.sleep(2 ** (i + 1))
                continue
            raise
        except urllib.error.URLError as e:
            last = e
            if i < retries - 1:
                time.sleep(2 ** (i + 1))
                continue
            raise
    raise RuntimeError(f"请求失败: {last}")


def _retry_after(e: urllib.error.HTTPError) -> float | None:
    ra = e.headers.get("Retry-After") if e.headers else None
    if not ra:
        return None
    try:
        return float(ra)
    except ValueError:
        return None


# ---------- Semantic Scholar ----------
SS_FIELDS = ",".join([
    "title", "abstract", "authors", "year", "venue",
    "externalIds", "citationCount", "openAccessPdf", "fieldsOfStudy",
])
SS_BASE = "https://api.semanticscholar.org/graph/v1/paper/search"


def semantic_scholar(keyword: str, field: str = "", year_from: str = "", year_to: str = "", limit: int = 5) -> dict:
    limit = max(1, min(int(limit), 20))
    params = {"query": keyword or "spacecraft pose estimation", "limit": str(limit), "fields": SS_FIELDS}
    if field:
        params["fieldsOfStudy"] = field
    if year_from or year_to:
        params["year"] = f"{year_from or '1900'}-{year_to or '2030'}"
    url = f"{SS_BASE}?{urllib.parse.urlencode(params)}"
    headers = {}
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if api_key:
        headers["x-api-key"] = api_key
    try:
        data = json.loads(_retry(lambda: _get(url, headers=headers), retries=6).decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {"source": "semantic_scholar", "error": "Semantic Scholar 限流(429)，请稍后重试或换用 OpenAlex/arXiv", "papers": []}
        return {"source": "semantic_scholar", "error": f"HTTP {e.code}", "papers": []}
    except urllib.error.URLError as e:
        return {"source": "semantic_scholar", "error": f"网络错误: {e.reason}", "papers": []}
    papers = []
    for p in data.get("data", [])[:limit]:
        ext = p.get("externalIds") or {}
        oa = p.get("openAccessPdf") or {}
        papers.append({
            "title": p.get("title", ""),
            "authors": [a.get("name", "") for a in (p.get("authors") or [])[:5]],
            "year": p.get("year"),
            "venue": p.get("venue", ""),
            "citations": p.get("citationCount", 0),
            "abstract": (p.get("abstract") or "")[:400],
            "doi": ext.get("DOI", ""),
            "arxiv": ext.get("ArXiv", ""),
            "pdf": oa.get("url", ""),
            "fields": (p.get("fieldsOfStudy") or [])[:3],
        })
    return {"source": "semantic_scholar", "total": data.get("total", 0), "count": len(papers), "papers": papers}


# ---------- arXiv ----------
ARXIV_BASE = "http://export.arxiv.org/api/query"


def arxiv(keyword: str, author: str = "", category: str = "", limit: int = 5) -> dict:
    limit = max(1, min(int(limit), 20))
    parts = []
    if keyword:
        parts.append("+AND+".join(f"all:{t.strip()}" for t in keyword.split() if t.strip()))
    if author:
        parts.append(f'au:{author.replace(" ", "+")}')
    if category:
        parts.append(f"cat:{category.strip()}")
    query = "+AND+".join(parts) or "all:spacecraft+pose"
    url = f"{ARXIV_BASE}?search_query={query}&max_results={limit}&sortBy=relevance"
    xml_text = _retry(lambda: _get(url, timeout=15)).decode("utf-8")
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    papers = []
    for entry in root.findall("atom:entry", ns):
        title = entry.find("atom:title", ns)
        summary = entry.find("atom:summary", ns)
        published = entry.find("atom:published", ns)
        pid = entry.find("atom:id", ns)
        arxiv_id = (pid.text.split("/abs/")[-1] if pid is not None and pid.text else "")
        link = f"https://arxiv.org/abs/{arxiv_id}"
        authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns) if a.find("atom:name", ns) is not None]
        papers.append({
            "title": (title.text or "").strip().replace("\n", " ") if title is not None else "",
            "authors": authors[:5],
            "published": (published.text or "")[:10] if published is not None else "",
            "abstract": (summary.text or "").strip().replace("\n", " ")[:400] if summary is not None else "",
            "arxiv": arxiv_id,
            "pdf": f"https://arxiv.org/pdf/{arxiv_id}",
        })
    return {"source": "arxiv", "count": len(papers), "papers": papers}


# ---------- OpenAlex ----------
OA_BASE = "https://api.openalex.org/works"


def openalex(keyword: str, field: str = "", year_from: str = "", year_to: str = "", limit: int = 5) -> dict:
    limit = max(1, min(int(limit), 25))
    filt = []
    if year_from:
        filt.append(f"from_publication_date:{year_from}-01-01")
    if year_to:
        filt.append(f"to_publication_date:{year_to}-12-31")
    params = {"search": keyword or "spacecraft pose estimation", "per-page": str(limit)}
    if filt:
        params["filter"] = ",".join(filt)
    url = f"{OA_BASE}?{urllib.parse.urlencode(params)}"
    data = json.loads(_retry(lambda: _get(url)).decode("utf-8"))
    papers = []
    for w in data.get("results", [])[:limit]:
        auth = w.get("authorships") or []
        authors = [(a.get("author") or {}).get("display_name", "") for a in auth[:5]]
        ids = w.get("ids") or {}
        best = w.get("best_oa_location") or {}
        papers.append({
            "title": w.get("title") or w.get("display_name") or "",
            "authors": authors,
            "year": w.get("publication_year"),
            "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name", ""),
            "citations": w.get("cited_by_count", 0),
            "abstract": _reconstruct_abstract(w.get("abstract_inverted_index")),
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "pdf": best.get("pdf_url", "") or "",
            "fields": [c.get("display_name", "") for c in (w.get("concepts") or [])[:3] if isinstance(c, dict)],
        })
    return {"source": "openalex", "count": data.get("meta", {}).get("count", len(papers)), "papers": papers}


def _reconstruct_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            pos.append((i, word))
    pos.sort()
    return " ".join(w for _, w in pos)[:400]


# ---------- CrossRef ----------
CR_BASE = "https://api.crossref.org/works"


def crossref(keyword: str, field: str = "", year_from: str = "", limit: int = 5) -> dict:
    limit = max(1, min(int(limit), 20))
    params = {"query": keyword or "spacecraft pose estimation", "rows": str(limit)}
    if year_from:
        params["filter"] = f"from-pub-date:{year_from}"
    url = f"{CR_BASE}?{urllib.parse.urlencode(params)}"
    data = json.loads(_retry(lambda: _get(url, timeout=25)).decode("utf-8"))
    items = data.get("message", {}).get("items", [])
    papers = []
    for it in items[:limit]:
        authors = [f"{a.get('given','')} {a.get('family','')}".strip() for a in (it.get("author") or [])[:5]]
        papers.append({
            "title": (it.get("title") or [""])[0],
            "authors": authors,
            "year": (it.get("published", {}) or {}).get("date-parts", [[None]])[0][0],
            "venue": (it.get("container-title") or [""])[0],
            "citations": it.get("is-referenced-by-count", 0),
            "abstract": (it.get("abstract") or "")[:400],
            "doi": it.get("DOI", ""),
            "pdf": "",
            "fields": [],
        })
    return {"source": "crossref", "count": len(papers), "papers": papers}


# ---------- 统一入口 ----------
SOURCES = {
    "semantic_scholar": semantic_scholar,
    "arxiv": arxiv,
    "openalex": openalex,
    "crossref": crossref,
}


def search(source: str, params: dict[str, Any]) -> dict:
    source = (source or "semantic_scholar").strip().lower()
    fn = SOURCES.get(source, semantic_scholar)
    try:
        return fn(**_kwargs(source, params))
    except Exception as exc:  # noqa: BLE001
        return {"source": source, "error": str(exc), "papers": []}


def _kwargs(source: str, p: dict[str, Any]) -> dict[str, Any]:
    keyword = str(p.get("keyword") or p.get("query") or p.get("input") or "")
    limit = p.get("max_results") or p.get("limit") or 5
    try:
        limit = int(limit)
    except Exception:
        limit = 5
    k: dict[str, Any] = {"keyword": keyword, "limit": limit}
    if source == "arxiv":
        k["author"] = str(p.get("author") or "")
        k["category"] = str(p.get("category") or "")
    else:
        k["field"] = str(p.get("field") or "")
        k["year_from"] = str(p.get("year_from") or "")
        if source != "crossref":
            k["year_to"] = str(p.get("year_to") or "")
    return k


def format_results(res: dict) -> str:
    if res.get("error"):
        return f"[{res.get('source')}] 检索失败: {res['error']}"
    papers = res.get("papers", [])
    if not papers:
        return f"[{res.get('source')}] 未找到匹配论文。"
    lines = [f"[{res.get('source')}] 共 {res.get('count', len(papers))} 篇，显示 {len(papers)} 篇：\n"]
    for i, p in enumerate(papers, 1):
        auth = ", ".join(p.get("authors", [])[:3])
        if len(p.get("authors", [])) > 3:
            auth += " et al."
        lines.append(f"{i}. {p.get('title','')}")
        lines.append(f"   作者: {auth}")
        lines.append(f"   年份: {p.get('year','?')} | 引用: {p.get('citations',0)} | {p.get('venue','')}")
        if p.get("abstract"):
            lines.append(f"   摘要: {p['abstract'][:200]}…")
        links = []
        if p.get("doi"):
            links.append(f"DOI:https://doi.org/{p['doi']}")
        if p.get("arxiv"):
            links.append(f"arXiv:https://arxiv.org/abs/{p['arxiv']}")
        if p.get("pdf"):
            links.append(f"PDF:{p['pdf']}")
        if links:
            lines.append(f"   链接: {' | '.join(links)}")
        lines.append("")
    return "\n".join(lines)
