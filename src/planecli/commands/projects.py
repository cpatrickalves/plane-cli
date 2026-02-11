"""Project CRUD commands."""

from __future__ import annotations

from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.async_sdk import paginate_all_async, run_sdk
from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.formatters import output, output_single
from planecli.utils.resolve import resolve_project_async

project_app = cyclopts.App(
    name=["project", "projects"],
    help="Manage projects.",
)

PROJECT_COLUMNS = [
    ("identifier", "ID"),
    ("name", "Name"),
    ("state_display", "State"),
    ("description", "Description"),
    ("created_at", "Created"),
]

# Plane project network values map to these states
_NETWORK_TO_STATE = {
    0: "planned",
    1: "started",
    2: "paused",
    3: "completed",
    4: "canceled",
}


def _enrich_project(data: dict) -> dict:
    """Add convenience fields to a project dict."""
    network = data.get("network")
    fallback = str(network) if network is not None else ""
    data["state_display"] = _NETWORK_TO_STATE.get(network, fallback)
    return data

PROJECT_FIELDS = [
    ("id", "UUID"),
    ("identifier", "Identifier"),
    ("name", "Name"),
    ("description", "Description"),
    ("network", "Network"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]


@project_app.command(name="list", alias="ls")
async def list_(
    *,
    state: Annotated[str | None, Parameter(alias="-s")] = None,
    limit: Annotated[int, Parameter(alias="-l")] = 50,
    sort: str = "linear",
    json: bool = False,
) -> None:
    """List all projects in the workspace.

    Parameters
    ----------
    state
        Filter by state: planned, started, paused, completed, canceled.
    limit
        Maximum results to show.
    sort
        Sort order: linear (default), created, updated.
    """
    try:
        client = get_client()
        workspace = get_workspace()
        projects = await paginate_all_async(client.projects.list, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    data = [_enrich_project(p.model_dump()) for p in projects]

    # Filter by state
    if state:
        state_lower = state.lower()
        # Reverse lookup: state name -> network value
        state_to_network = {v: k for k, v in _NETWORK_TO_STATE.items()}
        if state_lower not in state_to_network:
            valid = ", ".join(sorted(state_to_network.keys()))
            from planecli.exceptions import ValidationError
            raise ValidationError(
                f"Invalid state '{state}'. Valid states: {valid}"
            )
        target_network = state_to_network[state_lower]
        data = [d for d in data if d.get("network") == target_network]

    # Sort
    if sort == "updated":
        data.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    elif sort == "created":
        data.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    else:
        # "linear" - sort by sort_order if available, otherwise by created_at
        data.sort(key=lambda x: x.get("sort_order") or 0)

    data = data[:limit]
    output(data, PROJECT_COLUMNS, title="Projects", as_json=json)


@project_app.command(alias="read")
async def show(
    project: str,
    *,
    json: bool = False,
) -> None:
    """Show project details.

    Parameters
    ----------
    project
        Project name, identifier, or UUID.
    """
    try:
        client = get_client()
        workspace = get_workspace()
        data = await resolve_project_async(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, PROJECT_FIELDS, title="Project Details", as_json=json)


@project_app.command(alias="new")
async def create(
    name: str,
    *,
    identifier: Annotated[str | None, Parameter(alias="-i")] = None,
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    json: bool = False,
) -> None:
    """Create a new project.

    Parameters
    ----------
    name
        Project name.
    identifier
        Short project identifier (e.g. FE, BE). Auto-generated if not specified.
    description
        Project description.
    """
    from plane.models.projects import CreateProject

    try:
        client = get_client()
        workspace = get_workspace()

        create_data = CreateProject(name=name)
        if identifier:
            create_data.identifier = identifier.upper()
        if description:
            create_data.description = description

        project = await run_sdk(client.projects.create, workspace, create_data)
        data = project.model_dump()
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, PROJECT_FIELDS, title="Project Created", as_json=json)


@project_app.command
async def update(
    project: str,
    *,
    name: str | None = None,
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    json: bool = False,
) -> None:
    """Update an existing project.

    Parameters
    ----------
    project
        Project name, identifier, or UUID.
    name
        New project name.
    description
        New project description.
    """
    from plane.models.projects import UpdateProject

    try:
        client = get_client()
        workspace = get_workspace()
        resolved = await resolve_project_async(project, client, workspace)
        project_id = resolved["id"]

        update_data = UpdateProject()
        if name:
            update_data.name = name
        if description:
            update_data.description = description

        updated = await run_sdk(
            client.projects.update, workspace, project_id, update_data
        )
        data = updated.model_dump()
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, PROJECT_FIELDS, title="Project Updated", as_json=json)


@project_app.command
async def delete(project: str) -> None:
    """Delete a project.

    Parameters
    ----------
    project
        Project name, identifier, or UUID.
    """
    from planecli.formatters import console

    try:
        client = get_client()
        workspace = get_workspace()
        resolved = await resolve_project_async(project, client, workspace)
        project_id = resolved["id"]
        project_name = resolved.get("name", project_id)

        await run_sdk(client.projects.delete, workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    console.print(f"[green]Project '{project_name}' deleted.[/]")
