import { useEffect, useState } from "react";
import type { ZoteroCollection, ZoteroItem } from "../api/client";
import { zoteroCollections, zoteroIngest, zoteroIngestCollection, zoteroPing, zoteroSearch } from "../api/client";
import { IconSearch } from "./icons";

export function ZoteroPage({ onIngested }: { onIngested: () => void }) {
  const [online, setOnline] = useState<boolean | null>(null);
  const [base, setBase] = useState("");
  const [err, setErr] = useState("");
  const [collections, setCollections] = useState<ZoteroCollection[]>([]);
  const [selCol, setSelCol] = useState("");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<ZoteroItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [ingesting, setIngesting] = useState<string>("");
  const [msg, setMsg] = useState("");
  const [batching, setBatching] = useState(false);

  async function checkOnline() {
    try {
      const r = await zoteroPing();
      setOnline(r.online);
      setBase(r.base);
      setErr(r.error || "");
    } catch (e) {
      setOnline(false);
      setErr(String(e));
    }
  }

  useEffect(() => {
    checkOnline();
  }, []);

  async function loadCollections() {
    try {
      const r = await zoteroCollections();
      setCollections(r.collections);
    } catch (e) {
      setErr(String(e));
    }
  }

  async function search() {
    setBusy(true);
    setErr("");
    try {
      const r = await zoteroSearch(query.trim(), selCol, 30);
      setItems(r.items);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function ingest(item: ZoteroItem) {
    setIngesting(item.key);
    setMsg("");
    try {
      const r = await zoteroIngest(item.key, "zotero," + (item.tags || []).join(","), true);
      setMsg(`已入库：${r.paper.title}`);
      onIngested();
    } catch (e) {
      setMsg(`入库失败：${e}`);
    } finally {
      setIngesting("");
    }
  }

  async function ingestCollection(key: string, name: string) {
    if (!key) return;
    setBatching(true);
    setMsg(`正在批量导入收藏夹「${name}」…`);
    try {
      const r = await zoteroIngestCollection(key, true, 100);
      setMsg(`「${name}」导入完成：成功 ${r.n} 篇${r.failed.length ? `，失败 ${r.failed.length}` : ""}`);
      onIngested();
    } catch (e) {
      setMsg(`批量导入失败：${e}`);
    } finally {
      setBatching(false);
    }
  }

  return (
    <div className="kb-wrap">
      <div className="kb-head">
        <h1>本地 Zotero 对接</h1>
      </div>
      <div className="kb-body">
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="row between">
            <div>
              <span className={`pill ${online ? "" : "err"}`}>
                <span className="dot" />
                {online === null ? "检测中…" : online ? "Zotero 在线" : "未连接"}
              </span>
              <span className="muted" style={{ marginLeft: 10 }}>{base || "http://localhost:23119/api"}</span>
            </div>
            <button className="btn ghost sm" onClick={checkOnline}>重新检测</button>
          </div>
          {online && !collections.length && (
            <button className="btn sm" style={{ marginTop: 10 }} onClick={loadCollections}>加载收藏夹</button>
          )}
          {online && collections.length > 0 && (
            <div className="stack" style={{ marginTop: 10, gap: 6 }}>
              <div className="muted">点击收藏夹筛选检索；点「导入」一键入库整个收藏夹到知识库</div>
              <div className="row wrap" style={{ gap: 6 }}>
                <button className={`btn sm ${selCol === "" ? "" : "ghost"}`} onClick={() => setSelCol("")}>全部</button>
                {collections.map((c) => (
                  <div key={c.key} className="row" style={{ gap: 4 }}>
                    <button className={`btn sm ${selCol === c.key ? "" : "ghost"}`} onClick={() => setSelCol(c.key)}>
                      {c.name} ({c.n_items})
                    </button>
                    <button
                      className="btn ghost sm"
                      disabled={batching}
                      title="一键导入此收藏夹到知识库"
                      onClick={() => ingestCollection(c.key, c.name)}
                    >
                      导入
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
          {err && <div className="muted" style={{ color: "var(--rose)", marginTop: 8 }}>{err}</div>}
        </div>

        <div className="row" style={{ marginBottom: 12 }}>
          <input
            className="field"
            placeholder="检索 Zotero 库，如 event camera"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
          />
          <button className="btn" disabled={busy || !online} onClick={search}>
            <IconSearch width={14} height={14} /> {busy ? "检索中…" : "检索"}
          </button>
        </div>

        {msg && <div className="muted-2" style={{ marginBottom: 10 }}>{msg}</div>}

        <div className="list">
          {items.map((it) => (
            <div key={it.key} className="card">
              <div className="row between">
                <span className="badge tool">{it.itemType}</span>
                {it.year && <span className="muted">{it.year}</span>}
              </div>
              <div style={{ fontWeight: 600, marginTop: 6 }}>{it.title}</div>
              {it.creators && <div className="muted" style={{ marginTop: 3 }}>{it.creators}</div>}
              {it.publication && <div className="muted" style={{ marginTop: 2 }}>{it.publication}</div>}
              {it.abstract && <div className="muted-2" style={{ marginTop: 6 }}>{it.abstract.slice(0, 200)}…</div>}
              <div className="row between" style={{ marginTop: 8 }}>
                <div className="row wrap" style={{ gap: 10 }}>
                  {it.doi && <a className="muted-2" href={`https://doi.org/${it.doi}`} target="_blank" rel="noreferrer" style={{ color: "var(--blue)" }}>DOI ↗</a>}
                  {it.url && <a className="muted-2" href={it.url} target="_blank" rel="noreferrer" style={{ color: "var(--blue)" }}>URL ↗</a>}
                </div>
                <button className="btn sm" disabled={ingesting === it.key} onClick={() => ingest(it)}>
                  {ingesting === it.key ? "入库中…" : "入库到知识库"}
                </button>
              </div>
            </div>
          ))}
          {!items.length && online && !busy && (
            <div className="muted" style={{ textAlign: "center", padding: 24 }}>
              输入关键词检索你的 Zotero 文献库，或点击「加载收藏夹」按收藏夹浏览。检索到条目后可一键入库到本地知识库供 RAG 问答。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
