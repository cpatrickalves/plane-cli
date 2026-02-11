"""Tests for fuzzy matching module."""

from __future__ import annotations

from planecli.utils.fuzzy import find_best_match, find_matches


class TestFindBestMatch:
    def test_exact_match(self):
        items = ["Frontend App", "Backend API", "Mobile"]
        result = find_best_match("Frontend App", items, key=lambda x: x)
        assert result is not None
        assert result.item == "Frontend App"
        assert result.score == 100.0

    def test_fuzzy_match(self):
        items = ["Frontend App", "Backend API", "Mobile"]
        result = find_best_match("frontend", items, key=lambda x: x)
        assert result is not None
        assert result.item == "Frontend App"

    def test_no_match_below_threshold(self):
        items = ["Frontend App", "Backend API"]
        result = find_best_match("zzzzzzzzz", items, key=lambda x: x)
        assert result is None

    def test_empty_items(self):
        result = find_best_match("query", [], key=lambda x: x)
        assert result is None

    def test_with_dict_items(self):
        items = [
            {"name": "Frontend App", "id": "1"},
            {"name": "Backend API", "id": "2"},
        ]
        result = find_best_match("backend", items, key=lambda x: x["name"])
        assert result is not None
        assert result.item["id"] == "2"

    def test_custom_threshold(self):
        items = ["Frontend App"]
        result = find_best_match("Fron", items, key=lambda x: x, threshold=90)
        assert result is None


class TestFindMatches:
    def test_returns_sorted_matches(self):
        items = ["Frontend App", "Frontend Mobile", "Backend"]
        results = find_matches("frontend", items, key=lambda x: x)
        assert len(results) >= 2
        assert results[0].score >= results[1].score

    def test_respects_limit(self):
        items = ["A", "B", "C", "D", "E"]
        results = find_matches("A", items, key=lambda x: x, limit=2, threshold=0)
        assert len(results) <= 2

    def test_empty_items(self):
        results = find_matches("query", [], key=lambda x: x)
        assert results == []
