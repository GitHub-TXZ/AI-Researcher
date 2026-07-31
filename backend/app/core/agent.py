from __future__ import annotations

import re
from typing import Any, Optional

from app.core.llm import LLM
from app.core.tools import EventFn, ToolRegistry

_TOOL_RE = re.compile(r"\[TOOL_CALL:[^\]]*\]")


class ToolAgent:
    """Specialist that calls tools via [TOOL_CALL:name:params] protocol."""

    def __init__(
        self,
        name: str,
        llm: LLM,
        system_prompt: str,
        tools: ToolRegistry,
        on_event: Optional[EventFn] = None,
        max_iters: int = 4,
    ):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.tools = tools
        self.on_event = on_event
        self.max_iters = max_iters

    def emit(self, typ: str, **payload: Any) -> None:
        if self.on_event:
            self.on_event({"type": typ, "agent": self.name, **payload})

    def run(self, user_text: str) -> str:
        final = ""
        for evt in self.run_iter(user_text):
            t = evt.get("type")
            if t == "agent_token" and evt.get("text"):
                final += evt["text"]
            elif t == "agent_token_reset":
                final = ""
        return final

    def run_iter(self, user_text: str, history: list[dict] | None = None):
        """Generator that yields events as they happen — enables real streaming.

        `history` 为先前的对话轮次 [{role:"user"|"assistant", content:str}]，
        用于让 Agent 具备跨轮上下文记忆（不含工具调用内部过程）。
        """
        self.emit("agent_start", goal=user_text[:240])
        yield {"type": "agent_start", "agent": self.name, "goal": user_text[:240]}
        system = (
            f"{self.system_prompt}\n\n## Tools\n{self.tools.describe()}\n\n"
            "## Tool format\n"
            "When needed, output exactly: `[TOOL_CALL:tool_name:param]` and nothing else in that turn.\n"
            "Examples: `[TOOL_CALL:blur_score:asset_id=abc]` "
            "`[TOOL_CALL:event_accumulate:asset_id=abc,mode=polarity]` "
            "`[TOOL_CALL:kb_search:event camera pose]`\n"
            "After tool results, give a final answer. Prefer tool numbers over guesses.\n"
            "## Conversation memory\n"
            "Earlier turns are provided as prior user/assistant messages. Use them for context; "
            "do not redo already-done work unless the user asks."
        )
        messages: list[dict] = [{"role": "system", "content": system}]
        if history:
            for h in history[-20:]:  # 最近 20 轮，避免上下文过长
                role = h.get("role") or "user"
                content = h.get("content") or ""
                if content.strip():
                    messages.append({"role": role if role in ("user", "assistant") else "user", "content": content})
        messages.append({"role": "user", "content": user_text})
        final = ""
        for _ in range(self.max_iters):
            for evt in self._stream_turn(messages):
                yield evt
            reply, final_this_turn = self._last_reply, self._last_visible
            calls = self._parse(reply)
            if not calls:
                final = final_this_turn
                break
            reasoning = final_this_turn.strip()
            if reasoning:
                self.emit("agent_thinking", text=reasoning[:1200])
                yield {"type": "agent_thinking", "agent": self.name, "text": reasoning[:1200]}
            # clear the streaming message body: reasoning moved to thinking timeline
            self.emit("agent_token_reset")
            yield {"type": "agent_token_reset", "agent": self.name}
            results = []
            for c in calls:
                self.emit("tool_call", tool=c["name"], args=c["params"])
                yield {"type": "tool_call", "agent": self.name, "tool": c["name"], "args": c["params"]}
                out = self._exec(c["name"], c["params"])
                self.emit("tool_result", tool=c["name"], summary=out[:600])
                yield {"type": "tool_result", "agent": self.name, "tool": c["name"], "summary": out[:600]}
                # 可视化产物：从工具输出中提取 result_image_id，emit agent_image 供对话内联展示
                m_img = re.search(r"result_image_id[\"']?\s*[:=]\s*[\"']?([0-9a-f]{12})", out)
                if m_img:
                    iid = m_img.group(1)
                    title = c["name"]
                    self.emit("agent_image", image_id=iid, title=title)
                    yield {"type": "agent_image", "agent": self.name, "image_id": iid, "title": title}
                results.append(f"[{c['name']}] {out}")
            messages.append({"role": "assistant", "content": reasoning or "(calling tools)"})
            messages.append(
                {
                    "role": "user",
                    "content": "Tool results:\n"
                    + "\n\n".join(results)
                    + "\n\nAnswer using these results. Mention result_image_id if any.",
                }
            )
        else:
            # max iters reached without a final answer turn — produce one (streamed)
            for evt in self._stream_turn(messages):
                yield evt
            final = self._last_visible
            final = final_this_turn
        self.emit("agent_done", text=final[:500])
        yield {"type": "agent_done", "agent": self.name, "text": final[:500]}

    def _stream_turn(self, messages):
        """Stream one LLM turn. Sets self._last_raw / self._last_visible after streaming.

        Yields `agent_token` events for the visible (tool-syntax-stripped) text
        as it arrives. If a `[TOOL_CALL:` marker is detected mid-stream, stops
        emitting further visible text so tool syntax never leaks to the UI.
        """
        HOLD = 12  # >= len("[TOOL_CALL:")
        raw = ""
        emitted = 0
        marker_seen = False
        for delta in self.llm.stream(messages):
            raw += delta
            if "[TOOL_CALL:" in raw:
                marker_seen = True
            visible = _TOOL_RE.sub("", raw)
            if marker_seen:
                # only flush reasoning that precedes the marker (minus holdback)
                marker_idx = raw.find("[TOOL_CALL:")
                safe = max(0, min(marker_idx, len(visible)) - HOLD)
                if safe > emitted:
                    chunk = visible[emitted:safe]
                    self.emit("agent_token", text=chunk)
                    yield {"type": "agent_token", "agent": self.name, "text": chunk}
                    emitted = safe
                # do not emit anything at/after the marker
            else:
                safe_end = max(0, len(visible) - HOLD)
                if safe_end > emitted:
                    chunk = visible[emitted:safe_end]
                    self.emit("agent_token", text=chunk)
                    yield {"type": "agent_token", "agent": self.name, "text": chunk}
                    emitted = safe_end
        visible = _TOOL_RE.sub("", raw)
        if not marker_seen and len(visible) > emitted:
            chunk = visible[emitted:]
            self.emit("agent_token", text=chunk)
            yield {"type": "agent_token", "agent": self.name, "text": chunk}
            emitted = len(visible)
        self._last_reply = raw
        self._last_visible = visible

    def _parse(self, text: str) -> list[dict[str, str]]:
        out = []
        for m in re.finditer(r"\[TOOL_CALL:([^:\]]+):?([^\]]*)\]", text):
            out.append({
                "name": m.group(1).strip(),
                "params": m.group(2).strip(),
                "raw": m.group(0),
            })
        return out

    def _exec(self, name: str, raw: str) -> str:
        params: dict[str, Any] = {}
        if "=" in raw:
            for part in raw.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[k.strip()] = v.strip()
        else:
            params["input"] = raw
            params["query"] = raw
            params["asset_id"] = raw
        try:
            return self.tools.run(name, params)
        except Exception as exc:  # noqa: BLE001
            return f"tool error: {exc}"
