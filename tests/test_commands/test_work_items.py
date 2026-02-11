"""Tests for work item commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from planecli.commands.work_items import WI_COLUMNS, WI_COLUMNS_ALL, list_


def _make_member(member_id: str, first_name: str, last_name: str, display_name: str):
    m = MagicMock()
    m.id = member_id
    m.first_name = first_name
    m.last_name = last_name
    m.display_name = display_name
    return m


def _make_work_item(
    item_id: str,
    name: str,
    sequence_id: int,
    state: str = "state-uuid-1",
    assignees: list | None = None,
    created_at: str = "2026-02-10T12:00:00Z",
    updated_at: str = "2026-02-10T12:00:00Z",
):
    item = MagicMock()
    item.model_dump.return_value = {
        "id": item_id,
        "name": name,
        "sequence_id": sequence_id,
        "state": state,
        "assignees": assignees or [],
        "labels": [],
        "priority": "medium",
        "created_at": created_at,
        "updated_at": updated_at,
    }
    return item


def _make_state(state_id: str, name: str):
    s = MagicMock()
    s.id = state_id
    s.name = name
    return s


def _make_label(label_id: str, name: str):
    lb = MagicMock()
    lb.id = label_id
    lb.name = name
    return lb


def _make_project(project_id: str, identifier: str, name: str):
    p = MagicMock()
    p.id = project_id
    p.identifier = identifier
    p.name = name
    p.model_dump.return_value = {
        "id": project_id,
        "identifier": identifier,
        "name": name,
    }
    return p


def _make_paginated_response(results, next_page=False, next_cursor=None):
    resp = MagicMock()
    resp.results = results
    resp.next_page_results = next_page
    resp.next_cursor = next_cursor
    return resp


class TestWiList:
    """Tests for the wi list command."""

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.commands.work_items.resolve_project_async")
    @patch("planecli.commands.work_items.run_sdk")
    @patch("planecli.commands.work_items.paginate_all_async")
    async def test_list_single_project(
        self,
        mock_paginate,
        mock_run_sdk,
        mock_resolve_project,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """wi list -p Frontend should list items from one project only."""
        client = MagicMock()
        mock_get_client.return_value = client

        # create_client returns a fresh client for parallel fetching
        proj_client = MagicMock()
        mock_create_client.return_value = proj_client

        # Members (workspace-scoped) via run_sdk
        mock_run_sdk.return_value = [
            _make_member("user-1", "Patrick", "Alves", "Patrick"),
        ]

        # Project resolution
        proj = _make_project("proj-1", "FE", "Frontend")
        mock_resolve_project.return_value = proj.model_dump()

        # Work items, states, labels via paginate_all_async
        items = [_make_work_item("wi-1", "Fix bug", 1), _make_work_item("wi-2", "Add feature", 2)]
        mock_paginate.side_effect = [
            items,  # work items
            [_make_state("state-uuid-1", "Todo")],  # states
            [],  # labels
        ]

        await list_(project="Frontend")

        mock_output.assert_called_once()
        call_args = mock_output.call_args
        data = call_args[0][0]
        columns = call_args[0][1]
        assert len(data) == 2
        assert columns == WI_COLUMNS

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.commands.work_items.run_sdk")
    @patch("planecli.commands.work_items.paginate_all_async")
    async def test_list_all_projects_no_flag(
        self,
        mock_paginate,
        mock_run_sdk,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """wi list without --project should list items from all projects."""
        client = MagicMock()
        mock_get_client.return_value = client

        proj_client = MagicMock()
        mock_create_client.return_value = proj_client

        # Members via run_sdk
        mock_run_sdk.return_value = [
            _make_member("user-1", "Patrick", "Alves", "Patrick"),
        ]

        # Two projects
        proj1 = _make_project("proj-1", "FE", "Frontend")
        proj2 = _make_project("proj-2", "BE", "Backend")

        fe_items = [_make_work_item("wi-1", "Fix bug", 1)]
        be_items = [_make_work_item("wi-2", "Add API", 5)]

        # paginate_all_async calls: projects, then per-project (items, states, labels) x2
        mock_paginate.side_effect = [
            [proj1, proj2],  # all projects
            fe_items,  # FE items
            [_make_state("state-uuid-1", "Todo")],  # FE states
            [],  # FE labels
            be_items,  # BE items
            [_make_state("state-uuid-1", "In Progress")],  # BE states
            [],  # BE labels
        ]

        await list_()

        mock_output.assert_called_once()
        call_args = mock_output.call_args
        data = call_args[0][0]
        columns = call_args[0][1]

        # Items from both projects
        assert len(data) == 2
        identifiers = {d["project_identifier"] for d in data}
        assert identifiers == {"FE", "BE"}

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.commands.work_items.run_sdk")
    @patch("planecli.commands.work_items.paginate_all_async")
    async def test_list_all_projects_has_project_column(
        self,
        mock_paginate,
        mock_run_sdk,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """All-projects output should include Project column (WI_COLUMNS_ALL)."""
        client = MagicMock()
        mock_get_client.return_value = client

        proj_client = MagicMock()
        mock_create_client.return_value = proj_client

        mock_run_sdk.return_value = []  # members

        proj = _make_project("proj-1", "FE", "Frontend")

        items = [_make_work_item("wi-1", "Fix bug", 1)]
        mock_paginate.side_effect = [
            [proj],  # all projects
            items,  # items
            [],  # states
            [],  # labels
        ]

        await list_()

        call_args = mock_output.call_args
        columns = call_args[0][1]
        assert columns == WI_COLUMNS_ALL
        # First column should be Project
        assert columns[0] == ("project_identifier", "Project")

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.commands.work_items.run_sdk")
    @patch("planecli.commands.work_items.paginate_all_async")
    async def test_list_all_projects_empty_projects_skipped(
        self,
        mock_paginate,
        mock_run_sdk,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """Empty projects (no work items) should be silently skipped."""
        client = MagicMock()
        mock_get_client.return_value = client

        proj_client = MagicMock()
        mock_create_client.return_value = proj_client

        mock_run_sdk.return_value = []  # members

        proj1 = _make_project("proj-1", "FE", "Frontend")
        proj2 = _make_project("proj-2", "EMPTY", "Empty Project")

        mock_paginate.side_effect = [
            [proj1, proj2],  # all projects
            [_make_work_item("wi-1", "Fix bug", 1)],  # FE items
            [],  # FE states
            [],  # FE labels
            [],  # EMPTY items
            [],  # EMPTY states
            [],  # EMPTY labels
        ]

        await list_()

        call_args = mock_output.call_args
        data = call_args[0][0]
        assert len(data) == 1
        assert data[0]["project_identifier"] == "FE"

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.resolve_user_async")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.commands.work_items.run_sdk")
    @patch("planecli.commands.work_items.paginate_all_async")
    async def test_list_all_projects_filter_by_assignee(
        self,
        mock_paginate,
        mock_run_sdk,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_resolve_user,
        mock_output,
    ):
        """--assignee filter should work across all projects."""
        client = MagicMock()
        mock_get_client.return_value = client

        proj_client = MagicMock()
        mock_create_client.return_value = proj_client

        mock_run_sdk.return_value = [
            _make_member("user-1", "Patrick", "Alves", "Patrick"),
        ]

        proj = _make_project("proj-1", "FE", "Frontend")

        items = [
            _make_work_item("wi-1", "Assigned to me", 1, assignees=["user-1"]),
            _make_work_item("wi-2", "Unassigned", 2, assignees=[]),
        ]
        mock_paginate.side_effect = [
            [proj],  # all projects
            items,  # items
            [],  # states
            [],  # labels
        ]

        mock_resolve_user.return_value = {"id": "user-1", "display_name": "Patrick"}

        await list_(assignee="me")

        call_args = mock_output.call_args
        data = call_args[0][0]
        assert len(data) == 1
        assert data[0]["name"] == "Assigned to me"

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.commands.work_items.run_sdk")
    @patch("planecli.commands.work_items.paginate_all_async")
    async def test_list_all_projects_filter_by_state(
        self,
        mock_paginate,
        mock_run_sdk,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """--state filter should work across all projects."""
        client = MagicMock()
        mock_get_client.return_value = client

        proj_client = MagicMock()
        mock_create_client.return_value = proj_client

        mock_run_sdk.return_value = []  # members

        proj1 = _make_project("proj-1", "FE", "Frontend")
        proj2 = _make_project("proj-2", "BE", "Backend")

        mock_paginate.side_effect = [
            [proj1, proj2],  # all projects
            [_make_work_item("wi-1", "FE task", 1, state="s-todo")],  # FE items
            [_make_state("s-todo", "Todo")],  # FE states
            [],  # FE labels
            [_make_work_item("wi-2", "BE task", 2, state="s-progress")],  # BE items
            [_make_state("s-progress", "In Progress")],  # BE states
            [],  # BE labels
        ]

        await list_(state="In Progress")

        call_args = mock_output.call_args
        data = call_args[0][0]
        assert len(data) == 1
        assert data[0]["project_identifier"] == "BE"

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.commands.work_items.run_sdk")
    @patch("planecli.commands.work_items.paginate_all_async")
    async def test_list_all_projects_sort_and_limit(
        self,
        mock_paginate,
        mock_run_sdk,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """--sort and --limit should work across merged results."""
        client = MagicMock()
        mock_get_client.return_value = client

        proj_client = MagicMock()
        mock_create_client.return_value = proj_client

        mock_run_sdk.return_value = []  # members

        proj = _make_project("proj-1", "FE", "Frontend")

        items = [
            _make_work_item("wi-1", "Old item", 1, created_at="2026-02-01T12:00:00Z"),
            _make_work_item("wi-2", "New item", 2, created_at="2026-02-10T12:00:00Z"),
            _make_work_item("wi-3", "Mid item", 3, created_at="2026-02-05T12:00:00Z"),
        ]
        mock_paginate.side_effect = [
            [proj],  # all projects
            items,  # items
            [],  # states
            [],  # labels
        ]

        await list_(limit=2)

        call_args = mock_output.call_args
        data = call_args[0][0]
        # Sorted by created desc, limited to 2
        assert len(data) == 2
        assert data[0]["name"] == "New item"
        assert data[1]["name"] == "Mid item"

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.commands.work_items.run_sdk")
    @patch("planecli.commands.work_items.paginate_all_async")
    async def test_list_all_projects_json_output(
        self,
        mock_paginate,
        mock_run_sdk,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """--json flag should work with all-projects listing."""
        client = MagicMock()
        mock_get_client.return_value = client

        proj_client = MagicMock()
        mock_create_client.return_value = proj_client

        mock_run_sdk.return_value = []  # members

        proj = _make_project("proj-1", "FE", "Frontend")

        items = [_make_work_item("wi-1", "Fix bug", 1)]
        mock_paginate.side_effect = [
            [proj],  # all projects
            items,  # items
            [],  # states
            [],  # labels
        ]

        await list_(json=True)

        call_args = mock_output.call_args
        assert call_args[1]["as_json"] is True
        data = call_args[0][0]
        # project_identifier should be present in data for JSON output
        assert data[0]["project_identifier"] == "FE"
