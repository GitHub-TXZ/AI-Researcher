"""学术写作与翻译 — 基于本地知识库的 RAG 辅助。

功能：
  - write_review:   基于知识库生成综述/研究背景
  - polish:         根据知识库润色用户草稿
  - translate:      学术翻译，用知识库术语统一专有名词
"""
from __future__ import annotations

from typing import Any

from app.core.llm import LLM
from app.storage.kb import KnowledgeBase


def _gather(kb: KnowledgeBase, query: str, top_k: int = 12) -> str:
    hits = kb.search(query, top_k)
    if not hits:
        return "(知识库为空，请先入库文献)"
    return "\n\n".join(
        f"[{i}] {h['title']}\n{h['text']}" for i, h in enumerate(hits, 1)
    )


def write_review(kb: KnowledgeBase, llm: LLM, topic: str, lang: str = "zh", style: str = "综述") -> str:
    """基于知识库生成综述或研究背景。"""
    ctx = _gather(kb, topic, 14)
    lang_note = "用中文撰写" if lang.startswith("zh") else "Write in English"
    prompt = (
        f"你是航天器光学/事件相机 6DoF 姿态估计领域的资深研究者。"
        f"请根据下方知识库片段，撰写一段关于「{topic}」的学术{style}，{lang_note}。\n"
        "要求：\n"
        "1. 结构清晰（背景→问题→方法→趋势），逻辑连贯；\n"
        "2. 引用知识库片段时用 [n] 标注，严禁编造未在片段中出现的结论；\n"
        "3. 使用学术化表达，避免口语；\n"
        "4. 800-1200 字。\n\n"
        f"## 知识库片段\n{ctx}\n\n"
        f"## 主题\n{topic}\n\n请直接输出{style}正文。"
    )
    return llm.chat([
        {"role": "system", "content": "你是学术写作助手，严格基于给定文献片段写作。"},
        {"role": "user", "content": prompt},
    ])


def polish(kb: KnowledgeBase, llm: LLM, draft: str, focus: str = "") -> str:
    """根据知识库润色用户草稿。"""
    ctx = _gather(kb, draft[:200] or focus, 8)
    prompt = (
        "你是学术写作润色助手。请润色下方用户草稿，使其更学术化、连贯、准确。\n"
        "要求：\n"
        "1. 修正语法与表达，但保留原意与结构；\n"
        "2. 可参考知识库片段中的术语与表述；\n"
        "3. 输出润色后的正文，不要解释改动。\n\n"
        f"## 知识库参考\n{ctx}\n\n"
        f"## 用户草稿\n{draft}\n"
    )
    if focus:
        prompt += f"\n润色重点：{focus}\n"
    return llm.chat([
        {"role": "system", "content": "你是学术润色助手，输出润色后的完整文本。"},
        {"role": "user", "content": prompt},
    ])


def _build_glossary(kb: KnowledgeBase, text: str, top_k: int = 10) -> str:
    """从知识库中抽取与待译文本相关的术语片段，供翻译时统一。"""
    hits = kb.search(text[:200], top_k)
    if not hits:
        return ""
    # 取片段中可能的术语行（含英文+中文共现的行）
    terms: list[str] = []
    for h in hits:
        for line in h["text"].split("\n"):
            if any(c.isascii() and c.isalpha() for c in line) and any("\u4e00" <= c <= "\u9fff" for c in line):
                terms.append(line.strip())
                if len(terms) >= 20:
                    break
    return "\n".join(terms[:20])


def translate(kb: KnowledgeBase, llm: LLM, text: str, direction: str = "en2zh") -> str:
    """学术翻译，用知识库术语统一专有名词。direction: en2zh / zh2en。"""
    glossary = _build_glossary(kb, text)
    if direction == "zh2en":
        task = "将下列中文翻译为英文学术英语"
        term_rule = "专有名词参考下方术语表，保持与领域惯例一致"
    else:
        task = "将下列英文翻译为中文，使用航天器姿态估计/计算机视觉领域的惯用译法"
        term_rule = "专有名词参考下方术语表统一译法；首次出现时在中文后用括号标注英文原文"
    prompt = f"你是学术翻译助手。{task}。\n要求：\n1. {term_rule}；\n2. 保留公式、变量、缩写原样；\n3. 只输出译文。\n"
    if glossary:
        prompt += f"\n## 术语参考\n{glossary}\n"
    prompt += f"\n## 待译文本\n{text}\n"
    return llm.chat([
        {"role": "system", "content": "你是学术翻译助手，只输出译文。"},
        {"role": "user", "content": prompt},
    ])
