"""Fuzzy matching with rapidfuzz for resource name resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from rapidfuzz import fuzz

MIN_MATCH_SCORE = 60


@dataclass
class FuzzyMatch:
    item: Any
    score: float
    matched_value: str


def find_best_match(
    query: str,
    items: Sequence[Any],
    key: Callable[[Any], str],
    *,
    threshold: float = MIN_MATCH_SCORE,
) -> FuzzyMatch | None:
    """Find the single best fuzzy match for a query.

    Args:
        query: The search string.
        items: Sequence of objects to search through.
        key: Function to extract the comparable string from each item.
        threshold: Minimum score (0-100) to consider a match.

    Returns:
        The best FuzzyMatch or None if no match exceeds the threshold.
    """
    if not items:
        return None

    best: FuzzyMatch | None = None
    for item in items:
        value = key(item)
        score = fuzz.token_sort_ratio(query.lower(), value.lower())
        if score >= threshold and (best is None or score > best.score):
            best = FuzzyMatch(item=item, score=score, matched_value=value)

    return best


def find_matches(
    query: str,
    items: Sequence[Any],
    key: Callable[[Any], str],
    *,
    limit: int = 5,
    threshold: float = MIN_MATCH_SCORE,
) -> list[FuzzyMatch]:
    """Find the top fuzzy matches for a query, sorted by score descending.

    Args:
        query: The search string.
        items: Sequence of objects to search through.
        key: Function to extract the comparable string from each item.
        limit: Maximum number of matches to return.
        threshold: Minimum score (0-100) to consider a match.

    Returns:
        List of FuzzyMatch objects sorted by score descending.
    """
    if not items:
        return []

    matches: list[FuzzyMatch] = []
    for item in items:
        value = key(item)
        score = fuzz.token_sort_ratio(query.lower(), value.lower())
        if score >= threshold:
            matches.append(FuzzyMatch(item=item, score=score, matched_value=value))

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:limit]
