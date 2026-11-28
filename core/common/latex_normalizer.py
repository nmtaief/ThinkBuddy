"""LaTeX and Math Normalizer for ThinkBuddy Question Bank.

Normalizes:
1. Triple-dollar delimiters ($$$...$$$) to standard $...$ (inline) or $$...$$ (block).
2. Unescaped set braces inside math (e.g. P = {a, b, c} -> P = \\{a, b, c\\}).
3. OCR-corrupted chemistry reaction arrows (\\geq, \\leq, >= -> \rightarrow).
4. Decimal commas in constants (e.g. \\pi = 3, 14 -> \\pi = 3.14, 3, 1416 -> 3.1416, ৩, ১৪ -> ৩.১৪).
"""

import re
from typing import Any

SET_BRACE_PATTERN = re.compile(r"(?<![\\a-zA-Z_\^}])\{([^{}]+?)\}(?![}\^])")


def normalize_latex(text_val: str) -> str:
    if not text_val or not isinstance(text_val, str):
        return text_val or ""

    text = text_val

    # 1. OCR-corrupted chemistry arrows:
    # Look for chemical formulas (e.g. Ca, O_2, CO_2, H_2O, CH_3COOH, HCl, NaOH, etc.)
    # or reaction patterns with \geq, \leq, >=
    def fix_chem_reaction(m):
        chunk = m.group(0)
        # Replace \geq, \leq, >= with \rightarrow when between chemical compounds
        return re.sub(r"(\s*)(?:\\geq|\\leq|>=)(\s*)", r"\1\\rightarrow\2", chunk)

    text = re.sub(
        r"(\${1,3}[^\$]*(?:Ca|CH_\{?3\}?COOH|H_\{?2\}?O|CO_\{?2\}?|O_\{?2\}?|HCl|NaOH|Fe|NaCl|SO_\{?4\}?|\bY\b|\bZ\b)[^\$]*\${1,3})",
        fix_chem_reaction,
        text,
    )

    # 2. Decimal commas in constants (adjacent to \pi or pi or units or 3-4 digits):
    text = re.sub(r"(\\pi|pi|পাই)\s*=\s*([0-9০-৯]+)\s*,\s*([0-9০-৯]+)", r"\1 = \2.\3", text)
    text = re.sub(
        r"\((?:\\pi|pi|পাই)\s*=\s*([0-9০-৯]+)\s*,\s*([0-9০-৯]+)\)", r"(\\pi = \1.\2)", text
    )
    # Pi with 4 decimals e.g. 3, 1416 -> 3.1416, ৩, ১৪১৬ -> ৩.১৪১৬
    text = re.sub(r"\b([3৩])\s*,\s*([1১][4৪](?:[1১][6৬])?)\b", r"\1.\2", text)

    # 3. Triple-dollar delimiter replacement
    def replace_triple_dollar(m):
        inner = m.group(1).strip()
        if "\n" in inner:
            return f"$$ {inner} $$"
        return f"$ {inner} $"

    text = re.sub(r"\${3,}(.*?)\${3,}", replace_triple_dollar, text, flags=re.DOTALL)

    # 4. Unescaped set braces inside math delimiters ($...$ or $$...$$)
    def escape_set_braces_in_math(m):
        delim = m.group(1)  # $ or $$
        inner = m.group(2)
        inner_fixed = SET_BRACE_PATTERN.sub(r"\\{\1\\}", inner)
        return f"{delim}{inner_fixed}{delim}"

    text = re.sub(r"(\${1,2})([^\$]+?)\1", escape_set_braces_in_math, text)

    return text


def normalize_options_json(options_data: Any) -> Any:
    """Recursively normalizes LaTeX in options (list of strings or json string)."""
    if isinstance(options_data, list):
        return [normalize_latex(str(opt)) if isinstance(opt, str) else opt for opt in options_data]
    return options_data
