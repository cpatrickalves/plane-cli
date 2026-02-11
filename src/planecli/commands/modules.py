"""Module commands."""

from __future__ import annotations

from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.formatters import output, output_single
from planecli.utils.resolve import resolve_module, resolve_project

module_app = cyclopts.App(
    name=["module", "modules"],
    help="Manage modules.",
)

MODULE_COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("status", "Status"),
    ("start_date", "Start"),
    ("target_date", "End"),
]

MODULE_FIELDS = [
    ("id", "UUID"),
    ("name", "Name"),
    ("description", "Description"),
    ("status", "Status"),
    ("start_date", "Start Date"),
    ("target_date", "Target Date"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]


@module_app.command(name="list", alias="ls")
def list_(
    *,
    project: Annotated[str, Parameter(alias="-p")],
    sort: str = "created",
    limit: Annotated[int, Parameter(alias="-l")] = 50,
    json: bool = False,
) -> None:
    """List modules in a project.

    Parameters
    ----------
    project
        Project name, identifier, or UUID.
    sort
        Sort by: created (default), updated.
    limit
        Maximum results to show.
    """
    from planecli.utils.resolve import _paginate_all

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        modules = _paginate_all(client.modules.list, workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    data = [m.model_dump() for m in modules]

    if sort == "updated":
        data.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    else:
        data.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    data = data[:limit]
    output(data, MODULE_COLUMNS, title="Modules", as_json=json)


@module_app.command(alias="read")
def show(
    module: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    json: bool = False,
) -> None:
    """Show module details.

    Parameters
    ----------
    module
        Module name or UUID.
    project
        Project name, identifier, or UUID.
    """
    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        data = resolve_module(module, client, workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, MODULE_FIELDS, title="Module Details", as_json=json)


@module_app.command(alias="new")
def create(
    name: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    start_date: str | None = None,
    end_date: str | None = None,
    json: bool = False,
) -> None:
    """Create a new module.

    Parameters
    ----------
    name
        Module name.
    project
        Project name, identifier, or UUID.
    description
        Module description.
    start_date
        Start date (YYYY-MM-DD).
    end_date
        End date (YYYY-MM-DD).
    """
    from plane.models.modules import CreateModule

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        create_data = CreateModule(name=name)
        if description:
            create_data.description = description
        if start_date:
            create_data.start_date = start_date
        if end_date:
            create_data.target_date = end_date

        mod = client.modules.create(workspace, project_id, create_data)
        data = mod.model_dump()
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, MODULE_FIELDS, title="Module Created", as_json=json)


@module_app.command
def update(
    module: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    name: str | None = None,
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    start_date: str | None = None,
    end_date: str | None = None,
    json: bool = False,
) -> None:
    """Update a module.

    Parameters
    ----------
    module
        Module name or UUID.
    project
        Project name, identifier, or UUID.
    name
        New module name.
    description
        New description.
    start_date
        New start date (YYYY-MM-DD).
    end_date
        New end date (YYYY-MM-DD).
    """
    from plane.models.modules import UpdateModule

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        mod_data = resolve_module(module, client, workspace, project_id)
        module_id = mod_data["id"]

        update_data = UpdateModule()
        if name:
            update_data.name = name
        if description:
            update_data.description = description
        if start_date:
            update_data.start_date = start_date
        if end_date:
            update_data.target_date = end_date

        updated = client.modules.update(workspace, project_id, module_id, update_data)
        data = updated.model_dump()
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, MODULE_FIELDS, title="Module Updated", as_json=json)


@module_app.command
def delete(
    module: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
) -> None:
    """Delete a module.

    Parameters
    ----------
    module
        Module name or UUID.
    project
        Project name, identifier, or UUID.
    """
    from planecli.formatters import console

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        mod_data = resolve_module(module, client, workspace, project_id)
        module_id = mod_data["id"]
        module_name = mod_data.get("name", module_id)

        client.modules.delete(workspace, project_id, module_id)
    except PlaneError as e:
        raise handle_api_error(e)

    console.print(f"[green]Module '{module_name}' deleted.[/]")
