import { useState } from "react";
import { polishDraft, translateText, writeReview } from "../api/client";
import { Markdown } from "./Markdown";

type Mode = "review" | "polish" | "translate";

export function WritingPage() {
  const [mode, setMode] = useState<Mode>("review");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [out, setOut] = useState("");

  // review
  const [topic, setTopic] = useState("event camera spacecraft pose estimation");
  const [lang, setLang] = useState("zh");
  const [style, setStyle] = useState("综述");
  // polish
  const [draft, setDraft] = useState("");
  const [focus, setFocus] = useState("");
  // translate
  const [src, setSrc] = useState("");
  const [direction, setDirection] = useState("en2zh");

  async function run() {
    setBusy(true);
    setErr("");
    setOut("");
    try {
      let r: { ok: boolean; text: string; error?: string };
      if (mode === "review") r = await writeReview(topic, lang, style);
      else if (mode === "polish") r = await polishDraft(draft, focus);
      else r = await translateText(src, direction);
      if (r.ok) setOut(r.text);
      else setErr(r.error || "失败");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="kb-wrap">
      <div className="kb-head">
        <h1>写作与翻译</h1>
      </div>
      <div className="kb-body">
        <div className="form-card">
          <div className="seg">
            <button className={`btn sm ${mode === "review" ? "" : "ghost"}`} onClick={() => setMode("review")}>综述/研究背景</button>
            <button className={`btn sm ${mode === "polish" ? "" : "ghost"}`} onClick={() => setMode("polish")}>润色草稿</button>
            <button className={`btn sm ${mode === "translate" ? "" : "ghost"}`} onClick={() => setMode("translate")}>学术翻译</button>
          </div>

          {mode === "review" && (
            <>
              <input className="field" placeholder="主题，如 event camera spacecraft pose estimation" value={topic} onChange={(e) => setTopic(e.target.value)} />
              <div className="field-row">
                <label className="field-label">
                  语言
                  <select className="field" value={lang} onChange={(e) => setLang(e.target.value)}>
                    <option value="zh">中文</option>
                    <option value="en">English</option>
                  </select>
                </label>
                <label className="field-label">
                  体裁
                  <select className="field" value={style} onChange={(e) => setStyle(e.target.value)}>
                    <option value="综述">综述</option>
                    <option value="研究背景">研究背景</option>
                    <option value="相关工作">相关工作</option>
                  </select>
                </label>
              </div>
              <div className="hint">基于知识库检索相关片段，生成带 [n] 引用的综述。请先在 Zotero 页入库文献。</div>
            </>
          )}

          {mode === "polish" && (
            <>
              <textarea className="field" rows={8} placeholder="粘贴你的草稿…" value={draft} onChange={(e) => setDraft(e.target.value)} />
              <input className="field" placeholder="润色重点（可选），如：更紧凑、加强引用" value={focus} onChange={(e) => setFocus(e.target.value)} />
              <div className="hint">参考知识库术语润色，保留原意与结构。</div>
            </>
          )}

          {mode === "translate" && (
            <>
              <label className="field-label" style={{ flex: "0 0 200px" }}>
                方向
                <select className="field" value={direction} onChange={(e) => setDirection(e.target.value)}>
                  <option value="en2zh">英 → 中</option>
                  <option value="zh2en">中 → 英</option>
                </select>
              </label>
              <textarea className="field" rows={8} placeholder="粘贴待译文本…" value={src} onChange={(e) => setSrc(e.target.value)} />
              <div className="hint">用知识库术语统一专有名词译法；中译英保留公式/缩写，英译中首次出现标注原文。</div>
            </>
          )}

          <button className="btn block" disabled={busy} onClick={run}>
            {busy ? "生成中…" : mode === "review" ? "生成综述" : mode === "polish" ? "润色" : "翻译"}
          </button>

          {err && <div className="hint" style={{ color: "var(--rose)" }}>{err}</div>}
        </div>

        {out && (
          <div className="card" style={{ marginTop: 16 }}>
            <div className="row between" style={{ marginBottom: 8 }}>
              <span className="tool-cat" style={{ margin: 0 }}>结果</span>
              <button className="btn ghost sm" onClick={() => navigator.clipboard.writeText(out)}>复制</button>
            </div>
            <div className="md-body">
              <Markdown text={out} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
