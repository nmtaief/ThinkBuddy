"use client";

import React, { useMemo } from "react";
import katex from "katex";
import DOMPurify from "isomorphic-dompurify";

interface MathRendererProps {
  content: string;
  className?: string;
}

export const MathRenderer: React.FC<MathRendererProps> = ({ content, className = "" }) => {
  const sanitizedContent = useMemo(() => {
    if (!content) return "";

    // Replace display math $$...$$
    let formatted = content.replace(/\$\$([\s\S]+?)\$\$/g, (_, math) => {
      try {
        return katex.renderToString(math.trim(), { displayMode: true, throwOnError: false });
      } catch {
        return math;
      }
    });

    // Replace inline math $...$
    formatted = formatted.replace(/\$([^\$\n]+?)\$/g, (_, math) => {
      try {
        return katex.renderToString(math.trim(), { displayMode: false, throwOnError: false });
      } catch {
        return math;
      }
    });

    return DOMPurify.sanitize(formatted);
  }, [content]);

  return (
    <div
      className={`math-rendered-text ${className}`}
      // nosemgrep: typescript.react.security.audit.react-dangerouslysetinnerhtml.react-dangerouslysetinnerhtml
      dangerouslySetInnerHTML={{ __html: sanitizedContent }}
    />
  );
};
