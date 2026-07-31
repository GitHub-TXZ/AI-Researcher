from __future__ import annotations

import json
from typing import Any

import numpy as np

from app.core.llm import LLM
from app.core.tools import Tool, ToolRegistry
from app.domain import academic, cv, events
from app.domain import writing, zotero
from app.domain import spacecraft as sc
from app.domain.pose import parse_pose, quat_to_R, rot_err_deg, sequence_errors
from app.storage.assets import AssetStore
from app.storage.kb import KnowledgeBase
from app.storage import ephemeral as _eph


def _g(p: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for k in keys:
        if p.get(k) not in (None, ""):
            return p[k]
    return default


class _Fn(Tool):
    def __init__(self, name: str, desc: str, fn):
        super().__init__(name, desc)
        self.fn = fn

    def run(self, params: dict[str, Any]) -> str:
        return self.fn(params)


def build_tools(assets: AssetStore, kb: KnowledgeBase, llm: "LLM | None" = None) -> ToolRegistry:
    reg = ToolRegistry()

    def list_assets(p):
        kind = str(_g(p, "kind", "input", default="")).strip() or None
        items = assets.list(kind if kind in {"image", "events", "pose"} else None)
        if not items:
            return "暂无上传资源。请先在左侧上传图像/事件/姿态。"
        return "\n".join(f"- {a.id} [{a.kind}] {a.filename} {a.tags}" for a in items[:40])

    def kb_search(p):
        q = str(_g(p, "query", "input"))
        return kb.format_hits(kb.search(q, 5))

    def kb_ask(p):
        q = str(_g(p, "query", "input"))
        hits = kb.search(q, 6)
        if not hits:
            return "KB_EMPTY"
        return "仅用下列片段作答并引用[n]：\n" + kb.format_hits(hits)

    def image_stats(p):
        aid = str(_g(p, "asset_id", "input"))
        return json.dumps({"asset_id": aid, **cv.stats(assets.load_image(aid))})

    def blur_score(p):
        aid = str(_g(p, "asset_id", "input"))
        return json.dumps({"asset_id": aid, **cv.blur_score(assets.load_image(aid))})

    def canny_edge(p):
        aid = str(_g(p, "asset_id", "input"))
        out = cv.canny(assets.load_image(aid))
        iid = _eph.put(out, "canny_edge")
        return json.dumps({"source": aid, "result_image_id": iid})

    def orb_features(p):
        aid = str(_g(p, "asset_id", "input"))
        vis, info = cv.orb(assets.load_image(aid))
        iid = _eph.put(vis, "orb_features")
        return json.dumps({"source": aid, "result_image_id": iid, **info})

    def orb_match(p):
        a, b = str(p.get("asset_id_a") or ""), str(p.get("asset_id_b") or "")
        vis, info = cv.orb_match(assets.load_image(a), assets.load_image(b))
        iid = _eph.put(vis, "orb_match")
        return json.dumps({"a": a, "b": b, "result_image_id": iid, **info})

    def optical_flow(p):
        a, b = str(p.get("asset_id_a") or ""), str(p.get("asset_id_b") or "")
        vis, info = cv.flow(assets.load_image(a), assets.load_image(b))
        iid = _eph.put(vis, "optical_flow")
        return json.dumps({"a": a, "b": b, "result_image_id": iid, **info})

    def event_info(p):
        aid = str(_g(p, "asset_id", "input"))
        return json.dumps({"asset_id": aid, **events.info(assets.load_events(aid))})

    def event_accumulate(p):
        aid = str(_g(p, "asset_id", "input"))
        ev = assets.load_events(aid)
        meta = events.info(ev)
        w, h = events.sensor_size(ev)
        t0 = float(p.get("t0") or meta.get("t_min") or 0)
        t1 = float(p.get("t1") or (t0 + min(0.05, meta.get("duration") or 0.05)))
        mode = str(p.get("mode") or "polarity")
        frame = events.accumulate(ev, w, h, t0, t1, mode)
        iid = _eph.put(frame, "event_accumulate")
        return json.dumps({"source": aid, "result_image_id": iid, "t0": t0, "t1": t1, "mode": mode})

    def time_surface(p):
        aid = str(_g(p, "asset_id", "input"))
        ev = assets.load_events(aid)
        w, h = events.sensor_size(ev)
        tau = float(p.get("tau") or 0.03)
        frame = events.time_surface(ev, w, h, tau=tau)
        iid = _eph.put(frame, "time_surface")
        return json.dumps({"source": aid, "result_image_id": iid, "tau": tau})

    def event_rate(p):
        aid = str(_g(p, "asset_id", "input"))
        ev = assets.load_events(aid)
        meta = events.info(ev)
        t0 = float(p.get("t0") or meta.get("t_min") or 0)
        t1 = float(p.get("t1") or t0 + 0.05)
        return json.dumps({"asset_id": aid, "t0": t0, "t1": t1, **events.rate(ev, t0, t1)})

    def pose_convert(p):
        from app.domain.pose import qnorm

        raw = _g(p, "input", "query", "quat")
        data = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(data, dict):
            q, _ = parse_pose(data)
        else:
            q = qnorm(list(data)[:4])
        return json.dumps({"quat": np.asarray(q).tolist(), "R": quat_to_R(q).tolist()})

    def pose_error(p):
        raw = _g(p, "input", "query")
        data = json.loads(raw) if isinstance(raw, str) else raw
        qg, tg = parse_pose(data["gt"])
        qp, tp = parse_pose(data["pred"])
        return json.dumps({"rot_err_deg": rot_err_deg(qg, qp), "trans_err": float(np.linalg.norm(tg - tp))})

    def pose_sequence_error(p):
        gt = assets.load_json(str(p.get("gt_asset_id")))
        pred = assets.load_json(str(p.get("pred_asset_id")))
        if isinstance(gt, dict) and "poses" in gt:
            gt = gt["poses"]
        if isinstance(pred, dict) and "poses" in pred:
            pred = pred["poses"]
        r = sequence_errors(list(gt), list(pred))
        return json.dumps({k: v for k, v in r.items() if k not in {"rot_err_deg", "trans_err"}} | {
            "rot_head": r["rot_err_deg"][:8],
            "trans_head": r["trans_err"][:8],
        })

    def solve_pnp(p):
        data = json.loads(_g(p, "input", "query"))
        return json.dumps(
            cv.solve_pnp(
                np.asarray(data["object_points"], float),
                np.asarray(data["image_points"], float),
                np.asarray(data["K"], float),
            )
        )

    def academic_search(p):
        source = str(_g(p, "source", default="semantic_scholar"))
        res = academic.search(source, p)
        return json.dumps(res, ensure_ascii=False)

    def academic_search_all(p):
        keyword = str(_g(p, "keyword", "query", "input"))
        limit = p.get("max_results") or 5
        out = {}
        for src in ["semantic_scholar", "arxiv", "openalex"]:
            out[src] = academic.search(src, {"keyword": keyword, "max_results": limit})
        return json.dumps(out, ensure_ascii=False)

    def zotero_search(p):
        q = str(_g(p, "query", "keyword", "input"))
        ck = str(p.get("collection_key") or "")
        limit = p.get("max_results") or 10
        res = zotero.search(q, ck, int(limit))
        return json.dumps(res, ensure_ascii=False)

    def zotero_collections(p):
        return json.dumps({"collections": zotero.collections()}, ensure_ascii=False)

    def zotero_item(p):
        key = str(_g(p, "key", "item_key", "input"))
        return json.dumps(zotero.item(key), ensure_ascii=False)

    def write_review_tool(p):
        if llm is None:
            return json.dumps({"error": "LLM 未配置"})
        topic = str(_g(p, "topic", "query", "input"))
        lang = str(p.get("lang") or "zh")
        style = str(p.get("style") or "综述")
        return json.dumps({"text": writing.write_review(kb, llm, topic, lang, style)}, ensure_ascii=False)

    def polish_tool(p):
        if llm is None:
            return json.dumps({"error": "LLM 未配置"})
        draft = str(_g(p, "draft", "text", "input"))
        focus = str(p.get("focus") or "")
        return json.dumps({"text": writing.polish(kb, llm, draft, focus)}, ensure_ascii=False)

    def translate_tool(p):
        if llm is None:
            return json.dumps({"error": "LLM 未配置"})
        text = str(_g(p, "text", "input", "query"))
        direction = str(p.get("direction") or "en2zh")
        return json.dumps({"text": writing.translate(kb, llm, text, direction)}, ensure_ascii=False)

    def ideation_tool(p):
        if llm is None:
            return json.dumps({"error": "LLM 未配置"})
        from app.domain import ideation as _ideation
        topic = str(_g(p, "topic", "query", "input"))
        seed = str(p.get("seed_idea") or p.get("seed") or "")
        n = int(p.get("n_ideas") or 3)
        rounds = int(p.get("rounds") or 2)
        final = ""
        for evt in _ideation.run_debate(kb, llm, topic, n, rounds, seed):
            if evt.get("type") == "final":
                final = evt.get("text", "")
        return json.dumps({"ideas": final}, ensure_ascii=False)

    # ---- 航天器真实数据集 (spacecraft) ----
    def sc_list(p):
        return json.dumps(sc.list_targets(), ensure_ascii=False)

    def sc_frames(p):
        target = str(_g(p, "target", "input"))
        limit = int(p.get("limit") or 60)
        return json.dumps(sc.list_frames(target, limit), ensure_ascii=False)

    def sc_frame_info(p):
        target = str(_g(p, "target", "input"))
        idx = int(_g(p, "frame", "idx", default=0))
        return json.dumps(sc.frame_info(target, idx), ensure_ascii=False)

    def sc_pnp(p):
        target = str(_g(p, "target", "input"))
        idx = int(_g(p, "frame", "idx", default=0))
        return json.dumps(sc.pnp_validate(target, idx), ensure_ascii=False)

    def sc_pnp_sequence(p):
        target = str(_g(p, "target", "input"))
        step = int(p.get("step") or 1)
        return json.dumps(sc.pnp_sequence(target, step), ensure_ascii=False)

    def sc_event_stats(p):
        target = str(_g(p, "target", "input"))
        max_lines = int(p.get("max_lines") or 200000)
        return json.dumps(sc.event_stats(target, max_lines), ensure_ascii=False)

    def sc_event_frame(p):
        target = str(_g(p, "target", "input"))
        idx = int(_g(p, "frame", "idx", default=0))
        window = float(p.get("window_us") or 5000.0)
        img = sc.event_accumulate_around(target, idx, window)
        iid = _eph.put(img, f"{target}_event_frame_{idx}")
        return json.dumps({"target": target, "frame": idx, "result_image_id": iid, "window_us": window})

    def sc_model(p):
        target = str(_g(p, "target", "input"))
        return json.dumps(sc.model_info(target), ensure_ascii=False)

    def sc_viz_frame(p):
        target = str(_g(p, "target", "input"))
        idx = int(_g(p, "frame", "idx", default=0))
        img = sc.visualize_frame(target, idx)
        iid = _eph.put(img, f"{target}_viz_frame_{idx}")
        return json.dumps({"target": target, "frame": idx, "result_image_id": iid})

    def sc_viz_pnp(p):
        target = str(_g(p, "target", "input"))
        idx = int(_g(p, "frame", "idx", default=0))
        img = sc.visualize_pnp_reprojection(target, idx)
        iid = _eph.put(img, f"{target}_pnp_reprojection_{idx}")
        return json.dumps({"target": target, "frame": idx, "result_image_id": iid})

    def sc_viz_traj(p):
        target = str(_g(p, "target", "input"))
        img = sc.pose_trajectory(target)
        iid = _eph.put(img, f"{target}_pose_trajectory")
        return json.dumps({"target": target, "result_image_id": iid})

    def sc_viz_model(p):
        target = str(_g(p, "target", "input"))
        idx = int(_g(p, "frame", "idx", default=0))
        step = int(p.get("sample_step") or 20)
        img = sc.visualize_model_projection(target, idx, step)
        iid = _eph.put(img, f"{target}_model_projection_{idx}")
        return json.dumps({"target": target, "frame": idx, "result_image_id": iid})

    def sc_event_anim(p):
        import io
        import imageio.v2 as imageio

        target = str(_g(p, "target", "input"))
        idx = int(_g(p, "frame", "idx", default=0))
        n = int(p.get("n_frames") or 16)
        win = float(p.get("window_us") or 20000.0)
        frames = sc.event_animation_frames(target, idx, n, win)
        if not frames:
            return json.dumps({"error": "no events"})
        buf = io.BytesIO()
        imageio.mimsave(buf, frames, format="GIF", duration=0.12)
        iid = _eph.put_bytes(buf.getvalue(), "image/gif", f"{target}_event_anim_{idx}")
        return json.dumps({"target": target, "frame": idx, "result_image_id": iid, "n_frames": len(frames)})

    def sc_3d_model(p):
        target = str(_g(p, "target", "input"))
        elev = float(p.get("elev") or 20)
        azim = float(p.get("azim") or 35)
        img = sc.viz_3d_model(target, elev, azim)
        iid = _eph.put(img, f"{target}_3d_model")
        return json.dumps({"target": target, "result_image_id": iid})

    def sc_3d_pose(p):
        target = str(_g(p, "target", "input"))
        idx = int(_g(p, "frame", "idx", default=0))
        img = sc.viz_3d_pose(target, idx)
        iid = _eph.put(img, f"{target}_3d_pose_{idx}")
        return json.dumps({"target": target, "frame": idx, "result_image_id": iid})

    def sc_3d_rotate(p):
        import io
        import imageio.v2 as imageio

        target = str(_g(p, "target", "input"))
        n = int(p.get("n_frames") or 24)
        frames = sc.viz_3d_rotate_frames(target, n)
        if not frames:
            return json.dumps({"error": "no 3d model"})
        buf = io.BytesIO()
        imageio.mimsave(buf, frames, format="GIF", duration=0.1)
        iid = _eph.put_bytes(buf.getvalue(), "image/gif", f"{target}_3d_rotate")
        return json.dumps({"target": target, "result_image_id": iid, "n_frames": len(frames)})

    def sc_optical_montage(p):
        target = str(_g(p, "target", "input"))
        n = int(p.get("n") or 9)
        cols = int(p.get("cols") or 3)
        img = sc.viz_optical_montage(target, n, cols)
        iid = _eph.put(img, f"{target}_optical_montage")
        return json.dumps({"target": target, "result_image_id": iid, "n_frames": n})

    def sc_optical_event_pair(p):
        target = str(_g(p, "target", "input"))
        idx = int(_g(p, "frame", "idx", default=0))
        img = sc.viz_optical_event_pair(target, idx)
        iid = _eph.put(img, f"{target}_optical_event_pair_{idx}")
        return json.dumps({"target": target, "frame": idx, "result_image_id": iid})

    specs = [
        ("list_assets", "列出已上传资源，可选 kind=image|events|pose", list_assets),
        ("kb_search", "文献库语义检索 query=...", kb_search),
        ("kb_ask", "文献RAG上下文 query=...", kb_ask),
        ("image_stats", "图像统计 asset_id=", image_stats),
        ("blur_score", "模糊度Laplacian asset_id=", blur_score),
        ("canny_edge", "Canny边缘 asset_id=", canny_edge),
        ("orb_features", "ORB特征 asset_id=", orb_features),
        ("orb_match", "双图ORB匹配 asset_id_a=,asset_id_b=", orb_match),
        ("optical_flow", "Farneback光流 asset_id_a=,asset_id_b=", optical_flow),
        ("event_info", "事件流信息 asset_id=", event_info),
        ("event_accumulate", "事件累积帧 asset_id=,可选t0,t1,mode", event_accumulate),
        ("time_surface", "时间表面 asset_id=,可选tau", time_surface),
        ("event_rate", "事件率 asset_id=,可选t0,t1", event_rate),
        ("pose_convert", "四元数转R", pose_convert),
        ("pose_error", "单帧姿态误差 JSON gt/pred", pose_error),
        ("pose_sequence_error", "序列误差 gt_asset_id=,pred_asset_id=", pose_sequence_error),
        ("solve_pnp", "OpenCV solvePnP JSON", solve_pnp),
        ("academic_search", "学术检索 source=semantic_scholar|arxiv|openalex|crossref, keyword=, 可选field/year_from/year_to/author/category", academic_search),
        ("academic_search_all", "多源学术检索 keyword= (semantic_scholar+arxiv+openalex)", academic_search_all),
        ("zotero_search", "本地Zotero检索 query=, 可选collection_key/max_results", zotero_search),
        ("zotero_collections", "列出本地Zotero收藏夹", zotero_collections),
        ("zotero_item", "读取Zotero条目详情 key=", zotero_item),
        ("write_review", "基于知识库写综述/研究背景 topic=, 可选lang=zh|en, style=综述|研究背景", write_review_tool),
        ("polish_draft", "基于知识库润色草稿 draft=, 可选focus=", polish_tool),
        ("translate", "学术翻译 text=, direction=en2zh|zh2en (用知识库术语统一)", translate_tool),
        ("ideation", "学术idea生成(双agent辩论) topic=, 可选seed_idea=,n_ideas=,rounds=", ideation_tool),
        ("spacecraft_list", "列出航天器真实数据集目标(含帧数/关键点/3D模型)", sc_list),
        ("spacecraft_frames", "列出某目标保留的帧清单 target=, 可选limit= (含真值平移/深度/bbox)", sc_frames),
        ("spacecraft_frame_info", "某帧详情 target=, frame= (真值pose R/t、keypoints、bbox、内参)", sc_frame_info),
        ("spacecraft_pnp", "真实PnP验证 target=, frame= (用landmarks+keypoints+内参解算,对比真值姿态误差)", sc_pnp),
        ("spacecraft_pnp_sequence", "批量PnP验证 target=, 可选step= (旋转/平移误差统计)", sc_pnp_sequence),
        ("spacecraft_event_stats", "事件流统计 target=, 可选max_lines= (事件数/极性比/率/传感器尺寸)", sc_event_stats),
        ("spacecraft_event_frame", "事件累积帧 target=, frame=, 可选window_us= (返回result_image_id)", sc_event_frame),
        ("spacecraft_model", "3D模型信息 target= (STL零件/密集点云数)", sc_model),
        ("spacecraft_viz_frame", "可视化:RGB+2D关键点+bbox target=, frame= (返回result_image_id)", sc_viz_frame),
        ("spacecraft_viz_pnp", "可视化:PnP重投影误差(GT绿/重投影红+每点误差条形图) target=, frame=", sc_viz_pnp),
        ("spacecraft_viz_trajectory", "可视化:真值3D平移轨迹+三视图 target=", sc_viz_traj),
        ("spacecraft_viz_model", "可视化:3D密集点云投影到RGB target=, frame=, 可选sample_step=", sc_viz_model),
        ("spacecraft_event_anim", "动画:事件累积GIF target=, frame=, 可选n_frames=,window_us= (返回result_image_id)", sc_event_anim),
        ("spacecraft_3d_model", "3D可视化:模型wireframe网格+关键点 target=, 可选elev=,azim= (返回result_image_id)", sc_3d_model),
        ("spacecraft_3d_pose", "3D可视化:真值6DoF位姿坐标系+相机视锥 target=, frame= (返回result_image_id)", sc_3d_pose),
        ("spacecraft_3d_rotate", "3D动画:模型旋转GIF target=, 可选n_frames= (返回result_image_id)", sc_3d_rotate),
        ("spacecraft_optical_montage", "光学图像同时可视化:多帧RGB平铺(关键点+bbox) target=, 可选n=9,cols=3 (返回result_image_id)", sc_optical_montage),
        ("spacecraft_optical_event_pair", "光学+事件同时可视化:同帧RGB与事件累积帧并排 target=, frame= (返回result_image_id)", sc_optical_event_pair),
    ]
    for name, desc, fn in specs:
        reg.add(_Fn(name, desc, fn))
    return reg
