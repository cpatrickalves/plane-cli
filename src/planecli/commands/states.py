"""State CRUD commands."""

from __future__ import annotations

from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.formatters import output, output_single
from planecli.utils.resolve import resolve_project, resolve_state

state_app = cyclopts.App(
    name=["state", "states"],
    help="Manage project states.",
)

STATE_COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("color", "Color"),
    ("group", "Group"),
    ("sequence", "Sequence"),
]

STATE_FIELDS = [
    ("id", "UUID"),
    ("name", "Name"),
    ("color", "Color"),
    ("description", "Description"),
    ("group", "Group"),
    ("sequence", "Sequence"),
    ("is_triage", "Is Triage"),
    ("default", "Default"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]


@state_app.command(name="list", alias="ls")
def list_(
    *,
    project: Annotated[str, Parameter(alias="-p")],
    group: str | None = None,
    sort: str = "sequence",
    limit: Annotated[int, Parameter(alias="-l")] = 50,
    json: bool = False,
) -> None:
    """List states in a project.

    Parameters
    ----------
    project
        Project name, identifier, or UUID.
    group
        Filter by group: backlog, unstarted, started, completed, cancelled, triage.
    sort
        Sort by: sequence (default), created, updated.
    limit
        Maximum results to show.
    """
    from planecli.utils.resolve import _paginate_all

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        states = _paginate_all(client.states.list, workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    data = [s.model_dump() for s in states]

    # Filter by group
    if group:
        group_lower = group.lower()
        data = [d for d in data if (d.get("group") or "").lower() == group_lower]

    # Sort
    if sort == "updated":
        data.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    elif sort == "created":
        data.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    else:
        # sequence
        data.sort(key=lambda x: x.get("sequence") or 0)

    data = data[:limit]

    # Colorize state names and color swatches for table display
    if not json:
        from planecli.utils.colors import color_swatch, colorize

        for d in data:
            raw_color = d.get("color")
            d["name"] = colorize(d.get("name", ""), raw_color)
            d["color"] = color_swatch(raw_color or "")

    output(data, STATE_COLUMNS, title="States", as_json=json)


@state_app.command(alias="read")
def show(
    state: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    json: bool = False,
) -> None:
    """Show state details.

    Parameters
    ----------
    state
        State name or UUID.
    project
        Project name, identifier, or UUID.
    """
    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        data = resolve_state(state, client, workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    if not json:
        from planecli.utils.colors import color_swatch, colorize

        raw_color = data.get("color")
        data["name"] = colorize(data.get("name", ""), raw_color)
        data["color"] = color_swatch(raw_color or "")

    output_single(data, STATE_FIELDS, title="State Details", as_json=json)


@state_app.command(alias="new")
def create(
    name: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    color: str = "#000000",
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    group: str | None = None,
    json: bool = False,
) -> None:
    """Create a new state.

    Parameters
    ----------
    name
        State name.
    project
        Project name, identifier, or UUID.
    color
        State color (hex, e.g. #FFA500). Defaults to #000000.
    description
        State description.
    group
        State group: backlog, unstarted, started, completed, cancelled, triage.
    """
    from plane.models.states import CreateState

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        create_data = CreateState(name=name, color=color)
        if description:
            create_data.description = description
        if group:
            create_data.group = group.lower()

        state = client.states.create(workspace, project_id, create_data)
        data = state.model_dump()
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, STATE_FIELDS, title="State Created", as_json=json)


@state_app.command
def update(
    state: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    name: str | None = None,
    color: str | None = None,
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    group: str | None = None,
    json: bool = False,
) -> None:
    """Update a state.

    Parameters
    ----------
    state
        State name or UUID.
    project
        Project name, identifier, or UUID.
    name
        New state name.
    color
        New color (hex, e.g. #FFA500).
    description
        New description.
    group
        New group: backlog, unstarted, started, completed, cancelled, triage.
    """
    from plane.models.states import UpdateState

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        st_data = resolve_state(state, client, workspace, project_id)
        state_id = st_data["id"]

        update_data = UpdateState()
        if name:
            update_data.name = name
        if color:
            update_data.color = color
        if description:
            update_data.description = description
        if group:
            update_data.group = group.lower()

        updated = client.states.update(workspace, project_id, state_id, update_data)
        data = updated.model_dump()
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, STATE_FIELDS, title="State Updated", as_json=json)


@state_app.command
def delete(
    state: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
) -> None:
    """Delete a state.

    Parameters
    ----------
    state
        State name or UUID.
    project
        Project name, identifier, or UUID.
    """
    from planecli.formatters import console

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        st_data = resolve_state(state, client, workspace, project_id)
        state_id = st_data["id"]
        state_name = st_data.get("name", state_id)

        client.states.delete(workspace, project_id, state_id)
    except PlaneError as e:
        raise handle_api_error(e)

    console.print(f"[green]State '{state_name}' deleted.[/]")
