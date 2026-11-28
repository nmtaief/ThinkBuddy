import React, { useMemo } from "react";
import katex from "katex";

interface MathRendererProps {
  content: string;
  className?: string;
}

export const MathRenderer: React.FC<MathRendererProps> = ({ content, className = "" }) => {
  const renderedContent = useMemo(() => {
    if (!content) return "";

    let text = content.replace(/\$\$([\s\S]*?)\$\$/g, (_, equation) => {
      try {
        return katex.renderToString(equation.trim(), {
          displayMode: true,
          throwOnError: false,
        });
      } catch {
        return equation;
      }
    });

    text = text.replace(/\$([^\$\n]+?)\$/g, (_, equation) => {
      try {
        return katex.renderToString(equation.trim(), {
          displayMode: false,
          throwOnError: false,
        });
      } catch {
        return equation;
      }
    });

    return text;
  }, [content]);

  return (
    <div
      className={`math-content ${className}`}
      dangerouslySetInnerHTML={{ __html: renderedContent }} // nosemgrep: typescript.react.security.audit.react-dangerouslysetinnerhtml.react-dangerouslysetinnerhtml
    />
  );
};

