"""Tests for resource resolution module."""

from __future__ import annotations

import pytest

from planecli.exceptions import ValidationError
from planecli.utils.resolve import (
    ISSUE_ID_PATTERN,
    _is_uuid,
    match_state_name,
    resolve_state_name,
)


class TestIsUUID:
    def test_valid_uuid(self):
        assert _is_uuid("550e8400-e29b-41d4-a716-446655440000")

    def test_uppercase_uuid(self):
        assert _is_uuid("550E8400-E29B-41D4-A716-446655440000")

    def test_invalid_uuid(self):
        assert not _is_uuid("not-a-uuid")

    def test_empty_string(self):
        assert not _is_uuid("")

    def test_partial_uuid(self):
        assert not _is_uuid("550e8400-e29b")


class TestIssueIdPattern:
    def test_standard_id(self):
        match = ISSUE_ID_PATTERN.match("ABC-123")
        assert match is not None
        assert match.group(1) == "ABC"
        assert match.group(2) == "123"

    def test_lowercase_id(self):
        match = ISSUE_ID_PATTERN.match("abc-456")
        assert match is not None

    def test_single_letter(self):
        match = ISSUE_ID_PATTERN.match("A-1")
        assert match is not None

    def test_invalid_no_number(self):
        match = ISSUE_ID_PATTERN.match("ABC-")
        assert match is None

    def test_invalid_no_prefix(self):
        match = ISSUE_ID_PATTERN.match("-123")
        assert match is None

    def test_invalid_numbers_in_prefix(self):
        match = ISSUE_ID_PATTERN.match("A1B-123")
        assert match is None


# ---------------------------------------------------------------------------
# Strict state matching (ADR-0009)
# ---------------------------------------------------------------------------

MB_STATES = [
    {"id": "s1", "name": "Backlog"},
    {"id": "s2", "name": "Em desenvolvimento"},
    {"id": "s3", "name": "code review"},
    {"id": "s4", "name": "pronto p/ qa"},
    {"id": "s5", "name": "em qa"},
    {"id": "s6", "name": "Done"},
]


class TestMatchStateName:
    def test_exact_match_is_case_insensitive(self):
        assert match_state_name("EM QA", MB_STATES) == (MB_STATES[4], [])

    def test_exact_match_wins_over_containing_names(self):
        states = [{"id": "a", "name": "QA"}, {"id": "b", "name": "pronto p/ qa"}]
        assert match_state_name("qa", states) == (states[0], [])

    def test_unique_whole_word(self):
        assert match_state_name("review", MB_STATES) == (MB_STATES[2], [])

    def test_unique_substring(self):
        assert match_state_name("desenv", MB_STATES) == (MB_STATES[1], [])

    def test_ambiguous_word_returns_candidates(self):
        state, candidates = match_state_name("qa", MB_STATES)
        assert state is None
        assert candidates == [MB_STATES[3], MB_STATES[4]]

    def test_unique_whole_word_beats_other_substrings(self):
        states = [{"id": "a", "name": "Todo"}, {"id": "b", "name": "to do later"}]
        assert match_state_name("do", states) == (states[1], [])

    def test_fuzzy_only_is_not_a_match(self):
        # "dne" fuzzy-matches "Done" but is not contained in any name
        assert match_state_name("dne", MB_STATES) == (None, [])

    def test_blank_query_matches_nothing(self):
        assert match_state_name("  ", MB_STATES) == (None, [])


class TestResolveStateName:
    def test_partial_match_prints_notice(self, capsys):
        assert resolve_state_name("review", MB_STATES) == MB_STATES[2]
        assert 'State matched: "review" -> "code review"' in capsys.readouterr().err

    def test_exact_match_prints_nothing(self, capsys):
        resolve_state_name("Done", MB_STATES)
        assert capsys.readouterr().err == ""

    def test_ambiguous_lists_matches_and_states(self):
        with pytest.raises(ValidationError) as exc:
            resolve_state_name("qa", MB_STATES)
        assert '"pronto p/ qa", "em qa"' in exc.value.message
        assert '"Backlog"' in exc.value.hint
        assert exc.value.exit_code == 5

    def test_no_match_lists_states(self):
        with pytest.raises(ValidationError, match='No state matches "dne"') as exc:
            resolve_state_name("dne", MB_STATES)
        assert '"code review"' in exc.value.hint


@pytest.mark.asyncio
async def test_resolve_state_async_uses_strict_match():
    from unittest.mock import AsyncMock, patch

    from planecli.utils.resolve import resolve_state_async

    with patch("planecli.cache.cached_list_states", new_callable=AsyncMock) as mock_states:
        mock_states.return_value = MB_STATES
        assert (await resolve_state_async("em qa", None, "ws", "p1"))["id"] == "s5"
        with pytest.raises(ValidationError):
            await resolve_state_async("qa", None, "ws", "p1")


@pytest.mark.asyncio
async def test_resolve_state_async_uuid_skips_name_matching():
    from unittest.mock import AsyncMock, MagicMock, patch

    from planecli.utils.resolve import resolve_state_async

    uuid = "550e8400-e29b-41d4-a716-446655440000"
    state = MagicMock()
    state.model_dump.return_value = {"id": uuid, "name": "Done"}
    with patch("planecli.api.async_sdk.run_sdk", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = state
        assert (await resolve_state_async(uuid, MagicMock(), "ws", "p1"))["id"] == uuid
