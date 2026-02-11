"""Label CRUD commands."""

from __future__ import annotations

from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.formatters import output, output_single
from planecli.utils.resolve import resolve_label, resolve_project

label_app = cyclopts.App(
    name=["label", "labels"],
    help="Manage project labels.",
)

LABEL_COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("color", "Color"),
    ("description", "Description"),
]

LABEL_FIELDS = [
    ("id", "UUID"),
    ("name", "Name"),
    ("color", "Color"),
    ("description", "Description"),
    ("parent", "Parent"),
    ("sort_order", "Sort Order"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]


@label_app.command(name="list", alias="ls")
def list_(
    *,
    project: Annotated[str, Parameter(alias="-p")],
    sort: str = "created",
    limit: Annotated[int, Parameter(alias="-l")] = 50,
    json: bool = False,
) -> None:
    """List labels in a project.

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

        labels = _paginate_all(client.labels.list, workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    data = [lbl.model_dump() for lbl in labels]

    if sort == "updated":
        data.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    else:
        data.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    data = data[:limit]
    output(data, LABEL_COLUMNS, title="Labels", as_json=json)


@label_app.command(alias="read")
def show(
    label: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    json: bool = False,
) -> None:
    """Show label details.

    Parameters
    ----------
    label
        Label name or UUID.
    project
        Project name, identifier, or UUID.
    """
    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        data = resolve_label(label, client, workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, LABEL_FIELDS, title="Label Details", as_json=json)


@label_app.command(alias="new")
def create(
    name: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    color: str | None = None,
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    json: bool = False,
) -> None:
    """Create a new label.

    Parameters
    ----------
    name
        Label name.
    project
        Project name, identifier, or UUID.
    color
        Label color (hex, e.g. #FF0000).
    description
        Label description.
    """
    from plane.models.labels import CreateLabel

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        create_data = CreateLabel(name=name)
        if color:
            create_data.color = color
        if description:
            create_data.description = description

        label = client.labels.create(workspace, project_id, create_data)
        data = label.model_dump()
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, LABEL_FIELDS, title="Label Created", as_json=json)


@label_app.command
def update(
    label: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    name: str | None = None,
    color: str | None = None,
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    json: bool = False,
) -> None:
    """Update a label.

    Parameters
    ----------
    label
        Label name or UUID.
    project
        Project name, identifier, or UUID.
    name
        New label name.
    color
        New color (hex, e.g. #FF0000).
    description
        New description.
    """
    from plane.models.labels import UpdateLabel

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        lbl_data = resolve_label(label, client, workspace, project_id)
        label_id = lbl_data["id"]

        update_data = UpdateLabel()
        if name:
            update_data.name = name
        if color:
            update_data.color = color
        if description:
            update_data.description = description

        updated = client.labels.update(workspace, project_id, label_id, update_data)
        data = updated.model_dump()
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, LABEL_FIELDS, title="Label Updated", as_json=json)


@label_app.command
def delete(
    label: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
) -> None:
    """Delete a label.

    Parameters
    ----------
    label
        Label name or UUID.
    project
        Project name, identifier, or UUID.
    """
    from planecli.formatters import console

    try:
        client = get_client()
        workspace = get_workspace()
        proj = resolve_project(project, client, workspace)
        project_id = proj["id"]

        lbl_data = resolve_label(label, client, workspace, project_id)
        label_id = lbl_data["id"]
        label_name = lbl_data.get("name", label_id)

        client.labels.delete(workspace, project_id, label_id)
    except PlaneError as e:
        raise handle_api_error(e)

    console.print(f"[green]Label '{label_name}' deleted.[/]")
