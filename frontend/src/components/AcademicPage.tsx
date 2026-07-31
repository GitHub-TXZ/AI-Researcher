import { useState } from "react";
import type { AcademicPaper } from "../api/client";
import { academicSearch } from "../api/client";
import { IconSearch } from "./icons";

const SOURCES = [
  { key: "semantic_scholar", label: "Semantic Scholar", hint: "全学科 2亿+" },
  { key: "arxiv", label: "arXiv", hint: "CS/物理 预印本" },
  { key: "openalex", label: "OpenAlex", hint: "全学科 2.5亿+" },
  { key: "crossref", label: "CrossRef", hint: "期刊元数据" },
];

export function AcademicPage() {
  const [source, setSource] = useState("semantic_scholar");
  const [keyword, setKeyword] = useState("spacecraft pose estimation event camera");
  const [field, setField] = useState("");
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [author, setAuthor] = useState("");
  const [category, setCategory] = useState("");
  const [limit, setLimit] = useState(5);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [papers, setPapers] = useState<AcademicPaper[]>([]);
  const [total, setTotal] = useState(0);
  const [advanced, setAdvanced] = useState(false);

  async function search() {
    if (!keyword.trim()) return;
    setBusy(true);
    setErr("");
    try {
      const r = await academicSearch({
        source,
        keyword: keyword.trim(),
        field,
        year_from: yearFrom,
        year_to: yearTo,
        author,
        category,
        max_results: limit,
      });
      if (!r.ok) {
        setErr(r.result?.error || "检索失败");
        setPapers([]);
        setTotal(0);
      } else {
        setPapers(r.result.papers);
        setTotal(r.result.count);
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="kb-wrap">
      <div className="kb-head">
        <h1>学术文献检索</h1>
      </div>
      <div className="kb-body">
        <div className="list" style={{ marginBottom: 16 }}>
          <div className="tool-cat" style={{ marginTop: 0 }}>数据源</div>
          <div className="row wrap">
            {SOURCES.map((s) => (
              <button
                key={s.key}
                className={`btn sm ${source === s.key ? "" : "ghost"}`}
                onClick={() => setSource(s.key)}
                title={s.hint}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <div className="row" style={{ marginBottom: 8 }}>
          <input
            className="field"
            placeholder="关键词，如 event camera spacecraft pose estimation"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
          />
          <button className="btn" disabled={busy || !keyword.trim()} onClick={search}>
            <IconSearch width={14} height={14} /> {busy ? "检索中…" : "检索"}
          </button>
          <button className="btn ghost sm" onClick={() => setAdvanced((a) => !a)}>
            {advanced ? "收起" : "高级"}
          </button>
        </div>

        {advanced && (
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="row wrap" style={{ gap: 12 }}>
              {source === "arxiv" ? (
                <>
                  <label className="muted-2" style={{ flex: "1 1 200px" }}>
                    作者
                    <input className="field" value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="如 Kostavel" />
                  </label>
                  <label className="muted-2" style={{ flex: "1 1 200px" }}>
                    arXiv 分类
                    <input className="field" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="如 cs.CV" />
                  </label>
                </>
              ) : (
                <>
                  <label className="muted-2" style={{ flex: "1 1 200px" }}>
                    学科领域
                    <input className="field" value={field} onChange={(e) => setField(e.target.value)} placeholder="如 Computer Science" />
                  </label>
                  <label className="muted-2" style={{ flex: "0 1 100px" }}>
                    起始年
                    <input className="field" value={yearFrom} onChange={(e) => setYearFrom(e.target.value)} placeholder="2020" />
                  </label>
                  {source !== "crossref" && (
                    <label className="muted-2" style={{ flex: "0 1 100px" }}>
                      截止年
                      <input className="field" value={yearTo} onChange={(e) => setYearTo(e.target.value)} placeholder="2026" />
                    </label>
                  )}
                </>
              )}
              <label className="muted-2" style={{ flex: "0 1 100px" }}>
                结果数
                <select className="field" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
                  {[3, 5, 10, 15, 20].map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        )}

        {err && <div className="muted" style={{ color: "var(--rose)", marginBottom: 12 }}>{err}</div>}

        {papers.length > 0 && (
          <div className="muted-2" style={{ marginBottom: 12 }}>
            {SOURCES.find((s) => s.key === source)?.label} · 共 {total} 篇，显示 {papers.length} 篇
          </div>
        )}

        <div className="list">
          {papers.map((p, i) => (
            <div key={i} className="card">
              <div className="row between">
                <span className="badge tool">{p.year ?? "?"}</span>
                {p.citations != null && <span className="muted">引用 {p.citations}</span>}
              </div>
              <div style={{ fontWeight: 600, marginTop: 6, color: "var(--text)" }}>{p.title}</div>
              <div className="muted" style={{ marginTop: 4 }}>
                {(p.authors || []).join(", ")}
                {p.venue ? ` · ${p.venue}` : ""}
              </div>
              {p.abstract && <div className="muted-2" style={{ marginTop: 6 }}>{p.abstract.slice(0, 220)}…</div>}
              <div className="row wrap" style={{ marginTop: 8, gap: 12 }}>
                {p.doi && (
                  <a className="muted-2" href={`https://doi.org/${p.doi}`} target="_blank" rel="noreferrer" style={{ color: "var(--blue)" }}>
                    DOI ↗
                  </a>
                )}
                {p.arxiv && (
                  <a className="muted-2" href={`https://arxiv.org/abs/${p.arxiv}`} target="_blank" rel="noreferrer" style={{ color: "var(--blue)" }}>
                    arXiv ↗
                  </a>
                )}
                {p.pdf && (
                  <a className="muted-2" href={p.pdf} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                    PDF ↗
                  </a>
                )}
              </div>
            </div>
          ))}
          {!papers.length && !busy && !err && (
            <div className="muted" style={{ textAlign: "center", padding: 30 }}>
              输入关键词检索学术文献，或直接在分析台对话中说「检索 event camera pose 的最新论文」
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
