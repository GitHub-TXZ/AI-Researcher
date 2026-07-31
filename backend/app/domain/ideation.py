"""学术 idea 生成 — 双 agent 辩论（Generator ↔ Critic）+ Reflection 迭代。

范式：
  - Generator: 基于知识库 + 内部知识提出研究 idea（含动机/方法/创新点/可行性）
  - Critic:    抨击 idea（新颖性/可行性/增量/漏洞），提出质疑
  - Refiner:   根据批判改进 idea
  - 多轮迭代（Reflection）→ 最终收敛为高质量 idea

两种模式：
  - generate: 由主题从知识库出发生成 idea
  - critique: 用户提供初步 idea，agent 给出改进思路 + 批判
"""
from __future__ import annotations

from typing import Any, Iterator

from app.core.llm import LLM
from app.storage.kb import KnowledgeBase

GEN_SYS = "你是航天器光学/事件相机 6DoF 姿态估计领域的资深研究者，擅长提出有创新性且可落地的研究 idea。"
CRITIC_SYS = "你是严格的审稿人/魔鬼辩护者，专挑研究 idea 的漏洞：新颖性不足、可行性存疑、增量太小、已被做过、方法缺陷。批判要尖锐、具体、有依据。"
REFINE_SYS = "你是研究思路整合者，根据批判意见改进 idea，保留可取之处、修补漏洞、强化创新点。"

GEN_PROMPT = """基于下方知识库片段与你的领域知识，围绕主题「{topic}」提出 {n} 个高质量研究 idea。
每个 idea 包含：\n1. **标题**\n2. **动机**（解决什么痛点）\n3. **核心方法**（具体技术路线）\n4. **创新点**（与现有工作的差异）\n5. **可行性**（数据/算力/实现难度）\n\n要求：idea 之间要有差异化（不止一种思路）；引用知识库用 [n]；不要泛泛而谈。\n\n## 知识库片段\n{ctx}\n\n## 主题\n{topic}\n\n请输出 {n} 个 idea。"""

CRITIC_PROMPT = """请对下列研究 idea 进行尖锐批判。逐条指出：
- 新颖性问题（是否已被做过 / 增量太小）
- 可行性问题（数据/算力/方法是否站得住）
- 逻辑漏洞（方法是否能真正解决动机中的痛点）
- 改进建议\n\n## 待批判的 idea\n{ideas}\n\n## 已有批判历史（供参考，避免重复）\n{history}\n\n请逐条批判，并给出严重程度（高/中/低）。"""

REFINE_PROMPT = """根据下列批判意见，改进原始 idea。要求：
- 保留可取之处，修补被指出的漏洞
- 强化创新点，避免与现有工作重复
- 若某 idea 不可救药，直接淘汰并说明
- 输出改进后的完整 idea 列表\n\n## 原始 idea\n{ideas}\n\n## 批判意见\n{critique}\n\n请输出改进后的 idea。"""

CRITIQUE_USER_PROMPT = """用户提供了一个初步研究 idea。请：
1. 给出改进与拓展思路（具体技术路线、可对比的 baseline、可用的数据集）
2. 对原 idea 进行批判（新颖性/可行性/漏洞）
3. 给出 2-3 个改进方向\n\n## 知识库参考\n{ctx}\n\n## 用户的初步 idea\n{idea}\n\n请输出思路 + 批判 + 改进方向。"""


def _ctx(kb: KnowledgeBase, query: str, top_k: int = 16) -> str:
    hits = kb.search(query, top_k)
    if not hits:
        return "(知识库为空)"
    return "\n\n".join(f"[{i}] {h['title']}\n{h['text']}" for i, h in enumerate(hits, 1))


def run_debate(
    kb: KnowledgeBase,
    llm: LLM,
    topic: str,
    n_ideas: int = 3,
    rounds: int = 2,
    seed_idea: str = "",
) -> Iterator[dict[str, Any]]:
    """流式输出辩论过程。若 seed_idea 非空，则为 critique 模式。"""
    if seed_idea:
        # critique 模式：单次思路+批判
        yield {"type": "agent_start", "agent": "Critic", "goal": "思路+批判用户 idea"}
        ctx = _ctx(kb, seed_idea[:200], 16)
        prompt = CRITIQUE_USER_PROMPT.format(ctx=ctx, idea=seed_idea)
        out = llm.chat([
            {"role": "system", "content": REFINE_SYS},
            {"role": "user", "content": prompt},
        ])
        yield {"type": "agent_token", "agent": "Critic", "text": out}
        yield {"type": "final", "text": out, "agents_used": ["Critic"]}
        return

    # generate 模式：Generator → Critic → Refiner 多轮
    ctx = _ctx(kb, topic, 16)
    ideas = ""
    history = ""
    for r in range(rounds):
        if r == 0:
            yield {"type": "agent_start", "agent": "Generator", "goal": f"围绕「{topic}」生成 {n_ideas} 个 idea"}
            ideas = llm.chat([
                {"role": "system", "content": GEN_SYS},
                {"role": "user", "content": GEN_PROMPT.format(topic=topic, n=n_ideas, ctx=ctx)},
            ])
            yield {"type": "agent_token", "agent": "Generator", "text": ideas}
        else:
            yield {"type": "agent_start", "agent": "Refiner", "goal": f"第 {r+1} 轮改进"}
            ideas = llm.chat([
                {"role": "system", "content": REFINE_SYS},
                {"role": "user", "content": REFINE_PROMPT.format(ideas=ideas, critique=critique)},
            ])
            yield {"type": "agent_token", "agent": "Refiner", "text": ideas}

        yield {"type": "agent_start", "agent": "Critic", "goal": f"第 {r+1} 轮批判"}
        critique = llm.chat([
            {"role": "system", "content": CRITIC_SYS},
            {"role": "user", "content": CRITIC_PROMPT.format(ideas=ideas, history=history or "(首轮)")},
        ])
        yield {"type": "agent_token", "agent": "Critic", "text": critique}
        history += f"\n--- 第{r+1}轮批判 ---\n{critique}"

    yield {"type": "final", "text": ideas, "agents_used": ["Generator", "Critic", "Refiner"]}
