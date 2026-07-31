"""本地 Zotero 对接 — 通过 Zotero 桌面端暴露的本地 HTTP API (默认 23119)。

Zotero 运行时会在 http://localhost:23119/api 暴露与 Web API v3 兼容的本地接口，
用户库记为 user 0。可列出收藏夹、检索条目、读取元数据与全文。

参考: https://www.zotero.org/support/dev/web_api/v3
本地 API 需带 header `Zotero-Allowed-Request: true`。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.settings import settings

UA = "PoseLab-ResearchAssistant/1.0 (zotero local)"


def _base() -> str:
    return settings.zotero_base_url.rstrip("/")


def _request(path: str, params: dict[str, Any] | None = None, timeout: int = 15) -> Any:
    base = _base()
    url = f"{base}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Zotero-Allowed-Request": "true",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"无法连接本地 Zotero ({base})。请确认 Zotero 桌面端已启动并开启本地 API。原因: {e.reason}"
        ) from e
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Zotero API 返回 HTTP {e.code}: {e.reason}") from e


def ping() -> dict:
    """探测本地 Zotero 是否在线。"""
    try:
        items = _request("/users/0/items", {"limit": 1, "itemType": "-attachment"})
        return {"online": True, "base": _base(), "sample": bool(items)}
    except Exception as e:  # noqa: BLE001
        return {"online": False, "base": _base(), "error": str(e)}


def collections() -> list[dict]:
    """列出所有收藏夹。"""
    data = _request("/users/0/collections", {"limit": 100})
    out = []
    for c in data:
        d = c.get("data", {})
        m = c.get("meta", {})
        out.append({
            "key": d.get("key"),
            "name": d.get("name", ""),
            "parent": d.get("parentCollection"),
            "n_items": m.get("numItems", 0),
        })
    return out


def _format_creators(creators: list[dict]) -> str:
    names = []
    for c in creators[:5]:
        n = c.get("name") or " ".join(filter(None, [c.get("firstName"), c.get("lastName")]))
        if n:
            names.append(n.strip())
    s = ", ".join(names)
    if len(creators) > 5:
        s += " et al."
    return s


def _summarize(d: dict) -> dict:
    return {
        "key": d.get("key"),
        "itemType": d.get("itemType"),
        "title": d.get("title", "") or d.get("name", ""),
        "creators": _format_creators(d.get("creators", []) or []),
        "year": (d.get("date") or "")[:4] if d.get("date") else "",
        "abstract": (d.get("abstractNote") or "")[:400],
        "doi": d.get("DOI", ""),
        "url": d.get("url", ""),
        "publication": d.get("publicationTitle") or d.get("publisher") or "",
        "tags": [t.get("tag", "") for t in (d.get("tags") or [])][:5],
    }


def search(query: str = "", collection_key: str = "", limit: int = 20, item_type: str = "") -> dict:
    """检索条目。query 为空时返回最近条目。"""
    limit = max(1, min(int(limit), 100))
    params: dict[str, Any] = {"limit": limit, "itemType": "-attachment"}
    if query:
        params["q"] = query
    if item_type:
        params["itemType"] = item_type
    path = f"/users/0/collections/{collection_key}/items" if collection_key else "/users/0/items"
    data = _request(path, params)
    items = []
    for it in data:
        d = it.get("data", {})
        if d.get("itemType") in {"attachment", "note"} and not query:
            continue
        items.append(_summarize(d))
    return {"count": len(items), "items": items}


def item(item_key: str) -> dict:
    """读取单个条目详情。"""
    data = _request(f"/users/0/items/{item_key}")
    return _summarize(data.get("data", {}))


def attachments(item_key: str) -> list[dict]:
    """列出某条目的附件（用于入库到知识库）。"""
    data = _request(f"/users/0/items/{item_key}/children", {"limit": 50})
    out = []
    for it in data:
        d = it.get("data", {})
        if d.get("itemType") == "attachment":
            out.append({
                "key": d.get("key"),
                "title": d.get("title", ""),
                "content_type": d.get("contentType", ""),
                "path": d.get("path", ""),
                "link_mode": d.get("linkMode"),
            })
    return out


def full_text(item_key: str) -> str:
    """读取条目的全文索引（若 Zotero 已建立全文索引）。"""
    try:
        data = _request(f"/users/0/items/{item_key}/full-text")
        return (data.get("content", "") or "")[:8000]
    except Exception:
        return ""


def download_attachment(attachment_key: str, timeout: int = 60) -> bytes:
    """下载某个附件条目的二进制文件（PDF 等）。
    本地 Zotero API 通常以 302 重定向到 file:// 本地存储路径，直接读取磁盘文件。"""
    base = _base()
    url = f"{base}/users/0/items/{attachment_key}/file"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "*/*",
            "Zotero-Allowed-Request": "true",
        },
    )
    # 不自动跟随重定向，手动处理 file:// 跳转
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location") or ""
        if loc.lower().startswith("file://"):
            from urllib.parse import unquote
            p = unquote(loc[len("file://"):])
            from pathlib import Path
            fp = Path(p)
            if fp.exists():
                return fp.read_bytes()
            raise RuntimeError(f"Zotero 重定向到本地文件但不存在: {p}") from e
        if e.code == 302 and loc:
            # http(s) 重定向，正常跟随
            with urllib.request.urlopen(loc, timeout=timeout) as resp:  # noqa: S310
                return resp.read()
        raise RuntimeError(
            f"下载 Zotero 附件 {attachment_key} 失败: HTTP {e.code} {e.reason}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"下载 Zotero 附件 {attachment_key} 失败: {e.reason}") from e


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 阻止自动重定向，交由上层处理（用于捕获 file:// 跳转）
        return None


def best_pdf_attachment(item_key: str) -> dict | None:
    """从条目子项中找到最佳 PDF 附件（优先 imported_file/link_mode attached）。"""
    atts = attachments(item_key)
    pdfs = [a for a in atts if "pdf" in (a.get("content_type") or "").lower()]
    if not pdfs:
        return None
    # 优先本地存储的附件（linkMode: imported_file / imported_url），避免 web 链接
    local = [a for a in pdfs if a.get("link_mode") in ("imported_file", "imported_url", "linked_file")]
    return (local or pdfs)[0]


def format_items(res: dict) -> str:
    items = res.get("items", [])
    if not items:
        return "Zotero 中未找到匹配条目。"
    lines = [f"Zotero 检索到 {res.get('count', len(items))} 条：\n"]
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. [{it.get('itemType','')}] {it.get('title','')}")
        if it.get("creators"):
            lines.append(f"   作者: {it['creators']}")
        if it.get("year"):
            lines.append(f"   年份: {it['year']} | {it.get('publication','')}")
        if it.get("abstract"):
            lines.append(f"   摘要: {it['abstract'][:180]}…")
        if it.get("doi"):
            lines.append(f"   DOI: {it['doi']}")
        lines.append(f"   key: {it.get('key')}")
        lines.append("")
    return "\n".join(lines)
