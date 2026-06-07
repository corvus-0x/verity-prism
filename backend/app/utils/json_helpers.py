"""
Shared JSON utilities for parsing Claude responses.
Claude sometimes wraps JSON in markdown code fences — these helpers
strip that formatting before parsing.
"""


def strip_json_fences(text: str) -> str:
    """
    Remove markdown code fences Claude sometimes wraps JSON in.
    '```json\\n{...}\\n```'  →  '{...}'
    '```\\n{...}\\n```'      →  '{...}'
    '{...}'                  →  '{...}'  (no-op)
    """
    text = text.strip()
    if not text.startswith("```"):
        return text
    # Remove the opening fence line (```json or ```)
    newline = text.find("\n")
    if newline != -1:
        text = text[newline:].strip()
    # Remove the closing fence
    if text.endswith("```"):
        text = text[: text.rfind("```")].strip()
    return text
