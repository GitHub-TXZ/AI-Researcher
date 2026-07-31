# PoseLab — 航天器光学 / 事件相机 6DoF 姿态估计研究助手

用**自然语言**驱动一个会调用工具的 Agent，对**光学图像、事件相机流、6DoF 姿态、3D 模型、文献知识库**做端到端分析与高逼格可视化。内置真实航天器数据集（SPEED 风格），并集成 Zotero、学术检索、AI 写作与 idea 生成，构成一个面向「航天器位姿估计」研究的完整工作台。

---

## ✨ 核心能力

- **自然语言对话 + 工具调用**：单一强力 Analyst Agent，通过 `[TOOL_CALL:name:params]` 协议自主调用 40+ 工具，过程流式可见（思考 / 调用 / 结果时间线）。
- **对话上下文记忆**：前端携带最近若干轮对话历史，Agent 能理解「它 / 再 / 换成」等指代，跨轮延续。
- **真实数据集分析**：内置 `spacecraft/` 三个目标（cassini-1-close / satty-1-close / soho-1-close），含成对 RGB+事件帧、原始事件流、真值 6DoF 姿态、3D 关键点与内参、3D 模型（STL + 密集点云）。
- **高逼格可视化**（产物在对话内联展示，可一键保存，**不落盘**）：
  - 光学：RGB + 2D 关键点 + bbox、多帧平铺 montage、光学 vs 事件并排
  - 姿态：PnP 重投影误差图、真值 3D 平移轨迹（3D + 三视图）
  - 3D：wireframe 模型 + 关键点、真值 6DoF 位姿坐标系 + 相机视锥、3D 点云投影、3D 模型旋转 GIF
  - 事件：事件累积帧、事件累积 GIF 动画
- **文献知识库（RAG）**：PDF / Markdown / TXT 入库，PyMuPDF 解析全文、切片、哈希向量检索；支持删除。
- **Zotero 一键入库**：连接本地 Zotero（`localhost:23119`），按收藏夹批量导入——**真实下载 PDF 二进制并用 PyMuPDF 解析全文**（处理 `file://` 重定向），而非仅取元数据。
- **学术检索**：Semantic Scholar / arXiv / OpenAlex / CrossRef 四源。
- **AI 写作**：综述 / 研究背景生成、草稿润色、学术翻译（术语与知识库对齐）。
- **idea 生成**：Generator × Critic × Refiner 多智能体辩论（Reflection 范式），流式输出。
- **领域主动推送**：左侧「领域推送」信息流，实时聚合 arXiv 前沿论文 + GitHub 高星仓库。
- **持久视图**：切换标签页时后台任务继续运行，回来仍可见结果，页面间互不串扰。

---

## 🧱 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI · Uvicorn · Pydantic-settings · NumPy · OpenCV · PyMuPDF · imageio · matplotlib |
| LLM | 兼容 OpenAI 接口（默认 DeepSeek `deepseek-chat`），urllib 直连流式 |
| Agent | 自研 `ToolAgent` 内核（可改、可扩展的事件发射 + 工具作用域） |
| 前端 | React 18 · Vite · TypeScript · Tailwind 风格 CSS · 自研轻量 Markdown 渲染 |
| 通信 | SSE（Server-Sent Events）流式：对话、idea 辩论、思考过程 |
| 部署 | docker-compose（api + web） |

---

## 🚀 快速开始

### 1. 配置 LLM

`backend/.env`：

```env
LLM_MODEL_ID="deepseek-chat"
LLM_BASE_URL="https://api.deepseek.com"
LLM_API_KEY="sk-你的密钥"
LLM_TIMEOUT=60
# 可选：自定义数据目录
# DATA_DIR="/path/to/data"
# 可选：自定义航天器数据集目录（默认 <repo>/spacecraft）
# SPACECRAFT_DIR="/path/to/spacecraft"
# 可选：本地 Zotero
# ZOTERO_BASE_URL="http://localhost:23119/api"
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
export PYTHONPATH=.
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev      # 开发模式 http://127.0.0.1:5173
# 或构建后部署：npm run build
```

### 4. Docker 一键起

```bash
docker-compose up --build
# web: http://127.0.0.1:5173   api: http://127.0.0.1:8000
```

打开前端后，左侧「自然语言指令示例」可直接点击填入对话框体验。

- API 文档：http://127.0.0.1:8000/docs

---

## 🗂 真实航天器数据集（`spacecraft/`）

SPEED 风格数据集，三个目标：

| 目标 | 帧 | 3D 关键点 | STL 零件 | 密集点云 |
|---|---|---|---|---|
| cassini-1-close | 30 | 18 | 12 | 226k |
| satty-1-close | 30 | 18 | 1 | 107k |
| soho-1-close | 30 | 26 | 8 | 299k |

每个目标目录结构：

```text
spacecraft/<target>-1-close/
  frames/NNNNN_rgb.png, NNNNN_event.png   成对光学 / 事件累积帧
  events/events.txt                        原始事件流 t,x,y,p
  timestamps.txt                           帧时间戳 name, ts
  test.json                                landmarks_3d, wireframe_points/faces,
                                           intrinsics, annotations[pose,keypoints,bbox]
spacecraft/models/<target>/                STL 零件 + dense.json 点云
```

> 数据集已做瘦身：每目标保留代表性帧子集，但 3D 模型完整保留，兼顾体量与一般性。

---

## 🛠 工具目录（40+）

Agent 可自主调用，按域分组：

**资源 / 通用**
`list_assets`

**图像（CV）**
`image_stats` · `blur_score` · `canny_edge` · `orb_features` · `orb_match` · `optical_flow`

**事件相机**
`event_info` · `event_accumulate` · `time_surface` · `event_rate`

**姿态 / PnP**
`pose_convert` · `pose_error` · `pose_sequence_error` · `solve_pnp`

**航天器真实数据集**
`spacecraft_list` · `spacecraft_frames` · `spacecraft_frame_info`
`spacecraft_pnp` · `spacecraft_pnp_sequence`（对比真值旋转 / 平移误差）
`spacecraft_event_stats` · `spacecraft_event_frame`
`spacecraft_model`

**可视化（产物内联展示，不落盘）**
- 光学：`spacecraft_viz_frame` · `spacecraft_optical_montage` · `spacecraft_optical_event_pair`
- 姿态：`spacecraft_viz_pnp`（重投影误差）· `spacecraft_viz_trajectory`（3D 轨迹）· `spacecraft_viz_model`（点云投影）
- 3D：`spacecraft_3d_model` · `spacecraft_3d_pose` · `spacecraft_3d_rotate`（GIF）
- 事件动画：`spacecraft_event_anim`（GIF）

**知识库 / 文献**
`kb_search` · `kb_ask` · `academic_search` · `academic_search_all`
`zotero_collections` · `zotero_search` · `zotero_item`

**写作 / idea**
`write_review` · `polish_draft` · `translate` · `ideation`

---

## 💬 自然语言示例

直接在对话框输入即可，也可点左侧示例一键填入：

- 列出航天器真实数据集的三个目标与规模
- 对 cassini 第 20 帧做真实 PnP 验证，对比真值姿态误差
- 同时可视化 cassini 的 9 帧光学图像（平铺，含关键点 + bbox）
- 3D 可视化 cassini 第 15 帧的真值 6DoF 位姿坐标系与相机视锥
- 生成 soho 第 25 帧附近的事件累积 GIF 动画
- 基于知识库写一段「事件相机 6DoF 位姿估计」研究背景综述
- 检索 spacecraft pose estimation 的最新 arXiv 论文

---

## 🏗 架构

```text
前端 (React SPA)
  ├ 分析台  AssetLibrary │ ChatPanel │ ToolPanel
  ├ 知识库  KnowledgePage
  ├ 学术检索 AcademicPage
  ├ Zotero   ZoteroPage
  ├ 写作     WritingPage
  ├ idea     IdeationPage
  └ 左侧栏  自然语言指令示例 + 领域推送(DiscoveryFeed)
        │  SSE 流式
        ▼
后端 (FastAPI)
  api/   assets · kb · chat · zotero · write · ideation · meta(discovery/spacecraft)
  crew/  ResearchCrew（编排）→ core/ToolAgent（工具调用内核 + 事件发射）
  domain/ cv · events · pose · spacecraft · academic · zotero · writing · ideation · discovery
  storage/ assets(落盘) · kb(落盘) · ephemeral(内存级可视化产物)
  tools/factory.py  全部工具注册
```

**可视化产物存储策略**：Agent 产出的图 / GIF 进入进程内存级 `ephemeral` 存储，经 `/api/assets/inline/{id}` 在对话内联展示，点「保存」才下载到本地——**不污染资源库、不落盘**；后端重启后清空（与对话本身不持久化一致）。

### 🖼 架构与成果图

![系统总体架构](report_assets/fig1_architecture.png)

*图 1 · 系统总体架构：前端 SPA 通过 SSE 与 FastAPI 后端流式通信，后端编排层调用 ToolAgent 内核与各领域工具。*

![学术闭环](report_assets/fig2_academic_loop.png)

*图 2 · 学术研究闭环：从文献检索 / Zotero 入库 → 知识库 RAG → 分析 / 写作 / idea 生成，形成可迭代的研究循环。*

![Agent 内核](report_assets/fig3_agent_kernel.png)

*图 3 · ToolAgent 内核：`[TOOL_CALL:name:params]` 协议解析、工具作用域、事件发射（思考 / 调用 / 结果 / token 流）。*

![RAG 与多智能体](report_assets/fig4_rag_multiagent.png)

*图 4 · RAG 检索 + 多智能体辩论（Generator × Critic × Refiner，Reflection 范式）。*

---

## 🖼 操作实例

![操作实例 01](report_assets/demo/01.png)
![操作实例 02](report_assets/demo/02.png)
![操作实例 03](report_assets/demo/03.png)
![操作实例 04](report_assets/demo/04.png)
![操作实例 05](report_assets/demo/05.png)
![操作实例 06](report_assets/demo/06.png)
![操作实例 07](report_assets/demo/07.png)
![操作实例 08](report_assets/demo/08.png)
![操作实例 09](report_assets/demo/09.png)
![操作实例 10](report_assets/demo/10.png)
![操作实例 11](report_assets/demo/11.png)
![操作实例 12](report_assets/demo/12.png)
![操作实例 13](report_assets/demo/13.png)
![操作实例 14](report_assets/demo/14.png)
![操作实例 15](report_assets/demo/15.png)
![操作实例 16](report_assets/demo/16.png)
![操作实例 17](report_assets/demo/17.png)
![操作实例 18](report_assets/demo/18.png)
![操作实例 19](report_assets/demo/19.png)

---

## 📦 数据持久化说明

| 内容 | 是否持久化 | 位置 |
|---|---|---|
| 用户上传的图像 / 事件 / 姿态 | ✅ 短暂落盘 | `data/uploads/` |
| 知识库文献（元数据 / 切片 / 向量 / 源 PDF） | ✅ 永久落盘 | `data/kb_index/` · `data/papers/` |
| Agent 可视化产物（图 / GIF） | ❌ 仅内存 | `ephemeral`（重启清空） |
| 对话历史 / 思考过程 / 检索流 | ❌ 仅内存 | 前端 React state |

---

## 📁 项目结构

```text
pose_research_assistant/
  backend/
    app/
      main.py              FastAPI 入口
      settings.py          配置（.env 驱动）
      core/                LLM 客户端 + ToolAgent 内核 + 工具基类
      domain/              各领域算法（cv/events/pose/spacecraft/academic/zotero/writing/ideation/discovery）
      storage/             assets · kb · ephemeral
      tools/factory.py     全部工具注册
      crew/orchestrator.py ResearchCrew 编排
      api/                 路由（assets/kb/chat/zotero/write/ideation/meta）
    requirements.txt
    .env
  frontend/
    src/
      App.tsx              视图路由 + 持久视图
      api/client.ts        API + SSE 客户端
      components/          AssetLibrary · ChatPanel · ToolPanel · KnowledgePage
                          · AcademicPage · ZoteroPage · WritingPage · IdeationPage
                          · DiscoveryFeed · Markdown · icons
    vite.config.ts         代理 /api → 后端
  spacecraft/              真实航天器数据集
  data/                    用户数据（上传 / 知识库）
  docker-compose.yml
```

---

## 🔧 配置项（`backend/app/settings.py`）

| 变量 | 默认 | 说明 |
|---|---|---|
| `LLM_MODEL_ID` | `gpt-4o-mini` | 模型 id（推荐 `deepseek-chat`） |
| `LLM_BASE_URL` | OpenAI | 兼容 OpenAI 接口的端点 |
| `LLM_API_KEY` | — | 密钥 |
| `LLM_TIMEOUT` | 60 | 超时秒数 |
| `DATA_DIR` | `<repo>/data` | 用户数据根目录 |
| `SPACECRAFT_DIR` | `<repo>/spacecraft` | 航天器数据集目录 |
| `ZOTERO_BASE_URL` | `http://localhost:23119/api` | 本地 Zotero API |
| `CORS_ORIGINS` | `localhost:5173,...` | 跨域白名单 |

---

## 📜 许可

本项目用于航天器位姿估计研究辅助。数据集与第三方 API 请遵循各自许可。
