import { useRef, useState } from "react";
import type { Paper } from "../api/client";
import { uploadPaper, kbSearch, deletePaper } from "../api/client";
import { IconUpload, IconSearch, IconBook } from "./icons";

export function KnowledgePage({ papers, onIngested }: { papers: Paper[]; onIngested: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<{ score?: number; text?: string; paper_title?: string }[] | null>(null);
  const [delBusy, setDelBusy] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function doUpload(file: File) {
    setBusy(true);
    setErr("");
    try {
      await uploadPaper(file);
      onIngested();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function search() {
    if (!query.trim()) return;
    try {
      const r = await kbSearch(query.trim(), 6);
      setHits(r.hits as { score?: number; text?: string; paper_title?: string }[]);
    } catch (e) {
      setErr(String(e));
    }
  }

  async function remove(p: Paper) {
    if (!confirm(`删除文献「${p.title}」？此操作不可撤销。`)) return;
    setDelBusy(p.id);
    try {
      await deletePaper(p.id);
      onIngested();
    } catch (e) {
      setErr(String(e));
    } finally {
      setDelBusy("");
    }
  }

  return (
    <div className="kb-wrap">
      <div className="kb-head">
        <h1>文献知识库</h1>
      </div>
      <div className="kb-body">
        <div
          className="upload-zone"
          onClick={() => fileRef.current?.click()}
          style={{ marginBottom: 16 }}
        >
          <IconUpload style={{ marginBottom: 6 }} />
          <div>{busy ? "入库中…" : "上传 PDF / Markdown / TXT 入库"}</div>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.md,.txt"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) doUpload(f);
              e.target.value = "";
            }}
          />
        </div>
        {err && <div className="muted" style={{ color: "var(--rose)", marginBottom: 12 }}>{err}</div>}

        <div className="row" style={{ marginBottom: 16 }}>
          <input
            className="field"
            placeholder="检索知识库…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
          />
          <button className="btn ghost" onClick={search}>
            <IconSearch width={14} height={14} /> 检索
          </button>
        </div>

        {hits && (
          <div className="list" style={{ marginBottom: 20 }}>
            <div className="tool-cat">检索结果</div>
            {hits.map((h, i) => (
              <div key={i} className="card">
                <div className="row between">
                  <span className="muted-2" style={{ fontWeight: 500 }}>{h.paper_title || "未知文献"}</span>
                  <span className="badge tool">{h.score?.toFixed(3)}</span>
                </div>
                <div className="muted" style={{ marginTop: 6 }}>{(h.text || "").slice(0, 220)}…</div>
              </div>
            ))}
            {!hits.length && <div className="muted">无匹配</div>}
          </div>
        )}

        <div className="tool-cat">已入库文献 · {papers.length}</div>
        <div className="list">
          {papers.map((p) => (
            <div key={p.id} className="card paper-item">
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="pt">{p.title}</div>
                <div className="pm">
                  {p.n_chunks} chunks · {p.tags.join(", ") || "无标签"}
                </div>
              </div>
              <IconBook width={16} height={16} style={{ color: "var(--text-3)" }} />
              <button
                className="del-btn"
                title="删除"
                disabled={delBusy === p.id}
                onClick={() => remove(p)}
              >
                {delBusy === p.id ? "…" : "✕"}
              </button>
            </div>
          ))}
          {!papers.length && <div className="muted" style={{ textAlign: "center", padding: 20 }}>暂无文献</div>}
        </div>
      </div>
    </div>
  );
}
