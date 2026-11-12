"""Tests for resource resolution module."""

from __future__ import annotations

import pytest

from planecli.exceptions import ResourceNotFoundError
from planecli.utils.resolve import ISSUE_ID_PATTERN, _is_uuid, resolve_user_async


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


class TestResolveUserAsyncNullEmail:
    """Plane SSO users can have email=None, which used to crash name lookups."""

    MEMBERS = [
        {"id": "u1", "display_name": "Patrick", "email": "patrick@example.com"},
        {"id": "u2", "display_name": "黄晨旭", "email": None},
        {"id": "u3", "display_name": "Terry", "email": None},
    ]

    @pytest.fixture(autouse=True)
    def _mock_members(self, monkeypatch):
        async def fake_list_members(workspace):
            return self.MEMBERS

        # resolve_user_async imports this lazily from planecli.cache.
        monkeypatch.setattr("planecli.cache.cached_list_members", fake_list_members)

    async def test_fuzzy_name_lookup_with_null_email(self):
        result = await resolve_user_async("黄晨旭", None, "company")
        assert result["id"] == "u2"

    async def test_exact_email_match_still_works(self):
        result = await resolve_user_async("PATRICK@example.com", None, "company")
        assert result["id"] == "u1"

    async def test_empty_query_does_not_match_null_email(self):
        with pytest.raises(ResourceNotFoundError):
            await resolve_user_async("", None, "company")
