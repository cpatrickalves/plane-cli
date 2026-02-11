"""Cycle CRUD commands."""

from __future__ import annotations

from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.formatters import output, output_single
from planecli.utils.resolve import resolve_cycle, resolve_project

cycle_app = cyclopts.App(
    name=["cycle", "cycles"],
    help="Manage cycles (sprints).",
)

CYCLE_COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("start_date", "Start"),
    ("end_date", "End"),
    ("total_issues", "Issues"),
    ("completed_issues", "Done"),
]

CYCLE_FIELDS = [
    ("id", "UUID"),
    ("name", "Name"),
    ("description", "Description"),
    ("start_date", "Start Date"),
    ("end_date", "End Date"),
    ("owned_by", "Owner"),
    ("total_issues", "Total Issues"),
    ("completed_issues", "Completed"),
    ("started_issues", "Started"),
    ("unstarted_issues", "Unstarted"),
    ("backlog_issues", "Backlog"),
    ("cancelled_issues", "Cancelled"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]

# Reuse work item columns for cycle items listing
ITEM_COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("state", "State"),
    ("priority", "Priority"),
]


@cycle_app.command(name="list", alias="ls")
def list_(
    *,
    project: Annotated[str, Parameter(alias="-p")],
    sort: str = "created",
    limit: Annotated[int, Parameter(alias="-l")] = 50,
    json: bool = False,
) -> None:
    """List cycles in a project.

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

        cycles = _paginate_all(client.cycles.list, workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    data = [c.model_dump() for c in cycles]

    if sort == "updated":
        data.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    else:
        data.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    data = data[:limit]
    output(data, CYCLE_COLUMNS, title="Cycles", as_json=json)


@cycle_app.command(alias="read")
def show(
    cycle: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    json: bool = False,
) -> None:
    """Show cycle details.

    Parameters
    ----------
    cycle
        Cycle name or UUID.
    project
        Project name, identifier, or UUID.
    """
    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        data = resolve_cycle(cycle, client, workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, CYCLE_FIELDS, title="Cycle Details", as_json=json)


@cycle_app.command(alias="new")
def create(
    name: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    start_date: str | None = None,
    end_date: str | None = None,
    json: bool = False,
) -> None:
    """Create a new cycle.

    Parameters
    ----------
    name
        Cycle name.
    project
        Project name, identifier, or UUID.
    description
        Cycle description.
    start_date
        Start date (YYYY-MM-DD).
    end_date
        End date (YYYY-MM-DD).
    """
    from plane.models.cycles import CreateCycle

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        # Get current user as owner
        me = client.users.get_me()

        create_data = CreateCycle(name=name, owned_by=me.id, project_id=project_id)
        if description:
            create_data.description = description
        if start_date:
            create_data.start_date = start_date
        if end_date:
            create_data.end_date = end_date

        cycle = client.cycles.create(workspace, project_id, create_data)
        data = cycle.model_dump()
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, CYCLE_FIELDS, title="Cycle Created", as_json=json)


@cycle_app.command
def update(
    cycle: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    name: str | None = None,
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    start_date: str | None = None,
    end_date: str | None = None,
    json: bool = False,
) -> None:
    """Update a cycle.

    Parameters
    ----------
    cycle
        Cycle name or UUID.
    project
        Project name, identifier, or UUID.
    name
        New cycle name.
    description
        New description.
    start_date
        New start date (YYYY-MM-DD).
    end_date
        New end date (YYYY-MM-DD).
    """
    from plane.models.cycles import UpdateCycle

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        cyc_data = resolve_cycle(cycle, client, workspace, project_id)
        cycle_id = cyc_data["id"]

        update_data = UpdateCycle()
        if name:
            update_data.name = name
        if description:
            update_data.description = description
        if start_date:
            update_data.start_date = start_date
        if end_date:
            update_data.end_date = end_date

        updated = client.cycles.update(workspace, project_id, cycle_id, update_data)
        data = updated.model_dump()
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, CYCLE_FIELDS, title="Cycle Updated", as_json=json)


@cycle_app.command
def delete(
    cycle: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
) -> None:
    """Delete a cycle.

    Parameters
    ----------
    cycle
        Cycle name or UUID.
    project
        Project name, identifier, or UUID.
    """
    from planecli.formatters import console

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        cyc_data = resolve_cycle(cycle, client, workspace, project_id)
        cycle_id = cyc_data["id"]
        cycle_name = cyc_data.get("name", cycle_id)

        client.cycles.delete(workspace, project_id, cycle_id)
    except PlaneError as e:
        raise handle_api_error(e)

    console.print(f"[green]Cycle '{cycle_name}' deleted.[/]")


@cycle_app.command(name="add-item")
def add_item(
    cycle: str,
    work_item: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
) -> None:
    """Add a work item to a cycle.

    Parameters
    ----------
    cycle
        Cycle name or UUID.
    work_item
        Work item identifier (ABC-123) or UUID.
    project
        Project name, identifier, or UUID.
    """
    from planecli.formatters import console
    from planecli.utils.resolve import resolve_work_item

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        cyc_data = resolve_cycle(cycle, client, workspace, project_id)
        cycle_id = cyc_data["id"]

        item = resolve_work_item(work_item, client, workspace, project_id)
        item_id = item["id"]

        client.cycles.add_work_items(workspace, project_id, cycle_id, [item_id])
    except PlaneError as e:
        raise handle_api_error(e)

    console.print(f"[green]Work item added to cycle '{cyc_data.get('name', cycle_id)}'.[/]")


@cycle_app.command(name="remove-item")
def remove_item(
    cycle: str,
    work_item: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
) -> None:
    """Remove a work item from a cycle.

    Parameters
    ----------
    cycle
        Cycle name or UUID.
    work_item
        Work item identifier (ABC-123) or UUID.
    project
        Project name, identifier, or UUID.
    """
    from planecli.formatters import console
    from planecli.utils.resolve import resolve_work_item

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        cyc_data = resolve_cycle(cycle, client, workspace, project_id)
        cycle_id = cyc_data["id"]

        item = resolve_work_item(work_item, client, workspace, project_id)
        item_id = item["id"]

        client.cycles.remove_work_item(workspace, project_id, cycle_id, item_id)
    except PlaneError as e:
        raise handle_api_error(e)

    console.print(f"[green]Work item removed from cycle '{cyc_data.get('name', cycle_id)}'.[/]")


@cycle_app.command
def items(
    cycle: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    limit: Annotated[int, Parameter(alias="-l")] = 50,
    json: bool = False,
) -> None:
    """List work items in a cycle.

    Parameters
    ----------
    cycle
        Cycle name or UUID.
    project
        Project name, identifier, or UUID.
    limit
        Maximum results to show.
    """
    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        cyc_data = resolve_cycle(cycle, client, workspace, project_id)
        cycle_id = cyc_data["id"]

        response = client.cycles.list_work_items(workspace, project_id, cycle_id)
        work_items = response.results if hasattr(response, "results") else []
    except PlaneError as e:
        raise handle_api_error(e)

    data = [item.model_dump() for item in work_items]
    data = data[:limit]
    cycle_name = cyc_data.get("name", cycle_id)
    output(data, ITEM_COLUMNS, title=f"Work Items in '{cycle_name}'", as_json=json)
