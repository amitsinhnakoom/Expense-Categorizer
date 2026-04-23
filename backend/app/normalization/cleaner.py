from __future__ import annotations

import re


_STORE_NUMBER_RE = re.compile(r"\b#?\d{2,}\b")
_NON_WORD_RE = re.compile(r"[^a-z0-9\s]")
_MULTI_SPACE_RE = re.compile(r"\s+")


def normalize_description(text: str) -> str:
    """Normalize descriptions to improve deterministic keyword matching."""
    cleaned = text.lower().strip()
    cleaned = _STORE_NUMBER_RE.sub(" ", cleaned)
    cleaned = _NON_WORD_RE.sub(" ", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned).strip()
    return cleaned
