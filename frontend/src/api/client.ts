export type Asset = {
  id: string;
  kind: "image" | "events" | "pose" | "other";
  filename: string;
  tags: string[];
  meta: Record<string, unknown>;
};

export type Tool = { name: string; description: string; category?: string };

export type Paper = { id: string; title: string; n_chunks: number; tags: string[] };

export type Evt = {
  type: string;
  agent?: string;
  text?: string;
  tool?: string;
  args?: string;
  summary?: string;
  message?: string;
  goal?: string;
  image_id?: string;
  title?: string;
};

export type ChatImage = { id: string; title: string };

export type Msg = {
  id: string;
  role: "user" | "bot" | "tool";
  text: string;
  agent?: string;
  tool?: string;
  ts: number;
  steps?: Step[];
  images?: ChatImage[];
};

export type Step = {
  kind: "start" | "thinking" | "tool_call" | "tool_result" | "done";
  text?: string;
  tool?: string;
  args?: string;
  summary?: string;
  goal?: string;
  ts: number;
};

async function jget<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

async function jpost<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || `${r.status}`);
  return data as T;
}

export async function getAssets() {
  return jget<{ assets: Asset[] }>("/api/assets");
}
export async function getTools() {
  return jget<{ tools: Tool[] }>("/api/tools");
}
export async function getSpacecraftTargets() {
  return jget<{ source: string; targets: SpacecraftTarget[] }>("/api/spacecraft/targets");
}

export interface DiscoveryItem {
  type: "paper" | "repo";
  source: string;
  title: string;
  authors: string[];
  year: string | null;
  abstract: string;
  url: string;
  pdf?: string;
  stars?: number;
  language?: string;
  venue: string;
  tags: string[];
}

export async function getDiscoveryFeed() {
  return jget<{
    ok: boolean;
    papers: DiscoveryItem[];
    repos: DiscoveryItem[];
    n_papers: number;
    n_repos: number;
  }>("/api/discovery/feed");
}

export interface SpacecraftTarget {
  target: string;
  frames: number;
  landmarks_3d: number;
  wireframe_points: number;
  stl_parts: number;
  dense_points: number;
}
export async function getPapers() {
  return jget<{ papers: Paper[] }>("/api/kb/papers");
}

export async function uploadAsset(file: File, kind = "", tags = ""): Promise<Asset> {
  const fd = new FormData();
  fd.append("file", file);
  if (kind) fd.append("kind", kind);
  if (tags) fd.append("tags", tags);
  const r = await fetch("/api/assets/upload", { method: "POST", body: fd });
  const d = await r.json();
  if (!r.ok) throw new Error(d.detail || `${r.status}`);
  return d.asset;
}

export async function uploadPaper(file: File, tags = "", title = ""): Promise<Paper> {
  const fd = new FormData();
  fd.append("file", file);
  if (tags) fd.append("tags", tags);
  if (title) fd.append("title", title);
  const r = await fetch("/api/kb/papers", { method: "POST", body: fd });
  const d = await r.json();
  if (!r.ok) throw new Error(d.detail || `${r.status}`);
  return d.paper;
}

export async function execTool(tool: string, params: Record<string, unknown>) {
  return jpost<{ ok: boolean; result: unknown; error?: string }>(`/api/tools/exec`, { tool, params });
}

export async function kbSearch(query: string, top_k = 5) {
  return jpost<{ hits: unknown[]; context: string }>(`/api/kb/search`, { query, top_k });
}

export async function deletePaper(paper_id: string) {
  const r = await fetch(`/api/kb/papers/${paper_id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<{ ok: boolean; paper_id: string }>;
}

export type AcademicPaper = {
  title: string;
  authors: string[];
  year?: number | string;
  venue?: string;
  citations?: number;
  abstract?: string;
  doi?: string;
  arxiv?: string;
  pdf?: string;
  fields?: string[];
};

export async function academicSearch(body: {
  source: string;
  keyword: string;
  field?: string;
  year_from?: string;
  year_to?: string;
  author?: string;
  category?: string;
  max_results?: number;
}) {
  return jpost<{ ok: boolean; result: { source: string; count: number; papers: AcademicPaper[]; error?: string }; formatted: string }>(
    `/api/academic/search`,
    body,
  );
}

export type ZoteroItem = {
  key: string;
  itemType: string;
  title: string;
  creators: string;
  year: string;
  abstract: string;
  doi: string;
  url: string;
  publication: string;
  tags: string[];
};

export type ZoteroCollection = { key: string; name: string; parent?: string; n_items: number };

export async function zoteroPing() {
  return jget<{ online: boolean; base: string; error?: string }>(`/api/zotero/ping`);
}
export async function zoteroCollections() {
  return jget<{ collections: ZoteroCollection[] }>(`/api/zotero/collections`);
}
export async function zoteroSearch(query: string, collection_key = "", limit = 20) {
  return jpost<{ count: number; items: ZoteroItem[] }>(`/api/zotero/search`, { query, collection_key, limit });
}
export async function zoteroIngest(item_key: string, tags = "", use_full_text = true) {
  return jpost<{ ok: boolean; paper: Paper }>(`/api/zotero/ingest`, { item_key, tags, use_full_text });
}
export async function zoteroIngestCollection(collection_key: string, use_full_text = true, limit = 100) {
  return jpost<{ ok: boolean; ingested: { key: string; title: string }[]; failed: unknown[]; n: number }>(
    `/api/zotero/ingest-collection`,
    { collection_key, use_full_text, limit },
  );
}

export async function writeReview(topic: string, lang = "zh", style = "综述") {
  return jpost<{ ok: boolean; text: string; error?: string }>(`/api/write/review`, { topic, lang, style });
}
export async function polishDraft(draft: string, focus = "") {
  return jpost<{ ok: boolean; text: string; error?: string }>(`/api/write/polish`, { draft, focus });
}
export async function translateText(text: string, direction = "en2zh") {
  return jpost<{ ok: boolean; text: string; error?: string }>(`/api/write/translate`, { text, direction });
}

export type IdeaEvt = {
  type: string;
  agent?: string;
  text?: string;
  goal?: string;
  message?: string;
};

export async function streamIdeation(
  body: { topic: string; seed_idea: string; n_ideas: number; rounds: number },
  onEvt: (e: IdeaEvt) => void,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch("/api/ideation/debate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok || !r.body) throw new Error(`ideation ${r.status}`);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      if (chunk.startsWith("data: ")) {
        try {
          onEvt(JSON.parse(chunk.slice(6)));
        } catch {
          /* skip */
        }
      }
    }
  }
}

export async function streamChat(
  message: string,
  mention: string[] | null,
  onEvt: (e: Evt) => void,
  signal?: AbortSignal,
  history: { role: string; content: string }[] = [],
): Promise<void> {
  const r = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, mention: mention || [], history }),
    signal,
  });
  if (!r.ok || !r.body) throw new Error(`chat ${r.status}`);

  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      if (chunk.startsWith("data: ")) {
        try {
          onEvt(JSON.parse(chunk.slice(6)));
        } catch {
          /* skip */
        }
      }
    }
  }
}
