"""Project CRUD commands."""

from __future__ import annotations

from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.formatters import output, output_single
from planecli.utils.resolve import resolve_project

project_app = cyclopts.App(
    name=["project", "projects"],
    help="Manage projects.",
)

PROJECT_COLUMNS = [
    ("identifier", "ID"),
    ("name", "Name"),
    ("description", "Description"),
    ("created_at", "Created"),
]

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
def list_(
    *,
    limit: Annotated[int, Parameter(alias="-l")] = 50,
    sort: str = "created",
    json: bool = False,
) -> None:
    """List all projects in the workspace."""
    from planecli.utils.resolve import _paginate_all

    try:
        client = get_client()
        workspace = get_workspace()
        projects = _paginate_all(client.projects.list, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    data = [p.model_dump() for p in projects]

    # Sort
    if sort == "updated":
        data.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    else:
        data.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    data = data[:limit]
    output(data, PROJECT_COLUMNS, title="Projects", as_json=json)


@project_app.command(alias="read")
def show(
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
        data = resolve_project(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, PROJECT_FIELDS, title="Project Details", as_json=json)


@project_app.command(alias="new")
def create(
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

        project = client.projects.create(workspace, create_data)
        data = project.model_dump()
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, PROJECT_FIELDS, title="Project Created", as_json=json)


@project_app.command
def update(
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
        resolved = resolve_project(project, client, workspace)
        project_id = resolved["id"]

        update_data = UpdateProject()
        if name:
            update_data.name = name
        if description:
            update_data.description = description

        updated = client.projects.update(workspace, project_id, update_data)
        data = updated.model_dump()
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, PROJECT_FIELDS, title="Project Updated", as_json=json)


@project_app.command
def delete(project: str) -> None:
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
        resolved = resolve_project(project, client, workspace)
        project_id = resolved["id"]
        project_name = resolved.get("name", project_id)

        client.projects.delete(workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    console.print(f"[green]Project '{project_name}' deleted.[/]")
