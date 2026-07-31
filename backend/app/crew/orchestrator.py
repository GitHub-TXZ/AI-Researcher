from __future__ import annotations

import re
from typing import Any, Iterator

from app.core.agent import ToolAgent
from app.core.llm import LLM
from app.core.tools import ToolRegistry
from app.storage.assets import AssetStore
from app.tools.factory import build_tools

PROMPT = """你是航天器光学/事件相机 6DoF 姿态估计研究助手。
用户会上传图像、事件流、姿态文件，并用自然语言要求分析。
你必须优先调用工具获取真实结果，禁止编造数值。

真实数据集已就绪（spacecraft/）：cassini-1-close / satty-1-close / soho-1-close 三个目标，
每个含成对 rgb+event 帧、原始事件流、真值 6DoF 姿态、3D 关键点与内参、3D 模型(STL+密集点云)。
分析真实数据集时优先用：
- spacecraft_list 列出目标与规模
- spacecraft_frames / spacecraft_frame_info 查看帧与真值姿态
- spacecraft_pnp / spacecraft_pnp_sequence 用 landmarks+keypoints+内参跑 PnP 并对比真值(旋转/平移误差)
- spacecraft_event_stats / spacecraft_event_frame 事件流统计与累积帧可视化
- spacecraft_model 查看 3D 模型
- 高逼格可视化：spacecraft_viz_frame(RGB+关键点+bbox)、spacecraft_viz_pnp(PnP重投影误差图)、spacecraft_viz_trajectory(3D姿态轨迹)、spacecraft_viz_model(3D点云投影)、spacecraft_event_anim(事件累积GIF动画)
- 3D数据可视化：spacecraft_3d_model(3D模型wireframe+关键点)、spacecraft_3d_pose(3D真值6DoF位姿坐标系+相机视锥)、spacecraft_3d_rotate(3D模型旋转GIF动画)
- 光学图像同时可视化：spacecraft_optical_montage(多帧RGB平铺，跨序列同时观察，含关键点+bbox)、spacecraft_optical_event_pair(同帧光学RGB与事件累积帧并排)
对用户上传的临时资源：分析图像用 image_*/orb_*/optical_flow/canny/blur；事件用 event_*/time_surface；
姿态用 pose_* / solve_pnp；文献用 kb_* / zotero_* / academic_*。
写作用 write_review（综述/研究背景）、polish_draft（润色）、translate（学术翻译，用知识库术语统一）。
先 list_assets / spacecraft_list 若不知道 id。回答简洁，并给出 result_image_id 方便用户在对话中查看结果图。"""


class ResearchCrew:
    def __init__(self, llm: LLM, assets: AssetStore, tools: ToolRegistry):
        self.llm = llm
        self.assets = assets
        self.tools = tools

    def run_stream(self, message: str, mention: list[str] | None = None, history: list[dict] | None = None) -> Iterator[dict[str, Any]]:
        catalog = ", ".join(f"{a.id}[{a.kind}]" for a in self.assets.list()[:25]) or "(none)"
        brief = f"{message}\n\nAvailable assets: {catalog}"
        if mention:
            brief = f"(Preferred focus: {', '.join(mention)})\n" + brief

        agent = ToolAgent("Analyst", self.llm, PROMPT, self.tools, max_iters=5)
        final_text = ""
        try:
            for evt in agent.run_iter(brief, history=history):
                t = evt.get("type")
                if t == "agent_token" and evt.get("text"):
                    final_text += evt["text"]
                elif t == "agent_token_reset":
                    final_text = ""
                yield evt
        except Exception as exc:  # noqa: BLE001
            answer = self._offline(message, str(exc))
            yield {"type": "error", "message": str(exc)}
            yield {"type": "agent_token", "agent": "Analyst", "text": answer}
            yield {"type": "final", "text": answer, "agents_used": ["Analyst"]}
            return
        yield {"type": "final", "text": final_text, "agents_used": ["Analyst"]}

    def _offline(self, message: str, err: str) -> str:
        import ast
        import json

        from app.domain.pose import quat_to_R, qnorm
        import numpy as np

        m = re.search(r"\[[^\]]+\]", message)
        if m and ("quat" in message.lower() or "四元数" in message or "convert" in message.lower()):
            try:
                q = qnorm(ast.literal_eval(m.group(0))[:4])
                return "LLM不可用，离线几何：\n" + json.dumps({"quat": q.tolist(), "R": quat_to_R(q).tolist()})
            except Exception:
                pass
        # try blur on first image asset if asked
        if any(k in message.lower() for k in ["blur", "模糊"]):
            imgs = self.assets.list("image")
            if imgs:
                from app.domain import cv

                return json.dumps({"offline": True, "asset_id": imgs[0].id, **cv.blur_score(self.assets.load_image(imgs[0].id))})
        return f"分析失败（{err}）。请检查 LLM 配置，或先上传数据后重试。"
