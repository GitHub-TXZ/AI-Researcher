import { useEffect, useRef, useState } from "react";
import type { ChatImage, Evt, Msg, Step } from "../api/client";
import { streamChat } from "../api/client";
import { IconSend } from "./icons";
import { Markdown, shortenIds } from "./Markdown";

const SUGGESTIONS = [
  "列出航天器真实数据集的三个目标与规模",
  "对 cassini 第 20 帧做真实 PnP 验证，对比真值姿态误差",
  "对三个目标批量 PnP 验证，给出旋转/平移误差统计",
  "统计 soho 的事件流并生成第 25 帧附近的事件累积帧",
];

async function downloadImage(img: ChatImage) {
  const r = await fetch(`/api/assets/inline/${img.id}`);
  if (!r.ok) {
    alert("图片已过期（内存级存储，后端重启后清空）");
    return;
  }
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const ext = blob.type.includes("gif") ? ".gif" : blob.type.includes("jpeg") ? ".jpg" : ".png";
  a.download = `${img.title || "visualization"}${ext}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function InlineImage({ img }: { img: ChatImage }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div className="inline-asset inline-asset-expired">
        <div className="inline-asset-foot">
          <span className="inline-asset-id">{img.title}</span>
        </div>
        <div className="muted" style={{ fontSize: 12, padding: "10px 4px" }}>
          图片已过期（内存级存储，后端重启后清空）。请重新发送指令以再次生成。
        </div>
      </div>
    );
  }
  return (
    <div className="inline-asset">
      <img
        src={`/api/assets/inline/${img.id}`}
        alt={img.title}
        loading="lazy"
        onError={() => setFailed(true)}
      />
      <div className="inline-asset-foot">
        <span className="inline-asset-id">{img.title}</span>
        <button className="save-btn" onClick={() => downloadImage(img)} title="保存到本地">
          ⬇ 保存
        </button>
      </div>
    </div>
  );
}

function InlineImages({ images }: { images: ChatImage[] }) {
  if (!images?.length) return null;
  return (
    <div className="inline-assets">
      {images.map((im) => (
        <InlineImage key={im.id} img={im} />
      ))}
    </div>
  );
}

function StepIcon({ kind }: { kind: Step["kind"] }) {
  const map: Record<Step["kind"], { ch: string; color: string }> = {
    start: { ch: "◎", color: "var(--blue)" },
    thinking: { ch: "✦", color: "var(--violet)" },
    tool_call: { ch: "⚙", color: "var(--accent)" },
    tool_result: { ch: "↳", color: "var(--amber)" },
    done: { ch: "✓", color: "var(--text-3)" },
  };
  const s = map[kind];
  return <span style={{ color: s.color, fontWeight: 600, fontSize: 13 }}>{s.ch}</span>;
}

function ThinkingCard({ steps }: { steps: Step[] }) {
  const [open, setOpen] = useState(true);
  const toolCalls = steps.filter((s) => s.kind === "tool_call").length;
  return (
    <div className="think-card">
      <button className="think-head" onClick={() => setOpen((o) => !o)}>
        <span className="think-chevron">{open ? "▾" : "▸"}</span>
        <span className="think-label">思考与调用过程</span>
        <span className="think-count">{steps.length} 步 · {toolCalls} 次工具调用</span>
      </button>
      {open && (
        <div className="think-body">
          {steps.length === 0 && (
            <div className="think-step">
              <span className="spinner" />
              <div className="muted-2">正在思考…</div>
            </div>
          )}
          {steps.map((s, i) => (
            <div key={i} className="think-step">
              <div className="think-step-icon">
                <StepIcon kind={s.kind} />
                {i < steps.length - 1 && <span className="think-line" />}
              </div>
              <div className="think-step-content">
                {s.kind === "start" && <div className="muted-2">目标：{s.goal}</div>}
                {s.kind === "thinking" && <div className="think-text">{s.text}</div>}
                {s.kind === "tool_call" && (
                  <div className="think-tool">
                    <span className="think-tool-name">⚙ {s.tool}</span>
                    <span className="think-tool-args">{shortenIds(s.args || "")}</span>
                  </div>
                )}
                {s.kind === "tool_result" && (
                  <div className="think-result">
                    <span className="muted">{s.tool} → </span>
                    <code>{shortenIds(s.summary || "").slice(0, 280)}</code>
                  </div>
                )}
                {s.kind === "done" && <div className="muted">完成</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ChatPanel({
  selected,
  onDone,
  onTrace,
  busy,
  setBusy,
  pending,
  setPending,
}: {
  selected: string;
  onDone: () => void;
  onTrace: (e: Evt) => void;
  busy: boolean;
  setBusy: (b: boolean) => void;
  pending: string;
  setPending: (s: string) => void;
}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const streamIdRef = useRef<string>("");
  const [atBottom, setAtBottom] = useState(true);
  const [action, setAction] = useState("");

  useEffect(() => {
    if (pending) {
      setInput(pending);
      setPending("");
    }
  }, [pending, setPending]);

  // 智能滚动：仅在用户已处于底部时自动滚到底
  useEffect(() => {
    if (atBottom) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [msgs, atBottom]);

  function onScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
    setAtBottom(near);
  }

  function scrollToBottom() {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    setAtBottom(true);
  }

  async function send(text: string) {
    if (!text.trim() || busy) return;
    const t = text.trim();
    // 构建上下文记忆：取最近的 user/bot 对话轮次（不含工具过程）
    const history = msgs
      .filter((m) => m.role === "user" || m.role === "bot")
      .map((m) => ({ role: m.role === "user" ? "user" : "assistant", content: m.text }))
      .slice(-10);
    setInput("");
    setBusy(true);
    setAtBottom(true);
    setAction("正在思考…");
    const turnId = crypto.randomUUID();
    setMsgs((m) => [
      ...m,
      { id: crypto.randomUUID(), role: "user", text: t, ts: Date.now() },
      { id: turnId, role: "tool", text: "", ts: Date.now(), steps: [] },
    ]);
    streamIdRef.current = "";
    const pendingImages: ChatImage[] = [];

    const pushStep = (s: Step) => {
      setMsgs((m) =>
        m.map((x) =>
          x.id === turnId ? { ...x, steps: [...(x.steps || []), s] } : x,
        ),
      );
    };

    const appendToken = (delta: string) => {
      if (!streamIdRef.current) {
        const id = crypto.randomUUID();
        streamIdRef.current = id;
        setMsgs((m) => [
          ...m,
          { id, role: "bot", agent: "Analyst", text: delta, ts: Date.now() },
        ]);
      } else {
        const id = streamIdRef.current;
        setMsgs((m) => m.map((x) => (x.id === id ? { ...x, text: x.text + delta } : x)));
      }
    };

    const resetToken = () => {
      const sid = streamIdRef.current;
      streamIdRef.current = "";
      if (sid) setMsgs((m) => m.filter((x) => x.id !== sid));
    };

    try {
      await streamChat(
        t,
        null,
        (evt) => {
          onTrace(evt);
        const ts = Date.now();
        if (evt.type === "agent_start") { setAction("分析中…"); pushStep({ kind: "start", goal: evt.goal, ts }); }
        else if (evt.type === "agent_thinking") { setAction("推理中…"); pushStep({ kind: "thinking", text: evt.text, ts }); }
        else if (evt.type === "tool_call") { setAction(`调用工具 ${evt.tool}`); pushStep({ kind: "tool_call", tool: evt.tool, args: evt.args, ts }); }
        else if (evt.type === "tool_result") { setAction(`读取 ${evt.tool} 结果`); pushStep({ kind: "tool_result", tool: evt.tool, summary: evt.summary, ts }); }
        else if (evt.type === "agent_token" && evt.text) { setAction("生成回答…"); appendToken(evt.text!); }
        else if (evt.type === "agent_token_reset") { resetToken(); }
        else if (evt.type === "agent_image" && evt.image_id) {
          pendingImages.push({ id: evt.image_id!, title: evt.title || "visualization" });
        }
        else if (evt.type === "agent_done") { setAction("整理答案…"); pushStep({ kind: "done", text: evt.text, ts }); }
        else if (evt.type === "final" && evt.text) {
          setAction("");
          const sid = streamIdRef.current;
          const imgs = pendingImages.length ? pendingImages : undefined;
          if (sid) {
            setMsgs((m) => m.map((x) => (x.id === sid ? { ...x, text: evt.text!, images: imgs, ts: Date.now() } : x)));
          } else {
            setMsgs((m) => [
              ...m,
              { id: crypto.randomUUID(), role: "bot", agent: "Analyst", text: evt.text!, images: imgs, ts: Date.now() },
            ]);
          }
          streamIdRef.current = "";
          onDone();
        } else if (evt.type === "error" && evt.message) {
          setAction("");
          streamIdRef.current = "";
          setMsgs((m) => [
            ...m,
            { id: crypto.randomUUID(), role: "bot", text: `⚠ ${evt.message}`, ts: Date.now() },
          ]);
        }
      },
        undefined,
        history,
      );
    } catch (e) {
      setMsgs((m) => [...m, { id: crypto.randomUUID(), role: "bot", text: String(e), ts: Date.now() }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat-wrap">
      <div className="chat-head">
        <h1>分析对话</h1>
        <div className={`pill ${busy ? "busy" : ""}`}>
          <span className="dot" />
          {busy ? (action || "分析中") : "就绪"}
        </div>
      </div>

      <div className="chat-body" ref={scrollRef} onScroll={onScroll} style={{ position: "relative" }}>
        {!msgs.length ? (
          <div className="chat-empty">
            <div className="big">⌖</div>
            <h2>航天器姿态估计研究助手</h2>
            <p className="muted">上传数据后，用自然语言驱动 CV / 事件 / 姿态 / 知识库 / 学术检索工具分析</p>
            <div className="suggest">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        ) : (
          msgs.map((m) => (
            <div key={m.id} className={`msg ${m.role}`}>
              <div className="msg-head">
                <span className="who">{m.role === "user" ? "你" : m.agent || "Analyst"}</span>
                <span className="time">{new Date(m.ts).toLocaleTimeString()}</span>
              </div>
              {m.steps && m.steps.length > 0 ? (
                <ThinkingCard steps={m.steps} />
              ) : m.role === "user" ? (
                <div className="msg-body">{m.text}</div>
              ) : (
                <div className="msg-body md-body">
                  <Markdown text={shortenIds(m.text)} />
                  <InlineImages images={m.images || []} />
                </div>
              )}
            </div>
          ))
        )}
        {!atBottom && msgs.length > 0 && (
          <button className="scroll-bottom-btn" onClick={scrollToBottom}>↓ 最新</button>
        )}
      </div>

      <div className="chat-input">
        <textarea
          className="field"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            selected
              ? `已选中资源 ${selected.slice(0, 8)}…  例：对这个图像做 blur_score`
              : "输入分析指令，或点击左侧工具…"
          }
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              send(input);
            }
          }}
        />
        <div className="actions">
          <span className="hint">
            {selected && <span>当前资源 <span className="kbd">{selected.slice(0, 8)}</span></span>}
          </span>
          <button className="btn" disabled={busy || !input.trim()} onClick={() => send(input)}>
            <IconSend width={14} height={14} />
            {busy ? "分析中…" : "发送"}
          </button>
        </div>
      </div>
    </div>
  );
}
