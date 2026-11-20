"use client";

import React, { useMemo } from "react";
import katex from "katex";
import DOMPurify from "isomorphic-dompurify";

interface MathRendererProps {
  content: string;
  className?: string;
}

const MAX_TOTAL_LENGTH = 15000;
const MAX_KATEX_EXPR_LENGTH = 1500;

function parseMarkdownToHtml(text: string): string {
  if (!text) return "";

  // Split into lines to identify block-level structures directly at the source
  // No regex replacements that can mangle minus signs (e.g. 5k - 2) or KaTeX formulas
  const lines = text.split("\n");
  const output: string[] = [];
  let inUl = false;
  let inOl = false;
  let inTable = false;
  let tableRows: string[][] = [];
  let currentParagraph: string[] = [];

  const flushParagraph = () => {
    if (currentParagraph.length > 0) {
      const pText = currentParagraph.join("<br/>");
      output.push(`<p>${pText}</p>`);
      currentParagraph = [];
    }
  };

  const closeLists = () => {
    if (inUl) {
      output.push("</ul>");
      inUl = false;
    }
    if (inOl) {
      output.push("</ol>");
      inOl = false;
    }
  };

  const closeTable = () => {
    if (inTable && tableRows.length > 0) {
      let tHtml = '<div class="table-responsive my-2 overflow-x-auto"><table class="border-collapse border border-gray-300 w-full text-sm">';
      const headerRow = tableRows[0];
      tHtml += '<thead><tr class="bg-gray-100">';
      for (const col of headerRow) {
        tHtml += `<th class="border border-gray-300 px-3 py-1 font-semibold text-left">${col.trim()}</th>`;
      }
      tHtml += '</tr></thead><tbody>';
      for (let r = 1; r < tableRows.length; r++) {
        const row = tableRows[r];
        if (row.every((c) => /^:?-+:?$/.test(c.trim()))) continue;
        tHtml += '<tr class="even:bg-gray-50">';
        for (const col of row) {
          tHtml += `<td class="border border-gray-300 px-3 py-1">${col.trim()}</td>`;
        }
        tHtml += '</tr>';
      }
      tHtml += '</tbody></table></div>';
      output.push(tHtml);
      inTable = false;
      tableRows = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Empty line separates blocks
    if (!trimmed) {
      flushParagraph();
      closeLists();
      closeTable();
      continue;
    }

    // Table row (| col1 | col2 |)
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      flushParagraph();
      closeLists();
      inTable = true;
      const cells = trimmed.slice(1, -1).split("|");
      tableRows.push(cells);
      continue;
    } else if (inTable) {
      closeTable();
    }

    // Unordered list item (- or *)
    const ulMatch = line.match(/^(\s*)[-*]\s+(.*)$/);
    if (ulMatch) {
      flushParagraph();
      if (inOl) {
        output.push("</ol>");
        inOl = false;
      }
      if (!inUl) {
        output.push("<ul>");
        inUl = true;
      }
      output.push(`<li>${ulMatch[2]}</li>`);
      continue;
    }

    // Ordered list item (e.g. "1. ", "১. ", "1) ", "১) ")
    const olMatch = line.match(/^(\s*)(?:[0-9]+|[০-৯]+)[.)]\s+(.*)$/);
    if (olMatch) {
      flushParagraph();
      if (inUl) {
        output.push("</ul>");
        inUl = false;
      }
      if (!inOl) {
        output.push("<ol>");
        inOl = true;
      }
      output.push(`<li>${olMatch[2]}</li>`);
      continue;
    }

    // Headings (### or ##)
    const hMatch = line.match(/^#{1,4}\s+(.*)$/);
    if (hMatch) {
      flushParagraph();
      closeLists();
      output.push(`<h3>${hMatch[1]}</h3>`);
      continue;
    }

    // Normal line within a paragraph
    closeLists();
    closeTable();
    currentParagraph.push(line);
  }

  flushParagraph();
  closeLists();
  closeTable();

  let html = output.join("");

  // Inline formatting:
  // Bold: **text**
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Italic: *text* (when not preceded or followed by *)
  html = html.replace(/(?<!\*)\*([^*]+?)\*(?!\*)/g, "<em>$1</em>");
  // Inline code: `code`
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  return html;
}

export const MathRenderer: React.FC<MathRendererProps> = ({ content, className = "" }) => {
  const sanitizedContent = useMemo(() => {
    if (!content) return "";

    // Cap total content length to prevent ReDoS / CPU exhaustion attacks
    const safeContent =
      content.length > MAX_TOTAL_LENGTH
        ? content.slice(0, MAX_TOTAL_LENGTH) + " ...[truncated]"
        : content;

    // 1. Extract Display Math $$...$$ into placeholders
    const displayMathMap: Map<string, string> = new Map();
    let placeholderCount = 0;

    let preprocessed = safeContent.replace(/\$\$([\s\S]+?)\$\$/g, (_, math) => {
      const key = `___MATH_DISP_${placeholderCount++}___`;
      const trimmed = math.trim();
      let rendered: string;
      if (trimmed.length > MAX_KATEX_EXPR_LENGTH) {
        rendered = `<div class="katex-error">[Formula exceeded length limit]</div>`;
      } else {
        try {
          rendered = katex.renderToString(trimmed, { displayMode: true, throwOnError: false });
        } catch {
          rendered = DOMPurify.sanitize(trimmed);
        }
      }
      displayMathMap.set(key, `<div class="katex-display-scroll overflow-x-auto my-2">${rendered}</div>`);
      return key;
    });

    // 2. Extract Inline Math $...$ into placeholders
    const inlineMathMap: Map<string, string> = new Map();
    preprocessed = preprocessed.replace(/\$([^\$\n]+?)\$/g, (_, math) => {
      const key = `___MATH_INL_${placeholderCount++}___`;
      const trimmed = math.trim();
      let rendered: string;
      if (trimmed.length > MAX_KATEX_EXPR_LENGTH) {
        rendered = `[Formula exceeded length limit]`;
      } else {
        try {
          rendered = katex.renderToString(trimmed, { displayMode: false, throwOnError: false });
        } catch {
          rendered = DOMPurify.sanitize(trimmed);
        }
      }
      inlineMathMap.set(key, rendered);
      return key;
    });

    // 3. Parse Markdown structures (bold, lists, paragraphs, headings)
    let parsedHtml = parseMarkdownToHtml(preprocessed);

    // 4. Restore math formulas from placeholders
    for (const [key, val] of displayMathMap.entries()) {
      parsedHtml = parsedHtml.replace(key, val);
    }
    for (const [key, val] of inlineMathMap.entries()) {
      parsedHtml = parsedHtml.replace(key, val);
    }

    // 5. Sanitize HTML with DOMPurify in browser environment
    let clean = parsedHtml;
    if (typeof window !== "undefined") {
      clean = DOMPurify.sanitize(parsedHtml, {
        ALLOWED_TAGS: [
          "span", "div", "p", "a", "strong", "em", "code", "pre", "br",
          "ul", "ol", "li", "h2", "h3", "h4",
          "table", "thead", "tbody", "tr", "th", "td",
          "svg", "path", "line", "rect", "circle", "g", "annotation", "math", "semantics", "mrow"
        ],
        ALLOWED_ATTR: [
          "class", "style", "aria-hidden", "aria-label", "role", "href", "target", "rel",
          "viewBox", "xmlns", "d", "fill", "stroke", "width", "height", "colspan", "rowspan"
        ],
        ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
      });
    }

    // Post-process to ensure external links are secure
    return clean.replace(/<a\s+(?:[^>]*?\s+)?href="([^"]*)"([^>]*)>/gi, (match, href, rest) => {
      return `<a href="${href}" target="_blank" rel="noopener noreferrer"${rest}>`;
    });
  }, [content]);

  return (
    <div
      className={`math-rendered-text ${className}`}
      dangerouslySetInnerHTML={{ __html: sanitizedContent }}
    />
  );
};
