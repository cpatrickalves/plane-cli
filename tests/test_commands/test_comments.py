"""Tests for work item comment commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from plane.errors import PlaneError

from planecli.commands.comments import _enrich_comment


def test_enrich_comment_resolves_actor_name_from_members_map():
    members_map = {"user-1": "Alice"}
    result = _enrich_comment(
        {"actor": "user-1", "comment_html": "<p>hello</p>"}, members_map
    )
    assert result["actor_name"] == "Alice"
    assert result["body_text"] == "hello"


def test_enrich_comment_falls_back_to_uuid_without_map():
    result = _enrich_comment({"actor": "user-1", "comment_html": "<p>hi</p>"})
    assert result["actor_name"] == "user-1"


def test_enrich_comment_falls_back_to_uuid_when_member_missing():
    result = _enrich_comment(
        {"actor": "user-x", "comment_html": ""}, {"user-1": "Alice"}
    )
    assert result["actor_name"] == "user-x"
    assert result["body_text"] == ""


@patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
@patch("planecli.cache.cached_list_comments", new_callable=AsyncMock)
async def test_fetch_issue_comments_sorts_and_resolves(mock_comments, mock_members):
    from planecli.commands.comments import fetch_issue_comments

    mock_members.return_value = [
        {"id": "u1", "display_name": "Alice"},
        {"id": "u2", "display_name": "Bob"},
    ]
    # Returned out of order; helper must sort oldest -> newest
    mock_comments.return_value = [
        {"id": "c2", "actor": "u2", "comment_html": "<p>later</p>",
         "created_at": "2026-02-11T10:00:00Z"},
        {"id": "c1", "actor": "u1", "comment_html": "<p>earlier</p>",
         "created_at": "2026-02-10T10:00:00Z"},
    ]

    result = await fetch_issue_comments("ws", "p1", "item-1")

    assert [c["id"] for c in result] == ["c1", "c2"]  # chronological
    assert result[0]["actor_name"] == "Alice"
    assert result[0]["body_text"] == "earlier"
    assert result[1]["actor_name"] == "Bob"


@patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
@patch("planecli.cache.cached_list_comments", new_callable=AsyncMock)
async def test_fetch_issue_comments_returns_all(mock_comments, mock_members):
    from planecli.commands.comments import fetch_issue_comments

    mock_members.return_value = []
    mock_comments.return_value = [
        {"id": f"c{i}", "actor": "u1", "comment_html": "<p>x</p>",
         "created_at": f"2026-02-{i:02d}T00:00:00Z"}
        for i in range(1, 31)
    ]

    result = await fetch_issue_comments("ws", "p1", "item-1")
    assert len(result) == 30  # no truncation


@patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
@patch("planecli.cache.cached_list_comments", new_callable=AsyncMock)
async def test_fetch_issue_comments_raises_on_failure(mock_comments, mock_members):
    from planecli.commands.comments import fetch_issue_comments

    mock_members.return_value = []
    mock_comments.side_effect = PlaneError("boom")

    with pytest.raises(PlaneError):
        await fetch_issue_comments("ws", "p1", "item-1")
