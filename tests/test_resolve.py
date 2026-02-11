"""Tests for resource resolution module."""

from __future__ import annotations

from planecli.utils.resolve import ISSUE_ID_PATTERN, _is_uuid


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
