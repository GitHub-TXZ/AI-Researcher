import type { Tool } from "../api/client";

const CATS: { key: string; label: string; color: string; match: RegExp }[] = [
  { key: "cv", label: "光学视觉", color: "var(--blue)", match: /^(image_|blur|canny|orb|optical_flow|hist)/ },
  { key: "ev", label: "事件相机", color: "var(--violet)", match: /^(event_|time_surface|accumulate)/ },
  { key: "pose", label: "姿态几何", color: "var(--amber)", match: /^(pose_|quat|solve_pnp|rot)/ },
  { key: "kb", label: "知识库", color: "var(--accent)", match: /^(kb_|list_papers)/ },
  { key: "asset", label: "资源", color: "var(--text-3)", match: /^(list_assets|get_asset)/ },
];

function catOf(name: string) {
  return CATS.find((c) => c.match.test(name)) || { key: "misc", label: "其它", color: "var(--text-3)" };
}

export function ToolPanel({
  tools,
  onPick,
  trace,
}: {
  tools: Tool[];
  onPick: (t: string) => void;
  trace: { type: string; tool?: string; text?: string; message?: string }[];
}) {
  const grouped: Record<string, Tool[]> = {};
  for (const t of tools) {
    const c = catOf(t.name);
    (grouped[c.key] ||= []).push(t);
  }

  return (
    <div className="panel panel-r">
      <div className="panel-header">
        <div className="panel-title">工具与轨迹</div>
        <div className="panel-subtitle">{tools.length} 个工具</div>
      </div>
      <div className="panel-body">
        {Object.entries(grouped).map(([key, list]) => {
          const c = CATS.find((x) => x.key === key) || { label: "其它", color: "var(--text-3)" };
          return (
            <div key={key}>
              <div className="tool-cat">{c.label}</div>
              <div className="list">
                {list.map((t) => (
                  <div key={t.name} className="tool-row" onClick={() => onPick(t.name)} title={t.description}>
                    <span className="dot" style={{ background: c.color }} />
                    <div style={{ minWidth: 0 }}>
                      <div className="tn">{t.name}</div>
                      <div className="td">{t.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        <div className="tool-cat" style={{ marginTop: 16 }}>执行轨迹</div>
        <div className="list">
          {trace.slice(-30).map((e, i) => (
            <div key={i} className={`trace-item ${e.type === "tool_call" ? "tool" : ""} ${e.type === "error" ? "error" : ""}`}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="tag">{e.type}{e.tool ? ` · ${e.tool}` : ""}</div>
                <div className="muted" style={{ marginTop: 2, wordBreak: "break-all" }}>
                  {(e.text || e.message || "").slice(0, 120)}
                </div>
              </div>
            </div>
          ))}
          {!trace.length && <div className="muted" style={{ textAlign: "center", padding: 12 }}>尚无执行记录</div>}
        </div>
      </div>
    </div>
  );
}
