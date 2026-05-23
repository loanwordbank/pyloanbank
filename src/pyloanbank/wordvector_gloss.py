"""Tokenize English gloss strings for ``WordVectorInput`` / GloVe coverage checks."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from .glove import load_glove_model

ABBREVIATIONS = {
    "interj": "interjection",
}

STOPWORDS = frozenset({
    "a", "an", "the", "to", "of", "and", "or", "but", "in", "on", "at", "for",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "must", "can", "not", "no", "so", "if", "than", "that", "this",
    "these", "those", "it", "its", "into", "over", "after", "before", "between",
    "through", "during", "without", "within", "about", "up", "down", "out", "off",
    "also", "nor", "too", "very", "just", "only", "own", "same", "such", "some",
    "any", "each", "few", "more", "most", "other", "all", "both", "either", "neither",
    "he", "she", "we", "they", "you", "i", "me", "him", "her", "us", "them",
})

_BRACKET_PATTERNS = (
    r"\([^()]*\)",
    r"\[[^\[\]]*\]",
    r"\{[^{}]*\}",
    r"〈[^〉]*〉",
    r"‹[^›]*›",
)


def strip_brackets(text: str) -> str:
    """Remove parenthetical and bracketed asides from a gloss segment."""
    text = (text or "").strip()
    while True:
        prev = text
        for pattern in _BRACKET_PATTERNS:
            text = re.sub(pattern, " ", text)
        if text == prev:
            break
    return " ".join(text.split())


def tokenize(meaning: str) -> list[str]:
    """Split a gloss segment into GloVe lookup tokens."""
    if not meaning:
        return []
    normalized = strip_brackets(meaning).strip().lower()
    tokens = [re.sub(r"^[\W_]+|[\W_]+$", "", t) for t in normalized.split()]
    tokens = [t for t in tokens if t]
    expanded = []
    for t in tokens:
        t = re.sub(r"'s$", "", t)
        if not t:
            continue
        for part in t.split("-"):
            if part and part in ABBREVIATIONS:
                expanded.extend(ABBREVIATIONS[part].split())
            elif part and part not in STOPWORDS:
                expanded.append(part)
    return expanded


def wordvector_input_from_gloss(gloss: str) -> str:
    """First comma- or semicolon-separated sense, with brackets stripped."""
    text = (gloss or "").strip()
    for sep in (",", ";"):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
            break
    return strip_brackets(text)


def wordvector_check_input(row: dict) -> str:
    """Raw gloss segment for one parameter row (Description, else Name)."""
    return wordvector_input_from_gloss(
        row.get("Description") or row.get("Name") or ""
    )


def wordvector_input_column_value(row: dict) -> str:
    """Space-joined tokens for ``WordVectorInput`` (first sense of Name/Description)."""
    return " ".join(tokenize(wordvector_check_input(row)))


def check_wordvector_input_coverage(
    parameters_table: list,
    base_path: Path,
    tokens_for_row: Callable[[dict], list[str]] | None = None,
) -> float:
    """Fill ``WordVectorInput`` and ``WordVector``; return GloVe coverage %."""
    if not parameters_table:
        return 0.0
    tokens_fn = tokens_for_row or (
        lambda row: tokenize(wordvector_check_input(row))
    )
    model = load_glove_model(base_path)
    hits = 0
    for row in parameters_table:
        tokens = tokens_fn(row)
        row["WordVectorInput"] = " ".join(tokens)
        in_model = bool(tokens and all(t in model for t in tokens))
        row["WordVector"] = in_model
        if in_model:
            hits += 1
    total = len(parameters_table)
    return (100.0 * hits / total) if total else 0.0
