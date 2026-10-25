"use client";

import React, { useMemo } from "react";
import katex from "katex";
import DOMPurify from "isomorphic-dompurify";

interface MathRendererProps {
  content: string;
  className?: string;
}

const MAX_TOTAL_LENGTH = 10000;
const MAX_KATEX_EXPR_LENGTH = 1000;

export const MathRenderer: React.FC<MathRendererProps> = ({ content, className = "" }) => {
  const sanitizedContent = useMemo(() => {
    if (!content) return "";

    // Cap total content length to prevent ReDoS / CPU exhaustion attacks
    const safeContent = content.length > MAX_TOTAL_LENGTH 
      ? content.slice(0, MAX_TOTAL_LENGTH) + " ...[truncated]" 
      : content;

    // Replace display math $$...$$
    let formatted = safeContent.replace(/\$\$([\s\S]+?)\$\$/g, (_, math) => {
      const trimmed = math.trim();
      if (trimmed.length > MAX_KATEX_EXPR_LENGTH) {
        return `[Formula exceeded length limit of ${MAX_KATEX_EXPR_LENGTH} characters]`;
      }
      try {
        return katex.renderToString(trimmed, { displayMode: true, throwOnError: false });
      } catch {
        return DOMPurify.sanitize(trimmed);
      }
    });

    // Replace inline math $...$
    formatted = formatted.replace(/\$([^\$\n]+?)\$/g, (_, math) => {
      const trimmed = math.trim();
      if (trimmed.length > MAX_KATEX_EXPR_LENGTH) {
        return `[Formula exceeded length limit]`;
      }
      try {
        return katex.renderToString(trimmed, { displayMode: false, throwOnError: false });
      } catch {
        return DOMPurify.sanitize(trimmed);
      }
    });

    // Configure DOMPurify to sanitize HTML and force target="_blank" rel="noopener noreferrer" on links
    const clean = DOMPurify.sanitize(formatted, {
      ALLOWED_TAGS: [
        "span", "div", "p", "a", "strong", "em", "code", "pre", "br",
        "svg", "path", "line", "rect", "circle", "g", "annotation", "math", "semantics", "mrow"
      ],
      ALLOWED_ATTR: [
        "class", "style", "aria-hidden", "aria-label", "role", "href", "target", "rel",
        "viewBox", "xmlns", "d", "fill", "stroke", "width", "height"
      ],
      ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
    });

    // Post-process to ensure all links are secure
    return clean.replace(/<a\s+(?:[^>]*?\s+)?href="([^"]*)"([^>]*)>/gi, (match, href, rest) => {
      // nosemgrep: javascript.browser.security.wildcard-postmessage-has-targetorigin.wildcard-postmessage-has-targetorigin
      return `<a href="${href}" target="_blank" rel="noopener noreferrer"${rest}>`;
    });
  }, [content]);

  return (
    <div
      className={`math-rendered-text ${className}`}
      // nosemgrep: typescript.react.security.audit.react-dangerouslysetinnerhtml.react-dangerouslysetinnerhtml
      dangerouslySetInnerHTML={{ __html: sanitizedContent }}
    />
  );
};
