"""Tests for work item comment commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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


@patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
@patch("planecli.cache.cached_list_comments", new_callable=AsyncMock)
async def test_fetch_issue_comments_degrades_when_members_fail(
    mock_comments, mock_members
):
    """A members-list failure is a secondary-enrichment concern: it must not
    take down comments that already loaded successfully (names fall back to
    the raw actor UUID, same as the no-map case)."""
    from planecli.commands.comments import fetch_issue_comments

    mock_members.side_effect = PlaneError("members unavailable")
    mock_comments.return_value = [
        {"id": "c1", "actor": "u1", "comment_html": "<p>hi</p>",
         "created_at": "2026-02-10T10:00:00Z"},
    ]

    result = await fetch_issue_comments("ws", "p1", "item-1")

    assert len(result) == 1
    assert result[0]["actor_name"] == "u1"  # fell back to raw UUID


@patch("planecli.commands.comments.output")
@patch("planecli.commands.comments.fetch_issue_comments", new_callable=AsyncMock)
@patch(
    "planecli.commands.comments.resolve_work_item_across_projects_async",
    new_callable=AsyncMock,
)
@patch("planecli.commands.comments.get_workspace", return_value="ws")
@patch("planecli.commands.comments.get_client")
async def test_comment_ls_tail_slices_most_recent(
    mock_client, mock_ws, mock_resolve, mock_fetch, mock_output
):
    from planecli.commands.comments import list_

    mock_resolve.return_value = ({"id": "item-1"}, "p1")
    mock_fetch.return_value = [
        {"id": "c1", "created_at": "t1"},
        {"id": "c2", "created_at": "t2"},
        {"id": "c3", "created_at": "t3"},
    ]

    await list_("ABC-1", limit=2)

    mock_fetch.assert_awaited_once_with("ws", "p1", "item-1")
    data = mock_output.call_args[0][0]
    assert [c["id"] for c in data] == ["c2", "c3"]  # most recent 2, still chronological


@pytest.mark.parametrize("limit", [0, -2])
@patch("planecli.commands.comments.output")
@patch("planecli.commands.comments.fetch_issue_comments", new_callable=AsyncMock)
@patch(
    "planecli.commands.comments.resolve_work_item_across_projects_async",
    new_callable=AsyncMock,
)
@patch("planecli.commands.comments.get_workspace", return_value="ws")
@patch("planecli.commands.comments.get_client")
async def test_comment_ls_non_positive_limit_returns_none(
    mock_client, mock_ws, mock_resolve, mock_fetch, mock_output, limit
):
    """--limit 0 or negative means "no results", matching `wi ls`'s
    `data[:limit]` semantics (where limit=0 also yields an empty list) —
    not "all comments" (0 is falsy) and not a nonsensical reversed slice."""
    from planecli.commands.comments import list_

    mock_resolve.return_value = ({"id": "item-1"}, "p1")
    mock_fetch.return_value = [
        {"id": "c1", "created_at": "t1"},
        {"id": "c2", "created_at": "t2"},
        {"id": "c3", "created_at": "t3"},
    ]

    await list_("ABC-1", limit=limit)

    data = mock_output.call_args[0][0]
    assert data == []


@patch("planecli.commands.comments.output")
@patch("planecli.commands.comments.fetch_issue_comments", new_callable=AsyncMock)
@patch(
    "planecli.commands.comments.resolve_work_item_across_projects_async",
    new_callable=AsyncMock,
)
@patch("planecli.commands.comments.get_workspace", return_value="ws")
@patch("planecli.commands.comments.get_client")
async def test_comment_ls_hard_fails_on_plane_error(
    mock_client, mock_ws, mock_resolve, mock_fetch, mock_output
):
    from planecli.commands.comments import list_
    from planecli.exceptions import PlaneCLIError

    mock_resolve.return_value = ({"id": "item-1"}, "p1")
    mock_fetch.side_effect = PlaneError("boom")

    with pytest.raises(PlaneCLIError):
        await list_("ABC-1", limit=50)
    mock_output.assert_not_called()


@patch("planecli.cache.invalidate_resource", new_callable=AsyncMock)
@patch("planecli.commands.comments.run_sdk", new_callable=AsyncMock)
@patch(
    "planecli.commands.comments.resolve_work_item_across_projects_async",
    new_callable=AsyncMock,
)
@patch("planecli.commands.comments.get_workspace", return_value="ws")
@patch("planecli.commands.comments.get_client")
async def test_comment_create_invalidates_cache(
    mock_client, mock_ws, mock_resolve, mock_run_sdk, mock_invalidate
):
    from planecli.commands.comments import create

    mock_resolve.return_value = ({"id": "item-1"}, "p1")
    mock_run_sdk.return_value = MagicMock(
        model_dump=lambda: {"id": "c1", "comment_html": "<p>x</p>", "actor": "u1"}
    )

    await create("ABC-1", body="hello")

    mock_invalidate.assert_awaited_once_with("comments", "ws", "p1", "item-1")


@patch("planecli.cache.invalidate_resource", new_callable=AsyncMock)
@patch("planecli.commands.comments.run_sdk", new_callable=AsyncMock)
@patch(
    "planecli.commands.comments.resolve_work_item_across_projects_async",
    new_callable=AsyncMock,
)
@patch("planecli.commands.comments.get_workspace", return_value="ws")
@patch("planecli.commands.comments.get_client")
async def test_comment_update_invalidates_cache(
    mock_client, mock_ws, mock_resolve, mock_run_sdk, mock_invalidate
):
    from planecli.commands.comments import update

    mock_resolve.return_value = ({"id": "item-1"}, "p1")
    mock_run_sdk.return_value = MagicMock(
        model_dump=lambda: {"id": "c1", "comment_html": "<p>x</p>", "actor": "u1"}
    )

    await update("comment-1", issue="ABC-1", body="edited")

    mock_invalidate.assert_awaited_once_with("comments", "ws", "p1", "item-1")


@patch("planecli.cache.invalidate_resource", new_callable=AsyncMock)
@patch("planecli.commands.comments.run_sdk", new_callable=AsyncMock)
@patch(
    "planecli.commands.comments.resolve_work_item_across_projects_async",
    new_callable=AsyncMock,
)
@patch("planecli.commands.comments.get_workspace", return_value="ws")
@patch("planecli.commands.comments.get_client")
async def test_comment_delete_invalidates_cache(
    mock_client, mock_ws, mock_resolve, mock_run_sdk, mock_invalidate
):
    from planecli.commands.comments import delete

    mock_resolve.return_value = ({"id": "item-1"}, "p1")

    await delete("comment-1", issue="ABC-1")

    mock_invalidate.assert_awaited_once_with("comments", "ws", "p1", "item-1")
