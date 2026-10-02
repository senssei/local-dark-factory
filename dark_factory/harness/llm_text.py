"""Helpers for handling untrusted LLM text: JSON extraction, prompt fences and display sanitising."""

from __future__ import annotations

import json
import re
from typing import Any

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-_]")
_CONTROL_RE = re.compile("[\x00-\x08\x0b-\x0d\x0e-\x1f\x7f-\x9f\u200e\u200f\u2028\u2029\u202a-\u202e\u2066-\u2069]")


def strip_think(raw: str) -> str:
    """Remove reasoning-model <think> blocks."""
    return _THINK_RE.sub("", raw)


def extract_json_object(raw: str, keys: tuple[str, ...] = ()) -> Any:
    """Return the JSON object that answers the prompt from model output.

    Reasoning blocks and code fences are ignored. When `keys` is given, the last decodable object carrying
    one of them wins (a stray `{}` quoted in prose must not shadow the real answer); otherwise the last
    object is returned. Raises ValueError when no object can be decoded.
    """
    text = strip_think(raw)
    decoder = json.JSONDecoder()
    found: list[dict] = []
    pos = 0
    while (start := text.find("{", pos)) != -1:
        try:
            value, end = decoder.raw_decode(text[start:])
        except ValueError:
            pos = start + 1
            continue
        if isinstance(value, dict):
            found.append(value)
        pos = start + end
    if not found:
        raise ValueError("no JSON object found in model output")
    matching = [d for d in found if any(k in d for k in keys)]
    return (matching or found)[-1]


_CODE_FENCE_RE = re.compile(
    r"^(`{3,})[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n(.*?)\n[ \t]*\1`*[ \t]*$", re.DOTALL | re.MULTILINE
)


def extract_code_block(raw: str, lang: str = "") -> str:
    """Return the first fenced block of `lang` (any language if empty) from model output, else the stripped text.

    Fences are matched line-anchored, so backticks inside the code do not end the block.
    """
    text = strip_think(raw).strip()
    for match in _CODE_FENCE_RE.finditer(text):
        if not lang or match.group(2).lower() in ("", lang.lower()):
            return match.group(3).strip()
    return text


def fence(text: str, lang: str = "") -> str:
    """Wrap text in a code fence that no backtick run inside the text can close."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{lang}\n{text}\n{ticks}"


def clean_text(value: str) -> str:
    """Strip ANSI escapes, control characters (CR, C1) and bidi/line separators; newline and tab are kept."""
    return _CONTROL_RE.sub("", _ANSI_RE.sub("", value))


def md_cell(value: str) -> str:
    """Make text safe for a single markdown table cell."""
    return clean_text(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def str_list(value: Any) -> list[str]:
    """Coerce a model-supplied field into a list of strings (a bare string becomes one item)."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(x) for x in value]
    return [str(value)]
