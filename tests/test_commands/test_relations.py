"""Tests for work item relation commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from plane.errors import HttpError

from planecli.commands.relations import (
    _flatten,
    _normalize_type,
    add,
    fetch_issue_relations,
    remove,
)
from planecli.exceptions import APIError, ValidationError

EMPTY = {
    t: []
    for t in (
        "blocking",
        "blocked_by",
        "duplicate",
        "relates_to",
        "start_after",
        "start_before",
        "finish_after",
        "finish_before",
    )
}


def _raw(**types) -> dict:
    return {**EMPTY, **types}


def test_normalize_type_accepts_spellings():
    assert _normalize_type("blocked-by") == "blocked_by"
    assert _normalize_type("Relates To") == "relates_to"
    with pytest.raises(ValidationError, match="Unknown relation type"):
        _normalize_type("parent")


def test_flatten_accepts_objects_and_bare_uuids():
    raw = _raw(
        relates_to=[{"project_id": "p1", "issue_id": "i2"}],
        blocking=["i3"],  # the SDK model's shape
    )
    assert _flatten(raw) == [
        {"relation_type": "blocking", "issue_id": "i3", "project_id": None},
        {"relation_type": "relates_to", "issue_id": "i2", "project_id": "p1"},
    ]


@patch("planecli.commands.relations.create_client")
@patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
@patch("planecli.commands.relations.run_sdk", new_callable=AsyncMock)
async def test_fetch_relations_adds_identifier_and_tolerates_failures(
    mock_run, mock_projects, _create
):
    mock_projects.return_value = [{"id": "p1", "identifier": "ABC"}]

    async def fake_run(fn, path, *args):
        if path.endswith("/relations"):
            return _raw(
                relates_to=[{"project_id": "p1", "issue_id": "i2"}],
                blocked_by=[{"project_id": "p1", "issue_id": "gone"}],
            )
        if path.endswith("/gone"):
            raise HttpError("HTTP 404", status_code=404)
        return {"project": "p1", "sequence_id": 4, "name": "Other"}

    mock_run.side_effect = fake_run
    rows = await fetch_issue_relations(MagicMock(), "ws", "p1", "i1")

    by_id = {r["issue_id"]: r for r in rows}
    assert by_id["i2"]["identifier"] == "ABC-4"
    assert by_id["i2"]["name"] == "Other"
    assert by_id["gone"]["identifier"] is None  # degraded, not fatal


@pytest.fixture
def resolved():
    """Resolve ABC-1 to i1 and any target to i2; yields the target resolver mock."""
    with (
        patch("planecli.commands.relations.get_workspace", return_value="ws"),
        patch("planecli.commands.relations.get_client"),
        patch(
            "planecli.commands.relations.resolve_work_item_and_project_async",
            new_callable=AsyncMock,
            return_value=({"id": "i1"}, "p1"),
        ),
        patch(
            "planecli.commands.relations.resolve_work_item_across_projects_async",
            new_callable=AsyncMock,
            return_value=({"id": "i2"}, "p1"),
        ) as target,
    ):
        yield target


async def test_add_posts_type_and_targets_then_verifies(resolved):
    with (
        patch("planecli.commands.relations.run_sdk", new_callable=AsyncMock) as mock_run,
        patch(
            "planecli.commands.relations.fetch_issue_relations", new_callable=AsyncMock
        ) as mock_fetch,
        patch("planecli.commands.relations.output") as mock_out,
    ):
        mock_fetch.return_value = [
            {"relation_type": "blocking", "issue_id": "i2", "identifier": "ABC-2"}
        ]
        await add("ABC-1", "blocking", "ABC-2")

    assert mock_run.call_args.args[1:] == (
        "ws/projects/p1/work-items/i1/relations",
        {"relation_type": "blocking", "issues": ["i2"]},
    )
    assert mock_out.call_args.args[0][0]["identifier"] == "ABC-2"


async def test_add_raises_when_relation_did_not_land(resolved):
    with (
        patch("planecli.commands.relations.run_sdk", new_callable=AsyncMock),
        patch(
            "planecli.commands.relations.fetch_issue_relations",
            new_callable=AsyncMock,
            return_value=[],  # 201, but nothing was created
        ),
        pytest.raises(APIError, match="did not create"),
    ):
        await add("ABC-1", "relates_to", "ABC-2")


async def test_add_rejects_self_relation(resolved):
    resolved.return_value = ({"id": "i1"}, "p1")
    with pytest.raises(ValidationError, match="itself"):
        await add("ABC-1", "duplicate", "ABC-1")


async def test_add_requires_targets():
    with pytest.raises(ValidationError, match="at least one target"):
        await add("ABC-1", "blocking")


async def test_remove_posts_related_issue_and_verifies(resolved):
    related = _raw(relates_to=[{"project_id": "p1", "issue_id": "i2"}])
    with (
        patch("planecli.commands.relations.run_sdk", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.side_effect = [related, None, _raw()]
        await remove("ABC-1", "ABC-2")

    assert mock_run.call_args_list[1].args[1:] == (
        "ws/projects/p1/work-items/i1/relations/remove",
        {"related_issue": "i2"},
    )


async def test_remove_explains_missing_endpoint(resolved):
    related = _raw(relates_to=[{"project_id": "p1", "issue_id": "i2"}])
    with (
        patch("planecli.commands.relations.run_sdk", new_callable=AsyncMock) as mock_run,
        pytest.raises(APIError, match="cannot remove relations"),
    ):
        mock_run.side_effect = [related, HttpError("HTTP 404", status_code=404)]
        await remove("ABC-1", "ABC-2")


async def test_remove_raises_when_relation_is_still_there(resolved):
    related = _raw(relates_to=[{"project_id": "p1", "issue_id": "i2"}])
    with (
        patch("planecli.commands.relations.run_sdk", new_callable=AsyncMock) as mock_run,
        pytest.raises(APIError, match="did not remove"),
    ):
        mock_run.side_effect = [related, None, related]
        await remove("ABC-1", "ABC-2")


async def test_remove_rejects_unrelated_target(resolved):
    with (
        patch("planecli.commands.relations.run_sdk", new_callable=AsyncMock) as mock_run,
        pytest.raises(ValidationError, match="no relation to"),
    ):
        mock_run.side_effect = [_raw()]
        await remove("ABC-1", "ABC-2")
