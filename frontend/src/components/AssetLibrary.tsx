import { useEffect, useRef, useState } from "react";
import type { Asset } from "../api/client";
import { getSpacecraftTargets, uploadAsset } from "../api/client";
import type { SpacecraftTarget } from "../api/client";
import { IconUpload, IconImage, IconActivity } from "./icons";
import { DiscoveryFeed } from "./DiscoveryFeed";

const KIND_COLORS: Record<string, string> = {
  image: "image",
  events: "events",
  pose: "pose",
  other: "other",
};

const NL_PROMPTS: { group: string; items: string[] }[] = [
  {
    group: "真实数据集分析",
    items: [
      "列出航天器数据集的三个目标与规模",
      "对 cassini 第 20 帧做 PnP 验证，对比真值姿态的旋转/平移误差",
      "对三个目标批量 PnP 验证，给出误差统计表",
      "统计 soho 的事件流并生成第 25 帧附近的事件累积帧",
    ],
  },
  {
    group: "高逼格可视化",
    items: [
      "可视化 cassini 第 15 帧：RGB + 2D 关键点 + bbox",
      "画 cassini 的真值 3D 姿态轨迹图",
      "把 cassini 的 3D 点云投影到第 15 帧 RGB 上",
      "生成 soho 第 25 帧附近的事件累积 GIF 动画",
      "对 cassini 第 15 帧做 PnP 重投影误差可视化",
    ],
  },
  {
    group: "3D 数据可视化",
    items: [
      "3D 可视化 cassini 的模型（wireframe 网格 + 关键点）",
      "3D 可视化 cassini 第 15 帧的真值 6DoF 位姿坐标系与相机视锥",
      "生成 cassini 3D 模型旋转 GIF 动画",
      "对比三个目标的 3D 模型",
    ],
  },
  {
    group: "光学图像同时可视化",
    items: [
      "同时可视化 cassini 的 9 帧光学图像（平铺，含关键点+bbox）",
      "把 soho 的 12 帧光学图像平铺成网格",
      "并排显示 cassini 第 15 帧的光学 RGB 与事件累积帧",
    ],
  },
  {
    group: "上传数据分析",
    items: [
      "对当前图像做 blur_score 模糊度评估",
      "对当前图像做 Canny 边缘检测",
      "对当前图像做 ORB 特征检测",
      "对两张图做 Farneback 光流",
      "对当前事件流做累积帧（极性模式）",
    ],
  },
  {
    group: "文献与写作",
    items: [
      "检索 spacecraft pose estimation 的最新 arXiv 论文",
      "基于知识库写一段「事件相机 6DoF 位姿估计」研究背景综述",
      "润色我写的这段草稿，使其更学术化",
      "把这段中文翻译成学术英文，术语与知识库一致",
    ],
  },
];

export function AssetLibrary({
  assets,
  selected,
  onSelect,
  onUploaded,
  onPrompt,
}: {
  assets: Asset[];
  selected: string;
  onSelect: (id: string) => void;
  onUploaded: () => void;
  onPrompt?: (text: string) => void;
}) {
  const [kind, setKind] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [targets, setTargets] = useState<SpacecraftTarget[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    getSpacecraftTargets()
      .then((r) => setTargets(r.targets || []))
      .catch(() => setTargets([]));
  }, []);

  async function doUpload(file: File) {
    setBusy(true);
    setErr("");
    try {
      await uploadAsset(file, kind);
      onUploaded();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel panel-l">
      <div className="panel-header">
        <div className="panel-title">资源库</div>
        <div className="panel-subtitle">{assets.length} 个资源</div>
      </div>
      <div className="panel-body">
        <div
          className={`upload-zone ${dragOver ? "has-file" : ""}`}
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files?.[0];
            if (f) doUpload(f);
          }}
        >
          <IconUpload style={{ marginBottom: 6 }} />
          <div>{busy ? "上传中…" : "拖放或点击上传"}</div>
          <div className="muted" style={{ marginTop: 4 }}>
            图像 / 事件 .npy .csv / 姿态 .json · PDF 请到「知识库」入库
          </div>
          <input
            ref={fileRef}
            type="file"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) doUpload(f);
              e.target.value = "";
            }}
          />
        </div>

        <select
          className="field"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          style={{ marginTop: 8 }}
        >
          <option value="">自动识别类型</option>
          <option value="image">image (含可视化/GIF)</option>
          <option value="events">events</option>
          <option value="pose">pose</option>
          <option value="other">other</option>
        </select>

        {err && <div className="muted" style={{ color: "var(--rose)", marginTop: 6 }}>{err}</div>}

        {targets.length > 0 && (
          <div className="sc-dataset" style={{ marginTop: 12 }}>
            <div className="sc-dataset-title">航天器真实数据集</div>
            {targets.map((t) => (
              <div key={t.target} className="card sc-target">
                <div className="sc-target-name">{t.target}</div>
                <div className="sc-target-stats">
                  <span>{t.frames} 帧</span>
                  <span>{t.landmarks_3d} 关键点</span>
                  <span>{t.stl_parts} STL</span>
                  <span>{(t.dense_points / 1000).toFixed(0)}k 点云</span>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="nl-prompts" style={{ marginTop: 14 }}>
          <div className="nl-prompts-title">自然语言指令示例</div>
          <div className="nl-prompts-hint muted">
            直接在右侧对话框用自然语言描述需求即可，点击下方示例可一键填入。
          </div>
          {NL_PROMPTS.map((g) => (
            <div key={g.group} className="nl-prompt-group">
              <div className="nl-prompt-group-label">{g.group}</div>
              {g.items.map((p) => (
                <button
                  key={p}
                  className="nl-prompt-chip"
                  onClick={() => onPrompt?.(p)}
                  title="填入对话框"
                >
                  {p}
                </button>
              ))}
            </div>
          ))}
        </div>

        <div className="list" style={{ marginTop: 12 }}>
          {assets.map((a) => (
            <div
              key={a.id}
              className={`card asset-item ${selected === a.id ? "selected" : ""}`}
              onClick={() => onSelect(a.id)}
            >
              <div className="row between">
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="row" style={{ gap: 6 }}>
                    <span className={`badge ${KIND_COLORS[a.kind] || "other"}`}>{a.kind}</span>
                    {a.kind === "image" && <IconImage width={12} height={12} style={{ color: "var(--text-3)" }} />}
                    {a.kind === "events" && <IconActivity width={12} height={12} style={{ color: "var(--text-3)" }} />}
                  </div>
                  <div className="aid" style={{ marginTop: 4 }}>
                    {a.id.slice(0, 8)}
                  </div>
                  <div className="fname">{a.filename}</div>
                  {a.meta && "n" in a.meta && <div className="muted">{String(a.meta.n)} events</div>}
                  {a.meta && "w" in a.meta && <div className="muted">{String(a.meta.w)}×{String(a.meta.h)}</div>}
                </div>
              </div>
              {a.kind === "image" && (
                <span className="badge viz" title="可视化/图片产物">viz</span>
              )}
            </div>
          ))}
          {!assets.length && <div className="muted" style={{ textAlign: "center", padding: 20 }}>暂无资源</div>}
        </div>

        <DiscoveryFeed />
      </div>
    </div>
  );
}
