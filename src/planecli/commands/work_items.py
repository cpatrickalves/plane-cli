"""Work item / issue CRUD commands."""

from __future__ import annotations

from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.formatters import output, output_single
from planecli.utils.resolve import (
    resolve_label,
    resolve_module,
    resolve_project,
    resolve_state,
    resolve_user,
    resolve_work_item,
    resolve_work_item_across_projects,
)

wi_app = cyclopts.App(
    name=["work-item", "wi", "issues", "issue"],
    help="Manage work items (issues).",
)

WI_COLUMNS = [
    ("sequence_id", "ID"),
    ("name", "Title"),
    ("priority", "Priority"),
    ("state_detail_name", "State"),
    ("assignee_names", "Assignees"),
    ("created_at", "Created"),
]

WI_COLUMNS_ALL = [
    ("project_identifier", "Project"),
    ("sequence_id", "ID"),
    ("name", "Title"),
    ("priority", "Priority"),
    ("state_detail_name", "State"),
    ("assignee_names", "Assignees"),
    ("created_at", "Created"),
]

WI_FIELDS = [
    ("id", "UUID"),
    ("sequence_id", "Sequence ID"),
    ("name", "Title"),
    ("description_stripped", "Description"),
    ("priority", "Priority"),
    ("state_detail_name", "State"),
    ("assignee_names", "Assignees"),
    ("label_names", "Labels"),
    ("start_date", "Start Date"),
    ("target_date", "Target Date"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]


def _enrich_work_item(
    data: dict,
    *,
    state_map: dict[str, str] | None = None,
    member_map: dict[str, str] | None = None,
    label_map: dict[str, str] | None = None,
    project_identifier: str | None = None,
) -> dict:
    """Add convenience fields to a work item dict.

    Args:
        data: Work item dict from model_dump().
        state_map: Optional UUID->name mapping for states.
        member_map: Optional UUID->display_name mapping for workspace members.
        label_map: Optional UUID->name mapping for labels.
        project_identifier: Optional project identifier (e.g. "CHATFIN") for sequence IDs.
    """
    # Add sequence_id like CHATFIN-30
    if not project_identifier:
        project_detail = data.get("project_detail")
        project_identifier = (
            project_detail.get("identifier", "")
            if isinstance(project_detail, dict)
            else ""
        )
    seq = data.get("sequence_id", "")
    if project_identifier and seq:
        data["sequence_id"] = f"{project_identifier}-{seq}"

    # State name - try expanded object first, then lookup map, then raw value
    state_detail = data.get("state_detail") or data.get("state")
    if isinstance(state_detail, dict):
        data["state_detail_name"] = state_detail.get("name", "")
    elif isinstance(state_detail, str) and state_map and state_detail in state_map:
        data["state_detail_name"] = state_map[state_detail]
    elif isinstance(state_detail, str):
        data["state_detail_name"] = state_detail
    else:
        data["state_detail_name"] = ""

    # Assignee names - try expanded objects first, then lookup map
    assignees = data.get("assignees") or data.get("assignee_detail") or []
    if isinstance(assignees, list):
        names = []
        for a in assignees:
            if isinstance(a, dict):
                names.append(a.get("display_name") or a.get("first_name", ""))
            elif isinstance(a, str) and member_map and a in member_map:
                names.append(member_map[a])
            elif isinstance(a, str):
                names.append(a[:8])  # Show truncated UUID as fallback
        data["assignee_names"] = ", ".join(names) if names else ""
    else:
        data["assignee_names"] = ""

    # Label names - try expanded objects first, then lookup map
    labels = data.get("labels") or data.get("label_detail") or []
    if isinstance(labels, list):
        label_names = []
        for lbl in labels:
            if isinstance(lbl, dict):
                label_names.append(lbl.get("name", ""))
            elif isinstance(lbl, str) and label_map and lbl in label_map:
                label_names.append(label_map[lbl])
            elif isinstance(lbl, str):
                label_names.append(lbl)
        data["label_names"] = ", ".join(label_names) if label_names else ""
    else:
        data["label_names"] = ""

    # Description stripped
    desc_html = data.get("description_html") or ""
    if desc_html:
        import re

        data["description_stripped"] = re.sub(r"<[^>]+>", "", desc_html).strip()

    return data


def _resolve_project_id(project: str | None) -> str:
    """Resolve project flag to a project UUID."""
    from planecli.exceptions import ValidationError

    if not project:
        raise ValidationError(
            "Project is required for this command.",
            hint="Use --project <name-or-id> to specify the project.",
        )
    client = get_client()
    workspace = get_workspace()
    resolved = resolve_project(project, client, workspace)
    return resolved["id"]


@wi_app.command(name="list", alias="ls")
def list_(
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    assignee: str | None = None,
    state: str | None = None,
    labels: str | None = None,
    sort: str = "created",
    limit: Annotated[int, Parameter(alias="-l")] = 50,
    json: bool = False,
) -> None:
    """List work items.

    Parameters
    ----------
    project
        Project name, identifier, or UUID. If omitted, lists from all projects.
    assignee
        Filter by assignee name or 'me'.
    state
        Filter by state name.
    labels
        Filter by labels (comma-separated).
    sort
        Sort by: created (default), updated.
    limit
        Maximum results to show.
    """
    from planecli.utils.resolve import _paginate_all

    try:
        client = get_client()
        workspace = get_workspace()

        # Workspace-scoped: fetch members once
        members = client.workspaces.get_members(workspace)
        member_map = {}
        for m in members:
            if not m.id:
                continue
            full_name = " ".join(
                p for p in [getattr(m, "first_name", ""), getattr(m, "last_name", "")]
                if p
            )
            member_map[m.id] = full_name or m.display_name or ""

        if project:
            # Single project path (existing behavior)
            proj = resolve_project(project, client, workspace)
            projects_to_list = [proj]
        else:
            # All projects path
            all_projects = _paginate_all(client.projects.list, workspace)
            projects_to_list = [p.model_dump() for p in all_projects]

        data = []
        for proj in projects_to_list:
            project_id = proj["id"]
            proj_identifier = proj.get("identifier", "")

            items = _paginate_all(client.work_items.list, workspace, project_id)
            if not items:
                continue

            # Per-project lookup maps
            states = _paginate_all(client.states.list, workspace, project_id)
            state_map = {s.id: s.name for s in states if s.id and s.name}
            labels_list = _paginate_all(client.labels.list, workspace, project_id)
            label_map = {lb.id: lb.name for lb in labels_list if lb.id and lb.name}

            for i in items:
                enriched = _enrich_work_item(
                    i.model_dump(),
                    state_map=state_map,
                    member_map=member_map,
                    label_map=label_map,
                    project_identifier=proj_identifier,
                )
                enriched["project_identifier"] = proj_identifier
                data.append(enriched)
    except PlaneError as e:
        raise handle_api_error(e)

    # Filter by assignee
    if assignee:
        try:
            user = resolve_user(assignee, client, workspace)
            user_id = user["id"]
            data = [
                d for d in data
                if user_id in (d.get("assignees") or [])
                or any(
                    (isinstance(a, dict) and a.get("id") == user_id)
                    for a in (d.get("assignees") or [])
                )
            ]
        except Exception:
            pass

    # Filter by state
    if state:
        state_lower = state.lower()
        data = [d for d in data if state_lower in (d.get("state_detail_name") or "").lower()]

    # Sort
    if sort == "updated":
        data.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    else:
        data.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    data = data[:limit]
    columns = WI_COLUMNS if project else WI_COLUMNS_ALL
    output(data, columns, title="Work Items", as_json=json)


@wi_app.command(alias="read")
def show(
    issue: str,
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """Show work item details.

    Parameters
    ----------
    issue
        Work item identifier (ABC-123), UUID, or name.
    project
        Project name/ID (required for name-based lookup).
    """
    try:
        client = get_client()
        workspace = get_workspace()

        if project:
            project_id = _resolve_project_id(project)
            data = resolve_work_item(issue, client, workspace, project_id)
        else:
            data, _ = resolve_work_item_across_projects(issue, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    data = _enrich_work_item(data)
    output_single(data, WI_FIELDS, title="Work Item Details", as_json=json)


@wi_app.command(alias="new")
def create(
    title: str,
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    assignee: Annotated[str | None, Parameter(name=["--assignee", "--assign"])] = None,
    state: str | None = None,
    labels: str | None = None,
    priority: Annotated[str | None, Parameter()] = None,
    module: str | None = None,
    parent: str | None = None,
    estimate: Annotated[int | None, Parameter(alias="-e")] = None,
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    json: bool = False,
) -> None:
    """Create a new work item.

    Parameters
    ----------
    title
        Work item title.
    project
        Project name, identifier, or UUID (required).
    assignee
        Assignee name, email, or 'me'.
    state
        State name (e.g. 'Todo', 'In Progress').
    labels
        Comma-separated label names.
    priority
        Priority: urgent, high, medium, low, none. Also accepts 0-4 (0=none, 1=urgent).
    module
        Module name or UUID to add the item to.
    parent
        Parent work item identifier (ABC-123) for creating sub-issues.
    estimate
        Story point estimate.
    description
        Work item description (plain text).
    """
    from plane.models.work_items import CreateWorkItem

    try:
        client = get_client()
        workspace = get_workspace()
        project_id = _resolve_project_id(project)

        create_data = CreateWorkItem(name=title)

        if description:
            create_data.description_html = f"<p>{description}</p>"

        if priority:
            priority_map = {"0": "none", "1": "urgent", "2": "high", "3": "medium", "4": "low"}
            create_data.priority = priority_map.get(priority, priority.lower())

        if estimate is not None:
            create_data.estimate_point = estimate

        # Resolve assignee
        if assignee:
            user = resolve_user(assignee, client, workspace)
            create_data.assignees = [user["id"]]

        # Resolve state
        if state:
            state_data = resolve_state(state, client, workspace, project_id)
            create_data.state = state_data["id"]

        # Resolve labels
        if labels:
            label_ids = []
            for label_name in labels.split(","):
                label_name = label_name.strip()
                if label_name:
                    label_data = resolve_label(label_name, client, workspace, project_id)
                    label_ids.append(label_data["id"])
            if label_ids:
                create_data.labels = label_ids

        # Resolve parent
        if parent:
            parent_data, _ = resolve_work_item_across_projects(parent, client, workspace)
            create_data.parent = parent_data["id"]

        item = client.work_items.create(workspace, project_id, create_data)
        data = _enrich_work_item(item.model_dump())

        # Add to module if specified
        if module:
            module_data = resolve_module(module, client, workspace, project_id)
            client.modules.add_work_items(workspace, project_id, module_data["id"], [data["id"]])

    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, WI_FIELDS, title="Work Item Created", as_json=json)


@wi_app.command
def update(
    issue: str,
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    state: str | None = None,
    priority: str | None = None,
    assignee: Annotated[str | None, Parameter(name=["--assignee", "--assign"])] = None,
    labels: str | None = None,
    clear_labels: bool = False,
    name: str | None = None,
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    json: bool = False,
) -> None:
    """Update a work item.

    Parameters
    ----------
    issue
        Work item identifier (ABC-123), UUID, or name.
    project
        Project name/ID (required for name-based lookup).
    state
        New state name.
    priority
        New priority: urgent, high, medium, low, none.
    assignee
        New assignee name or 'me'.
    labels
        Comma-separated labels to set.
    clear_labels
        Remove all labels.
    name
        New title.
    description
        New description (plain text).
    """
    from plane.models.work_items import UpdateWorkItem

    try:
        client = get_client()
        workspace = get_workspace()

        # Resolve the work item
        if project:
            project_id = _resolve_project_id(project)
            item_data = resolve_work_item(issue, client, workspace, project_id)
        else:
            item_data, project_id = resolve_work_item_across_projects(issue, client, workspace)

        item_id = item_data["id"]
        update_data = UpdateWorkItem()

        if name:
            update_data.name = name

        if description:
            update_data.description_html = f"<p>{description}</p>"

        if priority:
            priority_map = {"0": "none", "1": "urgent", "2": "high", "3": "medium", "4": "low"}
            update_data.priority = priority_map.get(priority, priority.lower())

        if assignee:
            user = resolve_user(assignee, client, workspace)
            update_data.assignees = [user["id"]]

        if state:
            state_data = resolve_state(state, client, workspace, project_id)
            update_data.state = state_data["id"]

        if clear_labels:
            update_data.labels = []
        elif labels:
            label_ids = []
            for label_name in labels.split(","):
                label_name = label_name.strip()
                if label_name:
                    label_data = resolve_label(label_name, client, workspace, project_id)
                    label_ids.append(label_data["id"])
            update_data.labels = label_ids

        updated = client.work_items.update(workspace, project_id, item_id, update_data)
        data = _enrich_work_item(updated.model_dump())
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, WI_FIELDS, title="Work Item Updated", as_json=json)


@wi_app.command
def delete(
    issue: str,
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
) -> None:
    """Delete a work item.

    Parameters
    ----------
    issue
        Work item identifier (ABC-123), UUID, or name.
    project
        Project name/ID (required for name-based lookup).
    """
    from planecli.formatters import console

    try:
        client = get_client()
        workspace = get_workspace()

        if project:
            project_id = _resolve_project_id(project)
            item_data = resolve_work_item(issue, client, workspace, project_id)
        else:
            item_data, project_id = resolve_work_item_across_projects(issue, client, workspace)

        item_id = item_data["id"]
        item_name = item_data.get("name", item_id)

        client.work_items.delete(workspace, project_id, item_id)
    except PlaneError as e:
        raise handle_api_error(e)

    console.print(f"[green]Work item '{item_name}' deleted.[/]")


@wi_app.command
def search(
    query: str,
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    sort: str = "created",
    limit: Annotated[int, Parameter(alias="-l")] = 20,
    json: bool = False,
) -> None:
    """Search work items by text.

    Parameters
    ----------
    query
        Search query string.
    project
        Limit search to a specific project.
    sort
        Sort by: created (default), updated.
    limit
        Maximum results to show.
    """
    try:
        client = get_client()
        workspace = get_workspace()

        result = client.work_items.search(workspace, query)
        results_data = result.model_dump() if hasattr(result, "model_dump") else result

        # Extract work items from search results
        items = []
        if isinstance(results_data, dict):
            items = results_data.get("results", [])
        elif isinstance(results_data, list):
            items = results_data

        data = [_enrich_work_item(i if isinstance(i, dict) else i.model_dump()) for i in items]
    except PlaneError as e:
        raise handle_api_error(e)

    data = data[:limit]
    output(data, WI_COLUMNS, title=f"Search Results: '{query}'", as_json=json)


@wi_app.command
def assign(
    issue: str,
    *,
    assignee: Annotated[str, Parameter(name=["--assignee", "--assign"])] = "me",
    project: Annotated[str | None, Parameter(alias="-p")] = None,
) -> None:
    """Assign a work item (defaults to yourself).

    Parameters
    ----------
    issue
        Work item identifier (ABC-123), UUID, or name.
    assignee
        Assignee name, email, or 'me' (default).
    project
        Project name/ID (required for name-based lookup).
    """
    from plane.models.work_items import UpdateWorkItem

    from planecli.formatters import console

    try:
        client = get_client()
        workspace = get_workspace()

        if project:
            project_id = _resolve_project_id(project)
            item_data = resolve_work_item(issue, client, workspace, project_id)
        else:
            item_data, project_id = resolve_work_item_across_projects(issue, client, workspace)

        item_id = item_data["id"]
        user = resolve_user(assignee, client, workspace)

        update_data = UpdateWorkItem(assignees=[user["id"]])
        client.work_items.update(workspace, project_id, item_id, update_data)
    except PlaneError as e:
        raise handle_api_error(e)

    user_name = user.get("display_name") or user.get("first_name", "user")
    console.print(f"[green]Work item assigned to {user_name}.[/]")
