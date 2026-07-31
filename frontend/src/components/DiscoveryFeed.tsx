import { useEffect, useState } from "react";
import { getDiscoveryFeed } from "../api/client";
import type { DiscoveryItem } from "../api/client";

function ItemCard({ it }: { it: DiscoveryItem }) {
  const isRepo = it.type === "repo";
  return (
    <a className="df-card" href={it.url} target="_blank" rel="noreferrer">
      <div className="df-card-head">
        <span className={`df-tag ${isRepo ? "repo" : "paper"}`}>{isRepo ? "GitHub" : it.source}</span>
        <span className="df-meta">
          {isRepo ? `★ ${it.stars ?? 0}` : it.year || ""}
          {isRepo && it.language ? ` · ${it.language}` : ""}
        </span>
      </div>
      <div className="df-title">{it.title}</div>
      {it.authors?.length > 0 && (
        <div className="df-authors">{it.authors.filter(Boolean).join(", ")}</div>
      )}
      {it.abstract && <div className="df-abstract">{it.abstract}</div>}
    </a>
  );
}

export function DiscoveryFeed() {
  const [items, setItems] = useState<DiscoveryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState<"paper" | "repo">("paper");

  async function load() {
    setLoading(true);
    setErr("");
    try {
      const r = await getDiscoveryFeed();
      setItems([...r.papers, ...r.repos]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const papers = items.filter((i) => i.type === "paper");
  const repos = items.filter((i) => i.type === "repo");
  const shown = tab === "paper" ? papers : repos;

  return (
    <div className="df-wrap">
      <div className="df-head">
        <span className="df-title-label">领域推送</span>
        <button className="df-refresh" onClick={load} disabled={loading} title="刷新">
          {loading ? "…" : "↻"}
        </button>
      </div>
      <div className="df-tabs">
        <button className={`df-tab ${tab === "paper" ? "active" : ""}`} onClick={() => setTab("paper")}>
          论文 {papers.length}
        </button>
        <button className={`df-tab ${tab === "repo" ? "active" : ""}`} onClick={() => setTab("repo")}>
          仓库 {repos.length}
        </button>
      </div>
      {err && <div className="muted df-err">{err}</div>}
      <div className="df-list">
        {loading && !shown.length && <div className="muted" style={{ padding: 12 }}>正在检索领域前沿…</div>}
        {shown.map((it, i) => (
          <ItemCard key={`${it.type}-${it.url}-${i}`} it={it} />
        ))}
        {!loading && !shown.length && !err && (
          <div className="muted" style={{ padding: 12 }}>暂无结果，点 ↻ 重试</div>
        )}
      </div>
    </div>
  );
}
