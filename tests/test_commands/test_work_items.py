"""Tests for work item commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from planecli.commands.work_items import WI_COLUMNS, WI_COLUMNS_ALL, list_


def _make_member_dict(member_id: str, first_name: str, last_name: str, display_name: str):
    """Return a member as a dict (how cached_list_members returns them)."""
    return {
        "id": member_id,
        "first_name": first_name,
        "last_name": last_name,
        "display_name": display_name,
        "email": f"{first_name.lower()}@example.com",
    }


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


def _make_state_dict(state_id: str, name: str):
    """Return a state as a dict (how cached_list_states returns them)."""
    return {"id": state_id, "name": name, "color": None, "group": None}


def _make_label_dict(label_id: str, name: str):
    """Return a label as a dict (how cached_list_labels returns them)."""
    return {"id": label_id, "name": name, "color": None}


def _make_project_dict(project_id: str, identifier: str, name: str):
    """Return a project as a dict (how cached_list_projects returns them)."""
    return {"id": project_id, "identifier": identifier, "name": name}


class TestWiList:
    """Tests for the wi list command."""

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.commands.work_items.resolve_project_async")
    @patch("planecli.commands.work_items.paginate_all_async")
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_single_project(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_members,
        mock_paginate,
        mock_resolve_project,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """wi list -p Frontend should list items from one project only."""
        client = MagicMock()
        mock_get_client.return_value = client

        proj_client = MagicMock()
        mock_create_client.return_value = proj_client

        # Members (cached)
        mock_cached_members.return_value = [
            _make_member_dict("user-1", "Patrick", "Alves", "Patrick"),
        ]

        # Project resolution
        mock_resolve_project.return_value = _make_project_dict("proj-1", "FE", "Frontend")

        # Work items via paginate_all_async (not cached)
        items = [_make_work_item("wi-1", "Fix bug", 1), _make_work_item("wi-2", "Add feature", 2)]
        mock_paginate.return_value = items

        # States and labels (cached)
        mock_cached_states.return_value = [_make_state_dict("state-uuid-1", "Todo")]
        mock_cached_labels.return_value = []

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
    @patch("planecli.commands.work_items.paginate_all_async")
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_all_projects_no_flag(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_paginate,
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

        # Members (cached)
        mock_cached_members.return_value = [
            _make_member_dict("user-1", "Patrick", "Alves", "Patrick"),
        ]

        # Projects (cached)
        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
            _make_project_dict("proj-2", "BE", "Backend"),
        ]

        # Work items per project via paginate_all_async
        fe_items = [_make_work_item("wi-1", "Fix bug", 1)]
        be_items = [_make_work_item("wi-2", "Add API", 5)]
        mock_paginate.side_effect = [fe_items, be_items]

        # States and labels (cached, called per project)
        mock_cached_states.side_effect = [
            [_make_state_dict("state-uuid-1", "Todo")],
            [_make_state_dict("state-uuid-1", "In Progress")],
        ]
        mock_cached_labels.side_effect = [[], []]

        await list_()

        mock_output.assert_called_once()
        call_args = mock_output.call_args
        data = call_args[0][0]

        # Items from both projects
        assert len(data) == 2
        identifiers = {d["project_identifier"] for d in data}
        assert identifiers == {"FE", "BE"}

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.commands.work_items.paginate_all_async")
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_all_projects_has_project_column(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_paginate,
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

        mock_cached_members.return_value = []

        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
        ]

        items = [_make_work_item("wi-1", "Fix bug", 1)]
        mock_paginate.return_value = items

        mock_cached_states.return_value = []
        mock_cached_labels.return_value = []

        await list_()

        call_args = mock_output.call_args
        columns = call_args[0][1]
        assert columns == WI_COLUMNS_ALL
        assert columns[0] == ("project_identifier", "Project")

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.commands.work_items.paginate_all_async")
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_all_projects_empty_projects_skipped(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_paginate,
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

        mock_cached_members.return_value = []

        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
            _make_project_dict("proj-2", "EMPTY", "Empty Project"),
        ]

        mock_paginate.side_effect = [
            [_make_work_item("wi-1", "Fix bug", 1)],  # FE items
            [],  # EMPTY items
        ]

        mock_cached_states.side_effect = [
            [],  # FE states
            [],  # EMPTY states
        ]
        mock_cached_labels.side_effect = [
            [],  # FE labels
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
    @patch("planecli.commands.work_items.paginate_all_async")
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_all_projects_filter_by_assignee(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_paginate,
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

        mock_cached_members.return_value = [
            _make_member_dict("user-1", "Patrick", "Alves", "Patrick"),
        ]

        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
        ]

        items = [
            _make_work_item("wi-1", "Assigned to me", 1, assignees=["user-1"]),
            _make_work_item("wi-2", "Unassigned", 2, assignees=[]),
        ]
        mock_paginate.return_value = items

        mock_cached_states.return_value = []
        mock_cached_labels.return_value = []

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
    @patch("planecli.commands.work_items.paginate_all_async")
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_all_projects_filter_by_state(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_paginate,
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

        mock_cached_members.return_value = []

        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
            _make_project_dict("proj-2", "BE", "Backend"),
        ]

        mock_paginate.side_effect = [
            [_make_work_item("wi-1", "FE task", 1, state="s-todo")],
            [_make_work_item("wi-2", "BE task", 2, state="s-progress")],
        ]

        mock_cached_states.side_effect = [
            [_make_state_dict("s-todo", "Todo")],
            [_make_state_dict("s-progress", "In Progress")],
        ]
        mock_cached_labels.side_effect = [[], []]

        await list_(state="In Progress")

        call_args = mock_output.call_args
        data = call_args[0][0]
        assert len(data) == 1
        assert data[0]["project_identifier"] == "BE"

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.commands.work_items.paginate_all_async")
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_all_projects_sort_and_limit(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_paginate,
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

        mock_cached_members.return_value = []

        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
        ]

        items = [
            _make_work_item("wi-1", "Old item", 1, created_at="2026-02-01T12:00:00Z"),
            _make_work_item("wi-2", "New item", 2, created_at="2026-02-10T12:00:00Z"),
            _make_work_item("wi-3", "Mid item", 3, created_at="2026-02-05T12:00:00Z"),
        ]
        mock_paginate.return_value = items

        mock_cached_states.return_value = []
        mock_cached_labels.return_value = []

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
    @patch("planecli.commands.work_items.paginate_all_async")
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_all_projects_json_output(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_paginate,
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

        mock_cached_members.return_value = []

        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
        ]

        items = [_make_work_item("wi-1", "Fix bug", 1)]
        mock_paginate.return_value = items

        mock_cached_states.return_value = []
        mock_cached_labels.return_value = []

        await list_(json=True)

        call_args = mock_output.call_args
        assert call_args[1]["as_json"] is True
        data = call_args[0][0]
        assert data[0]["project_identifier"] == "FE"
