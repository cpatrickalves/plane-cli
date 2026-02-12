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


def _make_work_item_dict(
    item_id: str,
    name: str,
    sequence_id: int,
    state: str = "state-uuid-1",
    assignees: list | None = None,
    labels: list | None = None,
    created_at: str = "2026-02-10T12:00:00Z",
    updated_at: str = "2026-02-10T12:00:00Z",
) -> dict:
    """Return a work item as a dict (how cached_list_work_items returns them)."""
    return {
        "id": item_id,
        "name": name,
        "sequence_id": sequence_id,
        "state": state,
        "assignees": assignees or [],
        "labels": labels or [],
        "priority": "medium",
        "created_at": created_at,
        "updated_at": updated_at,
    }


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
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_single_project(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_members,
        mock_cached_work_items,
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

        # Work items (cached)
        mock_cached_work_items.return_value = [
            _make_work_item_dict("wi-1", "Fix bug", 1),
            _make_work_item_dict("wi-2", "Add feature", 2),
        ]

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
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
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
        mock_cached_work_items,
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

        # Work items per project (cached)
        mock_cached_work_items.side_effect = [
            [_make_work_item_dict("wi-1", "Fix bug", 1)],
            [_make_work_item_dict("wi-2", "Add API", 5)],
        ]

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
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
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
        mock_cached_work_items,
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

        mock_cached_work_items.return_value = [
            _make_work_item_dict("wi-1", "Fix bug", 1),
        ]

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
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
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
        mock_cached_work_items,
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

        mock_cached_work_items.side_effect = [
            [_make_work_item_dict("wi-1", "Fix bug", 1)],  # FE items
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
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
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
        mock_cached_work_items,
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

        mock_cached_work_items.return_value = [
            _make_work_item_dict("wi-1", "Assigned to me", 1, assignees=["user-1"]),
            _make_work_item_dict("wi-2", "Unassigned", 2, assignees=[]),
        ]

        mock_cached_states.return_value = []
        mock_cached_labels.return_value = []

        mock_resolve_user.return_value = {"id": "user-1", "display_name": "Patrick"}

        await list_(assignee="me")

        call_args = mock_output.call_args
        data = call_args[0][0]
        assert len(data) == 1
        assert data[0]["name"] == "Assigned to me"

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.resolve_user_async")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_filter_by_assignee_and_multiple_states(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_cached_work_items,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_resolve_user,
        mock_output,
    ):
        """--assignee me --state 'In Review,In Progress' uses AND logic."""
        mock_get_client.return_value = MagicMock()
        mock_create_client.return_value = MagicMock()

        mock_cached_members.return_value = [
            _make_member_dict("user-1", "Patrick", "Alves", "Patrick"),
            _make_member_dict("user-2", "Braulio", "Silva", "Braulio"),
        ]

        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
        ]

        mock_cached_work_items.return_value = [
            _make_work_item_dict(
                "wi-1", "My progress task", 1, state="s-progress", assignees=["user-1"],
            ),
            _make_work_item_dict(
                "wi-2", "Other progress task", 2, state="s-progress", assignees=["user-2"],
            ),
            _make_work_item_dict(
                "wi-3", "My review task", 3, state="s-review", assignees=["user-1"],
            ),
            _make_work_item_dict(
                "wi-4", "My done task", 4, state="s-done", assignees=["user-1"],
            ),
        ]

        mock_cached_states.return_value = [
            _make_state_dict("s-progress", "In Progress"),
            _make_state_dict("s-review", "In Review"),
            _make_state_dict("s-done", "Done"),
        ]
        mock_cached_labels.return_value = []

        mock_resolve_user.return_value = {"id": "user-1", "display_name": "Patrick"}

        await list_(assignee="me", state="In Review,In Progress")

        data = mock_output.call_args[0][0]
        assert len(data) == 2
        names = {d["name"] for d in data}
        assert names == {"My progress task", "My review task"}

    @patch("planecli.commands.work_items.resolve_user_async")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_filter_by_assignee_resolution_error(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_cached_work_items,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_resolve_user,
    ):
        """--assignee with invalid user raises error instead of silently passing."""
        from planecli.exceptions import ResourceNotFoundError

        mock_get_client.return_value = MagicMock()
        mock_create_client.return_value = MagicMock()
        mock_cached_members.return_value = []
        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
        ]
        mock_cached_work_items.return_value = [
            _make_work_item_dict("wi-1", "Some task", 1, assignees=["user-1"]),
        ]
        mock_cached_states.return_value = []
        mock_cached_labels.return_value = []

        mock_resolve_user.side_effect = ResourceNotFoundError("User", "nonexistent")

        import pytest
        with pytest.raises(ResourceNotFoundError):
            await list_(assignee="nonexistent")

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
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
        mock_cached_work_items,
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

        mock_cached_work_items.side_effect = [
            [_make_work_item_dict("wi-1", "FE task", 1, state="s-todo")],
            [_make_work_item_dict("wi-2", "BE task", 2, state="s-progress")],
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
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
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
        mock_cached_work_items,
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

        mock_cached_work_items.return_value = [
            _make_work_item_dict("wi-1", "Old item", 1, created_at="2026-02-01T12:00:00Z"),
            _make_work_item_dict("wi-2", "New item", 2, created_at="2026-02-10T12:00:00Z"),
            _make_work_item_dict("wi-3", "Mid item", 3, created_at="2026-02-05T12:00:00Z"),
        ]

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
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
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
        mock_cached_work_items,
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

        mock_cached_work_items.return_value = [
            _make_work_item_dict("wi-1", "Fix bug", 1),
        ]

        mock_cached_states.return_value = []
        mock_cached_labels.return_value = []

        await list_(json=True)

        call_args = mock_output.call_args
        assert call_args[1]["as_json"] is True
        data = call_args[0][0]
        assert data[0]["project_identifier"] == "FE"

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_filter_by_single_state(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_cached_work_items,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """Single --state value still works (backward compat)."""
        mock_get_client.return_value = MagicMock()
        mock_create_client.return_value = MagicMock()
        mock_cached_members.return_value = []
        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
        ]
        mock_cached_work_items.return_value = [
            _make_work_item_dict("wi-1", "Todo task", 1, state="s-todo"),
            _make_work_item_dict("wi-2", "Done task", 2, state="s-done"),
        ]
        mock_cached_states.return_value = [
            _make_state_dict("s-todo", "Todo"),
            _make_state_dict("s-done", "Done"),
        ]
        mock_cached_labels.return_value = []

        await list_(state="Todo")

        data = mock_output.call_args[0][0]
        assert len(data) == 1
        assert data[0]["name"] == "Todo task"

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_filter_by_multiple_states(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_cached_work_items,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """--state 'Todo,In Progress' returns items matching either state."""
        mock_get_client.return_value = MagicMock()
        mock_create_client.return_value = MagicMock()
        mock_cached_members.return_value = []
        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
        ]
        mock_cached_work_items.return_value = [
            _make_work_item_dict("wi-1", "Todo task", 1, state="s-todo"),
            _make_work_item_dict("wi-2", "Progress task", 2, state="s-progress"),
            _make_work_item_dict("wi-3", "Done task", 3, state="s-done"),
        ]
        mock_cached_states.return_value = [
            _make_state_dict("s-todo", "Todo"),
            _make_state_dict("s-progress", "In Progress"),
            _make_state_dict("s-done", "Done"),
        ]
        mock_cached_labels.return_value = []

        await list_(state="Todo,In Progress")

        data = mock_output.call_args[0][0]
        assert len(data) == 2
        names = {d["name"] for d in data}
        assert names == {"Todo task", "Progress task"}

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_filter_by_single_label(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_cached_work_items,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """--labels 'bug' returns items with 'bug' label."""
        mock_get_client.return_value = MagicMock()
        mock_create_client.return_value = MagicMock()
        mock_cached_members.return_value = []
        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
        ]
        mock_cached_work_items.return_value = [
            _make_work_item_dict("wi-1", "Bug task", 1, labels=["lbl-bug"]),
            _make_work_item_dict("wi-2", "Feature task", 2, labels=["lbl-feat"]),
        ]
        mock_cached_states.return_value = []
        mock_cached_labels.return_value = [
            _make_label_dict("lbl-bug", "bug"),
            _make_label_dict("lbl-feat", "feature"),
        ]

        await list_(labels="bug")

        data = mock_output.call_args[0][0]
        assert len(data) == 1
        assert data[0]["name"] == "Bug task"

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_filter_by_multiple_labels(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_cached_work_items,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """--labels 'bug,frontend' returns items matching either label."""
        mock_get_client.return_value = MagicMock()
        mock_create_client.return_value = MagicMock()
        mock_cached_members.return_value = []
        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
        ]
        mock_cached_work_items.return_value = [
            _make_work_item_dict("wi-1", "Bug task", 1, labels=["lbl-bug"]),
            _make_work_item_dict("wi-2", "FE task", 2, labels=["lbl-fe"]),
            _make_work_item_dict("wi-3", "Backend task", 3, labels=["lbl-be"]),
        ]
        mock_cached_states.return_value = []
        mock_cached_labels.return_value = [
            _make_label_dict("lbl-bug", "bug"),
            _make_label_dict("lbl-fe", "frontend"),
            _make_label_dict("lbl-be", "backend"),
        ]

        await list_(labels="bug,frontend")

        data = mock_output.call_args[0][0]
        assert len(data) == 2
        names = {d["name"] for d in data}
        assert names == {"Bug task", "FE task"}

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_filter_state_and_labels_combined(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_cached_work_items,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """--state 'Todo' --labels 'bug' uses AND logic."""
        mock_get_client.return_value = MagicMock()
        mock_create_client.return_value = MagicMock()
        mock_cached_members.return_value = []
        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
        ]
        mock_cached_work_items.return_value = [
            _make_work_item_dict("wi-1", "Todo bug", 1, state="s-todo", labels=["lbl-bug"]),
            _make_work_item_dict("wi-2", "Todo feat", 2, state="s-todo", labels=["lbl-feat"]),
            _make_work_item_dict("wi-3", "Done bug", 3, state="s-done", labels=["lbl-bug"]),
        ]
        mock_cached_states.return_value = [
            _make_state_dict("s-todo", "Todo"),
            _make_state_dict("s-done", "Done"),
        ]
        mock_cached_labels.return_value = [
            _make_label_dict("lbl-bug", "bug"),
            _make_label_dict("lbl-feat", "feature"),
        ]

        await list_(state="Todo", labels="bug")

        data = mock_output.call_args[0][0]
        assert len(data) == 1
        assert data[0]["name"] == "Todo bug"

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_filter_state_with_whitespace(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_cached_work_items,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """Whitespace around commas is trimmed: ' Todo , Done ' works."""
        mock_get_client.return_value = MagicMock()
        mock_create_client.return_value = MagicMock()
        mock_cached_members.return_value = []
        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
        ]
        mock_cached_work_items.return_value = [
            _make_work_item_dict("wi-1", "Todo task", 1, state="s-todo"),
            _make_work_item_dict("wi-2", "Done task", 2, state="s-done"),
            _make_work_item_dict("wi-3", "Progress task", 3, state="s-progress"),
        ]
        mock_cached_states.return_value = [
            _make_state_dict("s-todo", "Todo"),
            _make_state_dict("s-done", "Done"),
            _make_state_dict("s-progress", "In Progress"),
        ]
        mock_cached_labels.return_value = []

        await list_(state=" Todo , Done ")

        data = mock_output.call_args[0][0]
        assert len(data) == 2
        names = {d["name"] for d in data}
        assert names == {"Todo task", "Done task"}

    @patch("planecli.commands.work_items.output")
    @patch("planecli.commands.work_items.get_workspace", return_value="test-ws")
    @patch("planecli.commands.work_items.get_client")
    @patch("planecli.commands.work_items.create_client")
    @patch("planecli.cache.cached_list_work_items", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_members", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_projects", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_states", new_callable=AsyncMock)
    @patch("planecli.cache.cached_list_labels", new_callable=AsyncMock)
    async def test_list_filter_labels_no_match(
        self,
        mock_cached_labels,
        mock_cached_states,
        mock_cached_projects,
        mock_cached_members,
        mock_cached_work_items,
        mock_create_client,
        mock_get_client,
        mock_get_ws,
        mock_output,
    ):
        """--labels 'nonexistent' returns empty result."""
        mock_get_client.return_value = MagicMock()
        mock_create_client.return_value = MagicMock()
        mock_cached_members.return_value = []
        mock_cached_projects.return_value = [
            _make_project_dict("proj-1", "FE", "Frontend"),
        ]
        mock_cached_work_items.return_value = [
            _make_work_item_dict("wi-1", "Bug task", 1, labels=["lbl-bug"]),
        ]
        mock_cached_states.return_value = []
        mock_cached_labels.return_value = [
            _make_label_dict("lbl-bug", "bug"),
        ]

        await list_(labels="nonexistent")

        data = mock_output.call_args[0][0]
        assert len(data) == 0
