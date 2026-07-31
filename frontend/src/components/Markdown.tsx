import type { ReactNode } from "react";

/**轻量 markdown 渲染 — 支持 标题/粗体/斜体/行内代码/代码块/链接/列表/引用/分隔线。
 * 不引入外部依赖，覆盖研究助手输出的常见格式。*/

function inline(text: string, key: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // 顺序：code > link > bold > italic
  const regex = /(`[^`]+`)|(\[[^\]]+\]\([^)]+\))|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(_[^_]+_)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = regex.exec(text))) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("`")) {
      nodes.push(<code key={`${key}-${i}`} className="md-code-inline">{tok.slice(1, -1)}</code>);
    } else if (tok.startsWith("[")) {
      const mm = /\[([^\]]+)\]\(([^)]+)\)/.exec(tok);
      if (mm) nodes.push(<a key={`${key}-${i}`} href={mm[2]} target="_blank" rel="noreferrer" className="md-link">{mm[1]}</a>);
    } else if (tok.startsWith("**")) {
      nodes.push(<strong key={`${key}-${i}`}>{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("*")) {
      nodes.push(<em key={`${key}-${i}`}>{tok.slice(1, -1)}</em>);
    } else if (tok.startsWith("_")) {
      nodes.push(<em key={`${key}-${i}`}>{tok.slice(1, -1)}</em>);
    }
    last = m.index + tok.length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function Markdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;
  while (i < lines.length) {
    const line = lines[i];
    // 代码块
    if (line.trim().startsWith("```")) {
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        code.push(lines[i]);
        i++;
      }
      i++;
      blocks.push(<pre key={key++} className="md-code-block"><code>{code.join("\n")}</code></pre>);
      continue;
    }
    // 标题
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      const lvl = h[1].length;
      const content = inline(h[2], `h${key}`);
      blocks.push(
        lvl === 1 ? <h1 key={key++} className="md-h1">{content}</h1> :
        lvl === 2 ? <h2 key={key++} className="md-h2">{content}</h2> :
        lvl === 3 ? <h3 key={key++} className="md-h3">{content}</h3> :
        <h4 key={key++} className="md-h4">{content}</h4>,
      );
      i++;
      continue;
    }
    // 分隔线
    if (/^(-{3,}|\*{3,})$/.test(line.trim())) {
      blocks.push(<hr key={key++} className="md-hr" />);
      i++;
      continue;
    }
    // 引用
    if (line.startsWith(">")) {
      const quote: string[] = [];
      while (i < lines.length && lines[i].startsWith(">")) {
        quote.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      blocks.push(<blockquote key={key++} className="md-quote">{inline(quote.join(" "), `q${key}`)}</blockquote>);
      continue;
    }
    // 无序列表
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      blocks.push(<ul key={key++} className="md-ul">{items.map((it, j) => <li key={j}>{inline(it, `li${key}-${j}`)}</li>)}</ul>);
      continue;
    }
    // 有序列表
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      blocks.push(<ol key={key++} className="md-ol">{items.map((it, j) => <li key={j}>{inline(it, `ol${key}-${j}`)}</li>)}</ol>);
      continue;
    }
    // 空行
    if (line.trim() === "") {
      i++;
      continue;
    }
    // 段落（合并连续非空行）
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() !== "" && !/^(#{1,4}\s|```|>|\s*[-*]\s|\s*\d+\.\s)/.test(lines[i])) {
      para.push(lines[i]);
      i++;
    }
    blocks.push(<p key={key++} className="md-p">{inline(para.join(" "), `p${key}`)}</p>);
  }
  return <div className="md">{blocks}</div>;
}

/**把过长的 hash/uuid 截短显示，保留可读性。*/
export function shortenIds(text: string): string {
  // asset_id=<32位hex> / result_asset_id / "asset_id":"xxxx"
  return text
    .replace(/(asset_id|result_asset_id|source)["']?\s*[:=]\s*["']?([0-9a-f]{8})[0-9a-f]+["']?/gi, '$1=$2…')
    .replace(/\b([0-9a-f]{32})\b/g, (m) => m.slice(0, 8) + "…");
}
