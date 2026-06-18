import { createElement } from "react";
import type { ReactNode } from "react";

// 의존성 없는 경량 Markdown 렌더러(서버 컴포넌트).
// Claude 진단/대화 결과가 내뱉는 구조를 다룬다: heading(#)·bold(**)·italic(*)·inline code(`)·
// 링크([t](url))·불릿/번호 리스트·blockquote(>)·코드펜스(```)·GFM 표(| a | b |)·수평선(---)·문단.
// 텍스트는 React 노드로 삽입되어 이스케이프되므로 XSS 안전(dangerouslySetInnerHTML 미사용).
// 링크 URL 은 스킴 화이트리스트(http/https/mailto)만 허용 — javascript: 등 차단.

// bold(**) → italic(*) → inline code(`) → 링크([t](url)) 순서로 매칭(긴 토큰 우선). 비탐욕 →
// `**a *b* c**` 같은 중첩 허용. bold/italic/링크텍스트 안은 재귀 파싱(code 안은 리터럴).
const INLINE =
  /(\*\*([\s\S]+?)\*\*|\*([^*\n]+?)\*|`([^`]+?)`|\[([^\]]+?)\]\(([^)\s]+?)\))/;

// 안전한 링크 스킴만 통과(그 외는 링크화하지 않고 리터럴 텍스트로 둔다).
function safeUrl(url: string): string | null {
  const u = url.trim();
  return /^(https?:\/\/|mailto:)/i.test(u) ? u : null;
}

function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  // 재귀가 lastIndex 를 공유하지 않도록 호출마다 새 정규식.
  const re = new RegExp(INLINE.source, "g");
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[2] !== undefined)
      out.push(<strong key={`${key}-b${i}`}>{inline(m[2], `${key}-b${i}`)}</strong>);
    else if (m[3] !== undefined)
      out.push(<em key={`${key}-i${i}`}>{inline(m[3], `${key}-i${i}`)}</em>);
    else if (m[4] !== undefined) out.push(<code key={`${key}-c${i}`}>{m[4]}</code>);
    else if (m[5] !== undefined && m[6] !== undefined) {
      const href = safeUrl(m[6]);
      if (href)
        out.push(
          <a key={`${key}-a${i}`} href={href} target="_blank" rel="noopener noreferrer">
            {inline(m[5], `${key}-a${i}`)}
          </a>
        );
      else out.push(m[0]); // 안전하지 않은 스킴 → 원문 그대로
    }
    last = m.index + m[0].length;
    i++;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const LIST = /^\s*([-*]|\d+\.)\s+/;
const HEADING = /^(#{1,6})\s+(.*)$/;
// 수평선: 같은 문자(-, *, _) 3개 이상만 있는 줄.
const HR = /^\s*([-*_])\1{2,}\s*$/;
// GFM 표 구분선: |, :, -, 공백만으로 구성되고 대시를 1개 이상 포함.
const TABLE_SEP = /^[\s|:-]*-[\s|:-]*$/;

// 표 한 행을 셀 배열로 — 양끝 파이프 제거 후 | 로 분리, 셀 trim.
function cells(row: string): string[] {
  let s = row.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  return s.split("|").map((c) => c.trim());
}

// 현재 줄이 표 시작(헤더행 + 다음 줄이 구분선)인지.
function isTableStart(lines: string[], i: number): boolean {
  return (
    i + 1 < lines.length && lines[i].includes("|") && TABLE_SEP.test(lines[i + 1])
  );
}

export function Markdown({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let k = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === "") {
      i++;
      continue;
    }

    // 코드펜스 ```
    if (line.trim().startsWith("```")) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        buf.push(lines[i]);
        i++;
      }
      i++; // 닫는 펜스 건너뜀
      blocks.push(
        <pre key={k++} className="md-pre">
          <code>{buf.join("\n")}</code>
        </pre>
      );
      continue;
    }

    // 헤딩 ## → 페이지 스케일에 맞춰 한 단계 낮춤(h3~)
    const h = HEADING.exec(line);
    if (h) {
      const level = Math.min(h[1].length + 1, 6);
      blocks.push(
        createElement(
          `h${level}`,
          { key: k++, className: "md-h" },
          inline(h[2], `h${k}`)
        )
      );
      i++;
      continue;
    }

    // blockquote >
    if (line.trimStart().startsWith(">")) {
      const buf: string[] = [];
      while (i < lines.length && lines[i].trimStart().startsWith(">")) {
        buf.push(lines[i].replace(/^\s*>\s?/, ""));
        i++;
      }
      blocks.push(
        <blockquote key={k++} className="md-quote">
          {inline(buf.join(" "), `q${k}`)}
        </blockquote>
      );
      continue;
    }

    // GFM 표 — 헤더행 + 구분선 + 본문행들
    if (isTableStart(lines, i)) {
      const header = cells(lines[i]);
      i += 2; // 헤더 + 구분선 건너뜀
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim() !== "" && lines[i].includes("|")) {
        rows.push(cells(lines[i]));
        i++;
      }
      const kt = k++;
      blocks.push(
        <table key={kt} className="md-table">
          <thead>
            <tr>
              {header.map((c, j) => (
                <th key={j}>{inline(c, `t${kt}-h${j}`)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={ri}>
                {r.map((c, ci) => (
                  <td key={ci}>{inline(c, `t${kt}-${ri}-${ci}`)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );
      continue;
    }

    // 수평선 ---
    if (HR.test(line)) {
      blocks.push(<hr key={k++} className="md-hr" />);
      i++;
      continue;
    }

    // 리스트(불릿/번호)
    if (LIST.test(line)) {
      const ordered = /^\s*\d+\.\s+/.test(line);
      const items: string[] = [];
      while (i < lines.length && LIST.test(lines[i])) {
        items.push(lines[i].replace(LIST, ""));
        i++;
      }
      const children = items.map((it, j) => (
        <li key={j}>{inline(it, `li${k}-${j}`)}</li>
      ));
      blocks.push(
        createElement(ordered ? "ol" : "ul", { key: k++, className: "md-list" }, children)
      );
      continue;
    }

    // 문단 — 빈 줄/다른 블록 시작 전까지 모음
    const buf: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !LIST.test(lines[i]) &&
      !HEADING.test(lines[i]) &&
      !HR.test(lines[i]) &&
      !isTableStart(lines, i) &&
      !lines[i].trimStart().startsWith(">") &&
      !lines[i].trim().startsWith("```")
    ) {
      buf.push(lines[i]);
      i++;
    }
    blocks.push(
      <p key={k++} className="md-p">
        {inline(buf.join(" "), `p${k}`)}
      </p>
    );
  }

  return <div className="md">{blocks}</div>;
}
