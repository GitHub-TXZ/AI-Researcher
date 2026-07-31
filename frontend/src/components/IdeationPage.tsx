import { useEffect, useRef, useState } from "react";
import type { IdeaEvt } from "../api/client";
import { streamIdeation } from "../api/client";
import { Markdown } from "./Markdown";

type Turn = { agent: string; goal?: string; text: string; ts: number };

const AGENT_COLOR: Record<string, string> = {
  Generator: "var(--accent)",
  Critic: "var(--rose)",
  Refiner: "var(--blue)",
};

export function IdeationPage() {
  const [mode, setMode] = useState<"generate" | "critique">("generate");
  const [topic, setTopic] = useState("event camera spacecraft pose estimation under high dynamic motion");
  const [seed, setSeed] = useState("");
  const [nIdeas, setNIdeas] = useState(3);
  const [rounds, setRounds] = useState(2);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [final, setFinal] = useState("");
  const [status, setStatus] = useState("");
  const [roundIdx, setRoundIdx] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, final]);

  async function run() {
    setBusy(true);
    setErr("");
    setTurns([]);
    setFinal("");
    setStatus("准备中…");
    setRoundIdx(0);
    let cur: Turn | null = null;
    let rIdx = 0;
    try {
      await streamIdeation(
        { topic: mode === "generate" ? topic : "", seed_idea: mode === "critique" ? seed : "", n_ideas: nIdeas, rounds: rounds },
        (evt) => {
          if (evt.type === "agent_start") {
            const ag = evt.agent || "?";
            if (ag === "Generator") { rIdx = 0; setRoundIdx(1); }
            else if (ag === "Critic") { setRoundIdx(rIdx || 1); }
            else if (ag === "Refiner") { rIdx += 1; setRoundIdx(rIdx); }
            const step = mode === "critique" ? "" : ` · 第${rIdx || 1}/${rounds} 轮`;
            setStatus(`${ag}${step} · ${mode === "critique" ? "分析思路与批判" : ag === "Generator" ? "生成 idea" : ag === "Critic" ? "批判中" : "改进中"}…`);
            cur = { agent: ag, goal: evt.goal, text: "", ts: Date.now() };
            setTurns((t) => [...t, cur as Turn]);
          } else if (evt.type === "agent_token" && evt.text && cur) {
            const c = cur;
            c.text += evt.text;
            setTurns((t) => [...t.slice(0, -1), { ...c }]);
            scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
          } else if (evt.type === "final" && evt.text) {
            setFinal(evt.text);
            setStatus("完成");
          } else if (evt.type === "error") {
            setErr(evt.message || "失败");
            setStatus("出错");
          }
        },
      );
    } catch (e) {
      setErr(String(e));
      setStatus("出错");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="kb-wrap">
      <div className="kb-head">
        <h1>学术 idea 生成（双 agent 辩论）</h1>
      </div>
      <div className="kb-body" ref={scrollRef}>
        <div className="form-card">
          <div className="seg">
            <button className={`btn sm ${mode === "generate" ? "" : "ghost"}`} onClick={() => setMode("generate")}>
              从主题生成 idea
            </button>
            <button className={`btn sm ${mode === "critique" ? "" : "ghost"}`} onClick={() => setMode("critique")}>
              我给初步 idea，求思路与批判
            </button>
          </div>

          {mode === "generate" ? (
            <>
              <input
                className="field"
                placeholder="研究主题，如 event camera pose under high dynamic motion"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
              />
              <div className="field-row">
                <label className="field-label">
                  idea 数量
                  <select className="field" value={nIdeas} onChange={(e) => setNIdeas(Number(e.target.value))}>
                    {[2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </label>
                <label className="field-label">
                  辩论轮数
                  <select className="field" value={rounds} onChange={(e) => setRounds(Number(e.target.value))}>
                    {[1, 2, 3].map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="hint">Generator 生成 → Critic 批判 → Refiner 改进，多轮 Reflection 迭代。</div>
            </>
          ) : (
            <>
              <textarea
                className="field"
                rows={5}
                placeholder="你的初步 idea，如：用事件相机做高速旋转卫星的姿态估计，结合 time surface 和 PnP"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
              />
              <div className="hint">基于知识库给出改进思路 + 批判 + 改进方向。</div>
            </>
          )}

          <button className="btn block" disabled={busy || (mode === "generate" ? !topic.trim() : !seed.trim())} onClick={run}>
            {busy ? "辩论中…" : mode === "generate" ? "开始生成" : "思路+批判"}
          </button>
        </div>

        {busy && (
          <div className="status-bar" style={{ marginTop: 12 }}>
            <span className="spinner" />
            <span className="status-text">{status || "处理中…"}</span>
            {mode === "generate" && (
              <span className="status-progress">
                {Array.from({ length: rounds }).map((_, i) => (
                  <span key={i} className={`status-dot ${i < roundIdx ? "done" : i === roundIdx - 1 ? "active" : ""}`} />
                ))}
              </span>
            )}
          </div>
        )}
        {!busy && status === "完成" && (
          <div className="muted-2" style={{ marginTop: 12 }}>✓ 辩论完成，共 {rounds} 轮迭代。</div>
        )}

        {err && <div className="muted" style={{ color: "var(--rose)", marginTop: 12 }}>{err}</div>}

        {(turns.length > 0 || final) && (
          <div style={{ marginTop: 16 }}>
            {turns.map((t, i) => (
              <div key={i} className="card" style={{ marginBottom: 10, borderLeft: `3px solid ${AGENT_COLOR[t.agent] || "var(--border)"}` }}>
                <div className="row between" style={{ marginBottom: 6 }}>
                  <span style={{ color: AGENT_COLOR[t.agent] || "var(--text-2)", fontWeight: 600, fontSize: 13 }}>
                    {t.agent === "Generator" ? "✦ Generator" : t.agent === "Critic" ? "⚔ Critic" : "↻ Refiner"}
                  </span>
                  <span className="muted" style={{ fontSize: 11 }}>{new Date(t.ts).toLocaleTimeString()}</span>
                </div>
                {t.goal && <div className="muted" style={{ marginBottom: 4, fontSize: 12 }}>目标：{t.goal}</div>}
                <div className="md-body">
                  <Markdown text={t.text || "..."} />
                </div>
              </div>
            ))}
            {final && (
              <div className="card" style={{ borderLeft: "3px solid var(--accent)", background: "var(--accent-bg)" }}>
                <div className="tool-cat" style={{ margin: "0 0 6px", color: "var(--accent)" }}>最终收敛 idea</div>
                <div className="md-body">
                  <Markdown text={final} />
                </div>
                <button className="btn ghost sm" style={{ marginTop: 8 }} onClick={() => navigator.clipboard.writeText(final)}>
                  复制
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
