"""Fuzzy matching helpers shared by every search provider."""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Sequence


def normalize(text: str) -> str:
    """Lowercase, trim and collapse whitespace."""
    return " ".join(str(text or "").lower().split())


def tokenize(text: str) -> list[str]:
    """Split text into words, treating punctuation and separators as breaks."""
    return re.findall(r"[^\W_]+", str(text or "").lower(), re.UNICODE)


def is_subsequence(needle: str, haystack: str) -> bool:
    """Return True when *needle* appears in *haystack* in order (not adjacent)."""
    if not needle:
        return True
    iterator = iter(haystack)
    return all(char in iterator for char in needle)


def levenshtein(a: str, b: str) -> int:
    """Optimal string alignment distance (Levenshtein + transpositions)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous_previous: list[int] = []
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            cost = 0 if char_a == char_b else 1
            current.append(
                min(
                    previous[j] + 1,  # deletion
                    current[j - 1] + 1,  # insertion
                    previous[j - 1] + cost,  # substitution
                )
            )
            if (
                i > 1
                and j > 1
                and char_a == b[j - 2]
                and a[i - 2] == char_b
            ):
                current[j] = min(current[j], previous_previous[j - 2] + 1)
        previous_previous, previous = previous, current
    return previous[-1]


def similarity(a: str, b: str) -> float:
    """Return a 0..1 similarity ratio between two strings."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    distance = levenshtein(a, b)
    return max(0.0, 1.0 - distance / max(len(a), len(b)))


def fuzzy_score(
    query: str, target: str, typo_tolerance: bool = True
) -> float:
    """Score how well *target* matches *query* (0.0 = no match, 1.0 = exact)."""
    q = normalize(query)
    t = normalize(target)
    if not q or not t:
        return 0.0
    if q == t:
        return 1.0
    if t.startswith(q):
        return 0.94 + 0.06 * (len(q) / len(t))

    tokens = tokenize(t)
    if any(token.startswith(q) for token in tokens):
        return 0.9

    q_tokens = tokenize(q)
    if len(q_tokens) > 1:
        if all(any(token.startswith(part) for token in tokens) for part in q_tokens):
            return 0.88
        compact = " ".join(q_tokens)
        if compact in t:
            return 0.86

    index = t.find(q)
    if index >= 0:
        return max(0.72, 0.86 - 0.12 * (index / len(t)))

    if is_subsequence(q, t):
        density = len(q) / max(len(t), 1)
        return 0.52 + 0.18 * density

    if typo_tolerance and len(q) >= 3:
        best = 0.0
        for token in tokens:
            best = max(best, similarity(q, token))
            if token[0] == q[0] and len(token) > len(q):
                best = max(best, similarity(q, token[: len(q) + 1]))
        if best >= 0.7:
            return 0.35 + 0.32 * best
        if len(q) >= 4:
            best = max(best, similarity(q, t[: len(q) + 1]))
            if best >= 0.8:
                return 0.3 + 0.3 * best
    return 0.0


def rank(
    query: str,
    items: Iterable[Any],
    key: Callable[[Any], str],
    limit: int | None = None,
    typo_tolerance: bool = True,
    minimum: float = 0.01,
) -> list[tuple[float, Any]]:
    """Score and rank *items* by fuzzy relevance to *query*."""
    scored: list[tuple[float, Any]] = []
    for item in items:
        score = fuzzy_score(query, key(item), typo_tolerance=typo_tolerance)
        if score >= minimum:
            scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if limit is not None:
        return scored[:limit]
    return scored


def best_match(
    query: str, candidates: Sequence[str], typo_tolerance: bool = True
) -> tuple[str, float] | None:
    """Return the best matching candidate string and its score."""
    best: tuple[str, float] | None = None
    for candidate in candidates:
        score = fuzzy_score(query, candidate, typo_tolerance=typo_tolerance)
        if best is None or score > best[1]:
            best = (candidate, score)
    return best


__all__ = [
    "normalize",
    "is_subsequence",
    "levenshtein",
    "similarity",
    "tokenize",
    "fuzzy_score",
    "rank",
    "best_match",
]
