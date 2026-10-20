"""Tests for work item link commands."""

from __future__ import annotations

import json as jsonlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from planecli.commands.links import _enrich_link, add, delete, fetch_issue_links


def _link(link_id: str, url: str, title: str = "", **extra) -> dict:
    return {"id": link_id, "url": url, "title": title, "created_at": extra.pop("at", ""), **extra}


def test_enrich_link_drops_favicon_and_fills_title():
    data = _link("l1", "https://x.io", metadata={"title": "X", "favicon": "data:..."})
    result = _enrich_link(data)
    assert result["title"] == "X"
    assert "favicon" not in result["metadata"]


def test_enrich_link_keeps_explicit_title():
    assert _enrich_link(_link("l1", "u", "Mine", metadata={"title": "X"}))["title"] == "Mine"


@patch("planecli.commands.links.run_sdk", new_callable=AsyncMock)
async def test_fetch_issue_links_follows_pages_and_sorts(mock_run):
    mock_run.side_effect = [
        {"results": [_link("l2", "b", at="2")], "next_page_results": True, "next_cursor": "c1"},
        {"results": [_link("l1", "a", at="1")], "next_page_results": False, "next_cursor": "c2"},
    ]
    links = await fetch_issue_links(MagicMock(), "ws", "p1", "i1")
    assert [lk["id"] for lk in links] == ["l1", "l2"]
    assert mock_run.call_args_list[1].args[2] == {"per_page": 100, "cursor": "c1"}


def _patch_resolve():
    return patch(
        "planecli.commands.links.resolve_work_item_and_project_async",
        new_callable=AsyncMock,
        return_value=({"id": "i1"}, "p1"),
    )


@patch("planecli.commands.links.get_workspace", return_value="ws")
@patch("planecli.commands.links.get_client")
@patch("planecli.commands.links.run_sdk", new_callable=AsyncMock)
async def test_add_posts_url_and_title(mock_run, _client, _ws, capsys):
    mock_run.return_value = _link("l9", "https://x.io", "X")
    with _patch_resolve():
        await add("ABC-1", "https://x.io", title="X", json=True)

    assert mock_run.call_args.args[1:] == (
        "ws/projects/p1/work-items/i1/links",
        {"url": "https://x.io", "title": "X"},
    )
    assert jsonlib.loads(capsys.readouterr().out)["id"] == "l9"


@patch("planecli.commands.links.get_workspace", return_value="ws")
@patch("planecli.commands.links.get_client")
@patch("planecli.commands.links.run_sdk", new_callable=AsyncMock)
async def test_add_raises_when_echo_does_not_confirm(mock_run, _client, _ws):
    from planecli.exceptions import APIError

    mock_run.return_value = {"detail": "ok"}  # 2xx without the created link
    with _patch_resolve(), pytest.raises(APIError):
        await add("ABC-1", "https://x.io")


async def test_add_rejects_non_http_url():
    from planecli.exceptions import ValidationError

    with pytest.raises(ValidationError, match="Not an http"):
        await add("ABC-1", "ftp://x.io")


@pytest.mark.parametrize("selector", ["l2", "https://b.io"])
@patch("planecli.commands.links.get_workspace", return_value="ws")
@patch("planecli.commands.links.get_client")
@patch("planecli.commands.links.fetch_issue_links", new_callable=AsyncMock)
@patch("planecli.commands.links.run_sdk", new_callable=AsyncMock)
async def test_delete_by_id_or_url(mock_run, mock_fetch, _client, _ws, selector):
    mock_fetch.return_value = [_link("l1", "https://a.io"), _link("l2", "https://b.io")]
    with _patch_resolve():
        await delete("ABC-1", selector)
    assert mock_run.call_args.args[1] == "ws/projects/p1/work-items/i1/links/l2"


@patch("planecli.commands.links.get_workspace", return_value="ws")
@patch("planecli.commands.links.get_client")
@patch("planecli.commands.links.fetch_issue_links", new_callable=AsyncMock)
@patch("planecli.commands.links.run_sdk", new_callable=AsyncMock)
async def test_delete_unknown_link_lists_links(mock_run, mock_fetch, _client, _ws):
    from planecli.exceptions import ValidationError

    mock_fetch.return_value = [_link("l1", "https://a.io")]
    with _patch_resolve(), pytest.raises(ValidationError) as exc:
        await delete("ABC-1", "https://nope.io")
    assert "https://a.io" in exc.value.hint
    mock_run.assert_not_awaited()
