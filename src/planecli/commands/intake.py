"""Intake queue commands.

Uses the Plane SDK ``client.intake`` resource (plane-sdk >= 0.2.6).

Plane API notes:
- ``accept``/``decline``/``delete`` take the *work item* UUID (the ``issue`` field of an
  intake item, shown as "Issue ID" by ``intake ls``), NOT the intake wrapper ``id``.
- ``status`` is an integer: -2 pending, -1 rejected, 0 snoozed, 1 accepted, 2 duplicate.
- Whether intake is enabled is decided by the API, not by a client-side gate: ``ls``
  returns an empty list whenever the project's intake view is off, and mutations return
  HTTP 400 only for a project that never had intake enabled.
- Triaging (``accept``/``decline``) requires the project **Admin** role: for lower roles
  the API answers HTTP 200 with the record unchanged, so the returned status is checked.
"""

from __future__ import annotations

import html
from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.async_sdk import paginate_all_async, run_sdk
from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.exceptions import APIError, ValidationError
from planecli.formatters import console, output, output_single
from planecli.utils.resolve import resolve_project_async

intake_app = cyclopts.App(
    name=["intake"],
    help="Manage project intake queues.",
)

INTAKE_STATUS_LABELS = {
    -2: "pending",
    -1: "rejected",
    0: "snoozed",
    1: "accepted",
    2: "duplicate",
}

INTAKE_PRIORITIES = ("none", "low", "medium", "high", "urgent")

INTAKE_COLUMNS = [
    ("name", "Name"),
    ("priority", "Priority"),
    ("status", "Status"),
    ("created_at", "Created"),
    ("issue_id", "Issue ID"),
]

INTAKE_FIELDS = [
    ("issue_id", "Issue ID"),
    ("id", "Intake ID"),
    ("name", "Name"),
    ("priority", "Priority"),
    ("status", "Status"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]

# Fields of the `enabled` command (project-level), not intake item statuses.
INTAKE_ENABLED_FIELDS = [
    ("project", "Project"),
    ("project_id", "Project ID"),
    ("intake_enabled", "Intake Enabled"),
]


def _normalize_priority(value: str) -> str:
    """Normalize and validate a priority. Raises ValidationError on invalid input."""
    key = value.strip().lower()
    if key not in INTAKE_PRIORITIES:
        allowed = ", ".join(INTAKE_PRIORITIES)
        raise ValidationError(
            f"Invalid priority '{value}'.",
            hint=f"Valid values: {allowed}.",
        )
    return key


def _enrich_intake(data: dict) -> dict:
    """Flatten an IntakeWorkItem dict for display: name/priority/issue_id + status label."""
    data = {**data}
    issue = data.get("issue_detail") or {}
    data["name"] = issue.get("name") or ""
    data["priority"] = issue.get("priority") or "none"
    data["issue_id"] = data.get("issue") or issue.get("id") or ""
    status = data.get("status")
    if status is None:
        data["status"] = ""
    else:
        data["status"] = INTAKE_STATUS_LABELS.get(status, str(status))
    return data


@intake_app.command(name="list", alias="ls")
async def list_(
    *,
    project: Annotated[str, Parameter(alias="-p")],
    json: bool = False,
) -> None:
    """List items in a project's intake queue.

    Parameters
    ----------
    project
        Project name, identifier, or UUID.
    """
    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
        project_id = proj["id"]

        items = await paginate_all_async(client.intake.list, workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    data = [_enrich_intake(item.model_dump()) for item in items]
    title = f"Intake Queue ({proj.get('identifier', '')})"
    output(data, INTAKE_COLUMNS, title=title, as_json=json)


@intake_app.command(alias="new")
async def create(
    name: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    priority: Annotated[str | None, Parameter(alias="-P")] = None,
    json: bool = False,
) -> None:
    """Create a new item in a project's intake queue.

    Parameters
    ----------
    name
        Item title.
    project
        Project name, identifier, or UUID.
    description
        Item description (plain text; wrapped in a paragraph tag and HTML-escaped).
    priority
        Priority: none, low, medium, high, urgent. Default: none.
    """
    from plane.models.intake import CreateIntakeWorkItem
    from plane.models.work_items import WorkItemForIntakeRequest

    try:
        normalized_priority = _normalize_priority(priority) if priority is not None else "none"

        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
        project_id = proj["id"]

        issue = WorkItemForIntakeRequest(name=name, priority=normalized_priority)
        if description:
            issue.description_html = f"<p>{html.escape(description)}</p>"

        item = await run_sdk(
            client.intake.create, workspace, project_id, CreateIntakeWorkItem(issue=issue)
        )
        data = _enrich_intake(item.model_dump())

        from planecli.cache import invalidate_resource

        await invalidate_resource("work_items", workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, INTAKE_FIELDS, title="Intake Item Created", as_json=json)


async def _set_status(issue_id: str, project: str, status: int, title: str, json: bool) -> None:
    """Shared body of accept/decline: PATCH the intake status of a work item."""
    from plane.models.intake import UpdateIntakeWorkItem

    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
        project_id = proj["id"]

        item = await run_sdk(
            client.intake.update,
            workspace,
            project_id,
            issue_id,
            UpdateIntakeWorkItem(status=status),
        )
        raw = item.model_dump()
        # The API answers HTTP 200 with the record untouched when the caller is not a
        # project Admin, so a 200 alone is not proof the triage happened.
        if raw.get("status") != status:
            current = INTAKE_STATUS_LABELS.get(raw.get("status"), raw.get("status"))
            raise APIError(
                f"the intake status was not changed (still '{current}'). "
                "Triaging intake items requires the project Admin role."
            )
        data = _enrich_intake(raw)

        from planecli.cache import invalidate_resource

        await invalidate_resource("work_items", workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, INTAKE_FIELDS, title=title, as_json=json)


@intake_app.command
async def accept(
    issue_id: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    json: bool = False,
) -> None:
    """Accept (triage) an intake item, converting it into a regular work item.

    Requires the project Admin role; other roles get an error instead of a silent no-op.

    Parameters
    ----------
    issue_id
        Work item UUID — the "Issue ID" column of `intake ls` (not the intake wrapper ID).
    project
        Project name, identifier, or UUID.
    """
    await _set_status(issue_id, project, 1, "Intake Item Accepted", json)


@intake_app.command
async def decline(
    issue_id: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
    json: bool = False,
) -> None:
    """Decline (reject) an intake item.

    Requires the project Admin role; other roles get an error instead of a silent no-op.

    Parameters
    ----------
    issue_id
        Work item UUID — the "Issue ID" column of `intake ls` (not the intake wrapper ID).
    project
        Project name, identifier, or UUID.
    """
    await _set_status(issue_id, project, -1, "Intake Item Declined", json)


@intake_app.command
async def delete(
    issue_id: str,
    *,
    project: Annotated[str, Parameter(alias="-p")],
) -> None:
    """Delete an intake item.

    For any status other than 'accepted' this also permanently deletes the underlying
    work item, not just the intake queue entry.

    Parameters
    ----------
    issue_id
        Work item UUID — the "Issue ID" column of `intake ls` (not the intake wrapper ID).
    project
        Project name, identifier, or UUID.
    """
    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
        project_id = proj["id"]

        await run_sdk(client.intake.delete, workspace, project_id, issue_id)

        from planecli.cache import invalidate_resource

        await invalidate_resource("work_items", workspace, project_id)
    except PlaneError as e:
        raise handle_api_error(e)

    console.print(f"[green]Intake item {issue_id} deleted.[/]")


@intake_app.command
async def enabled(
    project: str,
    *,
    json: bool = False,
) -> None:
    """Check whether a project has intake enabled.

    Parameters
    ----------
    project
        Project name, identifier, or UUID.
    """
    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    is_enabled = bool(proj.get("intake_view"))
    data = {
        "project": proj.get("name", project),
        "project_id": proj["id"],
        "intake_enabled": is_enabled,
    }
    if json:
        output_single(data, INTAKE_ENABLED_FIELDS, title="Intake Status", as_json=True)
    elif is_enabled:
        console.print(f"[green]Intake is enabled[/] for {data['project']} (ID: {proj['id']})")
    else:
        console.print(f"[yellow]Intake is NOT enabled[/] for {data['project']} (ID: {proj['id']})")
