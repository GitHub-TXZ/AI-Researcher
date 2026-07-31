import { useEffect, useState } from "react";
import type { Asset, Evt, Paper, Tool } from "./api/client";
import { getAssets, getPapers, getTools } from "./api/client";
import { AssetLibrary } from "./components/AssetLibrary";
import { AcademicPage } from "./components/AcademicPage";
import { ChatPanel } from "./components/ChatPanel";
import { IdeationPage } from "./components/IdeationPage";
import { KnowledgePage } from "./components/KnowledgePage";
import { ToolPanel } from "./components/ToolPanel";
import { WritingPage } from "./components/WritingPage";
import { ZoteroPage } from "./components/ZoteroPage";
import { IconChat, IconBook, IconSearch, IconLayers, IconWrench, IconActivity } from "./components/icons";
import "./styles/global.css";
import "./styles/components.css";

type View = "work" | "kb" | "academic" | "zotero" | "write" | "idea";

export default function App() {
  const [view, setView] = useState<View>("work");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selected, setSelected] = useState("");
  const [trace, setTrace] = useState<Evt[]>([]);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState("");

  async function refresh() {
    try {
      const [a, t, p] = await Promise.all([getAssets(), getTools(), getPapers()]);
      setAssets(a.assets);
      setTools(t.tools);
      setPapers(p.papers);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function pickTool(name: string) {
    const hint = `调用工具 ${name}`;
    if (selected) {
      setPending(`${hint}，参数 asset_id=${selected}`);
    } else {
      setPending(hint);
    }
    setView("work");
  }

  function runPrompt(text: string) {
    setPending(text);
    setView("work");
  }

  function quickAnalysis(action: string) {
    if (!selected) return;
    setPending(`${action} asset_id=${selected}`);
    setView("work");
  }

  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="logo">P</div>
        <button
          className={`nav-btn ${view === "work" ? "active" : ""}`}
          title="分析台"
          onClick={() => setView("work")}
        >
          <IconChat />
        </button>
        <button
          className={`nav-btn ${view === "kb" ? "active" : ""}`}
          title="知识库"
          onClick={() => setView("kb")}
        >
          <IconBook />
        </button>
        <button
          className={`nav-btn ${view === "academic" ? "active" : ""}`}
          title="学术检索"
          onClick={() => setView("academic")}
        >
          <IconSearch />
        </button>
        <button
          className={`nav-btn ${view === "zotero" ? "active" : ""}`}
          title="本地 Zotero"
          onClick={() => setView("zotero")}
        >
          <IconLayers />
        </button>
        <button
          className={`nav-btn ${view === "write" ? "active" : ""}`}
          title="写作与翻译"
          onClick={() => setView("write")}
        >
          <IconWrench />
        </button>
        <button
          className={`nav-btn ${view === "idea" ? "active" : ""}`}
          title="idea 生成"
          onClick={() => setView("idea")}
        >
          <IconActivity />
        </button>
        <div className="nav-spacer" />
      </nav>

      {/* Each view stays mounted; inactive ones are hidden via display:none so
          in-flight background tasks (streaming chat / ideation) keep running and
          their state persists when you switch back. */}
      <section className={`view work ${view === "work" ? "active" : ""}`}>
        <AssetLibrary assets={assets} selected={selected} onSelect={setSelected} onUploaded={refresh} onPrompt={runPrompt} />
        <ChatPanel
          selected={selected}
          onDone={refresh}
          onTrace={(e) => setTrace((t) => [...t.slice(-60), e])}
          busy={busy}
          setBusy={setBusy}
          pending={pending}
          setPending={setPending}
        />
        <ToolPanel tools={tools} onPick={pickTool} trace={trace} />
      </section>

      <section className={`view with-rail ${view === "kb" ? "active" : ""}`}>
        <AssetLibrary assets={assets} selected={selected} onSelect={setSelected} onUploaded={refresh} onPrompt={runPrompt} />
        <KnowledgePage papers={papers} onIngested={refresh} />
      </section>

      <section className={`view with-rail ${view === "academic" ? "active" : ""}`}>
        <AssetLibrary assets={assets} selected={selected} onSelect={setSelected} onUploaded={refresh} onPrompt={runPrompt} />
        <AcademicPage />
      </section>

      <section className={`view with-rail ${view === "zotero" ? "active" : ""}`}>
        <AssetLibrary assets={assets} selected={selected} onSelect={setSelected} onUploaded={refresh} onPrompt={runPrompt} />
        <ZoteroPage onIngested={refresh} />
      </section>

      <section className={`view single ${view === "write" ? "active" : ""}`}>
        <WritingPage />
      </section>

      <section className={`view single ${view === "idea" ? "active" : ""}`}>
        <IdeationPage />
      </section>
    </div>
  );
}
