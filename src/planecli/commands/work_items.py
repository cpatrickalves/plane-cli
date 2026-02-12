"""Work item / issue CRUD commands."""

from __future__ import annotations

import asyncio
from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError
from rich.text import Text

from planecli.api.async_sdk import create_client, paginate_all_async, run_sdk
from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.formatters import output, output_single
from planecli.utils.colors import PRIORITY_COLORS, colorize, lighten_hex
from planecli.utils.resolve import (
    resolve_label_async,
    resolve_module_async,
    resolve_project_async,
    resolve_state_async,
    resolve_user_async,
    resolve_work_item_across_projects_async,
    resolve_work_item_async,
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
    state_map: dict[str, dict[str, str | None]] | None = None,
    member_map: dict[str, str] | None = None,
    label_map: dict[str, dict[str, str | None]] | None = None,
    project_identifier: str | None = None,
) -> dict:
    """Add convenience fields to a work item dict.

    Args:
        data: Work item dict from model_dump().
        state_map: Optional UUID->{"name": str, "color": str|None} mapping for states.
        member_map: Optional UUID->display_name mapping for workspace members.
        label_map: Optional UUID->{"name": str, "color": str|None} mapping for labels.
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

    # Priority - colorize with hardcoded color map; keep blank when unset
    priority_val = data.get("priority") or ""
    if priority_val and priority_val != "none" and isinstance(priority_val, str):
        data["priority"] = colorize(priority_val, PRIORITY_COLORS.get(priority_val))
    else:
        data["priority"] = ""

    # State name - try expanded object first, then lookup map, then raw value
    # Lighten "unstarted" group colors (e.g. Todo) to distinguish from "backlog"
    state_detail = data.get("state_detail") or data.get("state")
    if isinstance(state_detail, dict):
        state_name = state_detail.get("name", "")
        state_color = state_detail.get("color")
        if state_color and state_detail.get("group") == "unstarted":
            state_color = lighten_hex(state_color)
        data["state_detail_name"] = colorize(state_name, state_color)
    elif isinstance(state_detail, str) and state_map and state_detail in state_map:
        info = state_map[state_detail]
        state_color = info.get("color")
        if state_color and info.get("group") == "unstarted":
            state_color = lighten_hex(state_color)
        data["state_detail_name"] = colorize(info["name"] or "", state_color)
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

    # Label names - try expanded objects first, then lookup map (with per-label colors)
    labels = data.get("labels") or data.get("label_detail") or []
    if isinstance(labels, list):
        label_parts: list[str | Text] = []
        for lbl in labels:
            if isinstance(lbl, dict):
                label_parts.append(
                    colorize(lbl.get("name", ""), lbl.get("color"))
                )
            elif isinstance(lbl, str) and label_map and lbl in label_map:
                info = label_map[lbl]
                label_parts.append(
                    colorize(info["name"] or "", info.get("color"))
                )
            elif isinstance(lbl, str):
                label_parts.append(lbl)
        if label_parts:
            combined = Text()
            for i, part in enumerate(label_parts):
                if i > 0:
                    combined.append(", ")
                if isinstance(part, Text):
                    combined.append_text(part)
                else:
                    combined.append(str(part))
            data["label_names"] = combined
            data["label_detail_names"] = [str(part) for part in label_parts]
        else:
            data["label_names"] = ""
            data["label_detail_names"] = []
    else:
        data["label_names"] = ""
        data["label_detail_names"] = []

    # Description stripped
    desc_html = data.get("description_html") or ""
    if desc_html:
        import re

        data["description_stripped"] = re.sub(r"<[^>]+>", "", desc_html).strip()

    return data


async def _resolve_project_id_async(project: str | None) -> str:
    """Resolve project flag to a project UUID (async)."""
    from planecli.exceptions import ValidationError

    if not project:
        raise ValidationError(
            "Project is required for this command.",
            hint="Use --project <name-or-id> to specify the project.",
        )
    client = get_client()
    workspace = get_workspace()
    resolved = await resolve_project_async(project, client, workspace)
    return resolved["id"]


async def _fetch_project_data(
    client, workspace: str, project_id: str
) -> tuple[list, list[dict], list[dict]]:
    """Fetch work items, states, and labels for a project in parallel.

    Work items are fetched fresh (not cached). States and labels use the cache.
    """
    from planecli.cache import cached_list_labels, cached_list_states

    items, states, labels = await asyncio.gather(
        paginate_all_async(client.work_items.list, workspace, project_id),
        cached_list_states(workspace, project_id),
        cached_list_labels(workspace, project_id),
    )
    return items, states, labels


@wi_app.command(name="list", alias="ls")
async def list_(
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
        Filter by state name (comma-separated).
    labels
        Filter by label name (comma-separated).
    sort
        Sort by: created (default), updated.
    limit
        Maximum results to show.
    """
    try:
        client = get_client()
        workspace = get_workspace()

        # Workspace-scoped: fetch members once (cached)
        from planecli.cache import cached_list_members, cached_list_projects

        members = await cached_list_members(workspace)
        member_map = {}
        for m in members:
            if not m.get("id"):
                continue
            full_name = " ".join(
                p for p in [m.get("first_name", ""), m.get("last_name", "")]
                if p
            )
            member_map[m["id"]] = full_name or m.get("display_name", "")

        if project:
            proj = await resolve_project_async(project, client, workspace)
            projects_to_list = [proj]
        else:
            projects_to_list = await cached_list_projects(workspace)

        # Fetch all projects in parallel (each project fetches items+states+labels in parallel)
        data = []
        if projects_to_list:
            # Use fresh client instances for parallel project fetching
            async def _fetch_and_enrich(proj_dict: dict) -> list[dict]:
                proj_client = create_client()
                project_id = proj_dict["id"]
                proj_identifier = proj_dict.get("identifier", "")

                try:
                    items, states, labels_list = await _fetch_project_data(
                        proj_client, workspace, project_id
                    )
                except Exception:
                    return []

                if not items:
                    return []

                # states and labels are already dicts (from cache)
                state_map = {
                    s["id"]: {
                        "name": s.get("name"),
                        "color": s.get("color"),
                        "group": s.get("group"),
                    }
                    for s in states if s.get("id") and s.get("name")
                }
                label_map = {
                    lb["id"]: {"name": lb.get("name"), "color": lb.get("color")}
                    for lb in labels_list if lb.get("id") and lb.get("name")
                }

                enriched_items = []
                for i in items:
                    enriched = _enrich_work_item(
                        i.model_dump(),
                        state_map=state_map,
                        member_map=member_map,
                        label_map=label_map,
                        project_identifier=proj_identifier,
                    )
                    enriched["project_identifier"] = proj_identifier
                    enriched_items.append(enriched)
                return enriched_items

            results = await asyncio.gather(
                *[_fetch_and_enrich(p) for p in projects_to_list],
                return_exceptions=True,
            )

            from planecli.formatters import console

            for proj_dict, result in zip(projects_to_list, results):
                if isinstance(result, Exception):
                    console.print(
                        f"[yellow]Warning: Failed to fetch "
                        f"{proj_dict.get('identifier', proj_dict['id'])}: {result}[/]"
                    )
                    continue
                data.extend(result)
    except PlaneError as e:
        raise handle_api_error(e)

    # Filter by assignee
    if assignee:
        user = await resolve_user_async(assignee, client, workspace)
        user_id = user["id"]
        data = [
            d for d in data
            if user_id in (d.get("assignees") or [])
            or any(
                (isinstance(a, dict) and a.get("id") == user_id)
                for a in (d.get("assignees") or [])
            )
        ]

    # Filter by state (comma-separated, OR logic, substring match)
    if state:
        state_tokens = [s.strip().lower() for s in state.split(",") if s.strip()]
        if state_tokens:
            data = [
                d for d in data
                if any(
                    token in str(d.get("state_detail_name") or "").lower()
                    for token in state_tokens
                )
            ]

    # Filter by labels (comma-separated, OR logic, substring match)
    if labels:
        label_tokens = [ln.strip().lower() for ln in labels.split(",") if ln.strip()]
        if label_tokens:
            data = [
                d for d in data
                if any(
                    token in name.lower()
                    for token in label_tokens
                    for name in (d.get("label_detail_names") or [])
                )
            ]

    # Sort
    if sort == "updated":
        data.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    else:
        data.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    data = data[:limit]
    columns = WI_COLUMNS if project else WI_COLUMNS_ALL
    output(data, columns, title="Work Items", as_json=json)


@wi_app.command(alias="read")
async def show(
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
            project_id = await _resolve_project_id_async(project)
            data = await resolve_work_item_async(issue, client, workspace, project_id)
        else:
            data, _ = await resolve_work_item_across_projects_async(
                issue, client, workspace
            )
    except PlaneError as e:
        raise handle_api_error(e)

    data = _enrich_work_item(data)
    output_single(data, WI_FIELDS, title="Work Item Details", as_json=json)


@wi_app.command(alias="new")
async def create(
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

        # Resolve project and assignee in parallel (independent)
        parallel_tasks = [_resolve_project_id_async(project)]
        if assignee:
            parallel_tasks.append(resolve_user_async(assignee, client, workspace))
        if parent:
            parallel_tasks.append(
                resolve_work_item_across_projects_async(parent, client, workspace)
            )

        parallel_results = await asyncio.gather(*parallel_tasks)

        project_id = parallel_results[0]
        idx = 1

        create_data = CreateWorkItem(name=title)

        if description:
            create_data.description_html = f"<p>{description}</p>"

        if priority:
            priority_map = {"0": "none", "1": "urgent", "2": "high", "3": "medium", "4": "low"}
            create_data.priority = priority_map.get(priority, priority.lower())

        if estimate is not None:
            create_data.estimate_point = estimate

        if assignee:
            user = parallel_results[idx]
            create_data.assignees = [user["id"]]
            idx += 1

        if parent:
            parent_data, _ = parallel_results[idx]
            create_data.parent = parent_data["id"]
            idx += 1

        # Resolve state and labels (depend on project_id) in parallel
        dependent_tasks = []
        if state:
            dependent_tasks.append(
                resolve_state_async(state, client, workspace, project_id)
            )
        if labels:
            label_names = [ln.strip() for ln in labels.split(",") if ln.strip()]
            dependent_tasks.extend(
                resolve_label_async(ln, client, workspace, project_id)
                for ln in label_names
            )

        if dependent_tasks:
            dep_results = await asyncio.gather(*dependent_tasks)
            dep_idx = 0
            if state:
                state_data = dep_results[dep_idx]
                create_data.state = state_data["id"]
                dep_idx += 1
            if labels:
                label_ids = [dep_results[i]["id"] for i in range(dep_idx, len(dep_results))]
                if label_ids:
                    create_data.labels = label_ids

        item = await run_sdk(client.work_items.create, workspace, project_id, create_data)
        data = _enrich_work_item(item.model_dump())

        # Add to module if specified
        if module:
            module_data = await resolve_module_async(module, client, workspace, project_id)
            await run_sdk(
                client.modules.add_work_items,
                workspace, project_id, module_data["id"], [data["id"]],
            )

    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, WI_FIELDS, title="Work Item Created", as_json=json)


@wi_app.command
async def update(
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
            project_id = await _resolve_project_id_async(project)
            item_data = await resolve_work_item_async(issue, client, workspace, project_id)
        else:
            item_data, project_id = await resolve_work_item_across_projects_async(
                issue, client, workspace
            )

        item_id = item_data["id"]
        update_data = UpdateWorkItem()

        if name:
            update_data.name = name

        if description:
            update_data.description_html = f"<p>{description}</p>"

        if priority:
            priority_map = {"0": "none", "1": "urgent", "2": "high", "3": "medium", "4": "low"}
            update_data.priority = priority_map.get(priority, priority.lower())

        # Resolve assignee, state, and labels in parallel
        parallel_tasks = []
        task_keys = []

        if assignee:
            parallel_tasks.append(resolve_user_async(assignee, client, workspace))
            task_keys.append("assignee")
        if state:
            parallel_tasks.append(
                resolve_state_async(state, client, workspace, project_id)
            )
            task_keys.append("state")
        if labels and not clear_labels:
            label_names = [ln.strip() for ln in labels.split(",") if ln.strip()]
            for ln in label_names:
                parallel_tasks.append(
                    resolve_label_async(ln, client, workspace, project_id)
                )
                task_keys.append("label")

        if parallel_tasks:
            results = await asyncio.gather(*parallel_tasks)
            result_idx = 0
            for key in task_keys:
                if key == "assignee":
                    update_data.assignees = [results[result_idx]["id"]]
                elif key == "state":
                    update_data.state = results[result_idx]["id"]
                elif key == "label":
                    pass  # handled below
                result_idx += 1
            # Collect label IDs
            if labels and not clear_labels:
                label_ids = [
                    results[i]["id"]
                    for i, k in enumerate(task_keys)
                    if k == "label"
                ]
                update_data.labels = label_ids

        if clear_labels:
            update_data.labels = []

        updated = await run_sdk(
            client.work_items.update, workspace, project_id, item_id, update_data
        )
        data = _enrich_work_item(updated.model_dump())
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, WI_FIELDS, title="Work Item Updated", as_json=json)


@wi_app.command
async def delete(
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
            project_id = await _resolve_project_id_async(project)
            item_data = await resolve_work_item_async(issue, client, workspace, project_id)
        else:
            item_data, project_id = await resolve_work_item_across_projects_async(
                issue, client, workspace
            )

        item_id = item_data["id"]
        item_name = item_data.get("name", item_id)

        await run_sdk(client.work_items.delete, workspace, project_id, item_id)
    except PlaneError as e:
        raise handle_api_error(e)

    console.print(f"[green]Work item '{item_name}' deleted.[/]")


@wi_app.command
async def search(
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

        result = await run_sdk(client.work_items.search, workspace, query)
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
async def assign(
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
            project_id = await _resolve_project_id_async(project)
            item_data = await resolve_work_item_async(issue, client, workspace, project_id)
        else:
            item_data, project_id = await resolve_work_item_across_projects_async(
                issue, client, workspace
            )

        item_id = item_data["id"]
        user = await resolve_user_async(assignee, client, workspace)

        update_data = UpdateWorkItem(assignees=[user["id"]])
        await run_sdk(
            client.work_items.update, workspace, project_id, item_id, update_data
        )
    except PlaneError as e:
        raise handle_api_error(e)

    user_name = user.get("display_name") or user.get("first_name", "user")
    console.print(f"[green]Work item assigned to {user_name}.[/]")
