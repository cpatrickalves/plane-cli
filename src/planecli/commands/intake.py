"""Intake queue commands.

The Plane SDK does not expose intake endpoints, so these commands use direct HTTP
calls (same approach as documents.py).
"""

from __future__ import annotations

from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.client import get_client, get_config, get_workspace, handle_api_error
from planecli.formatters import console, output, output_single
from planecli.utils.resolve import resolve_project_async

intake_app = cyclopts.App(
    name=["intake"],
    help="Manage project intake queues.",
)

INTAKE_COLUMNS = [
    ("name", "Name"),
    ("priority", "Priority"),
    ("status_description", "Status"),
    ("created_at", "Created"),
    ("id", "Intake ID"),
]

INTAKE_FIELDS = [
    ("id", "Intake ID"),
    ("issue_id", "Issue ID"),
    ("name", "Name"),
    ("priority", "Priority"),
    ("status_description", "Status"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]


def _enrich_intake(data: dict) -> dict:
    """Flatten issue_detail fields for display."""
    issue = data.get("issue_detail") or {}
    data["name"] = issue.get("name", "")
    data["priority"] = issue.get("priority", "none")
    data["issue_id"] = issue.get("id", "")
    return data


def _intake_url(config, workspace: str, project_id: str) -> str:
    """Build the intake-issues API URL for a project."""
    return (
        f"{config.base_url}/api/v1/workspaces/{workspace}"
        f"/projects/{project_id}/intake-issues/"
    )


def _headers(config) -> dict:
    """Build auth headers for direct API calls."""
    return {"X-Api-Key": config.api_key}


@intake_app.command(name="list", alias="ls")
async def list_(
    *,
    project: Annotated[str, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """List items in a project's intake queue.

    Parameters
    ----------
    project
        Project name, identifier, or UUID. Required.
    """
    import requests

    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    if not proj.get("intake_view"):
        console.print(
            f"[yellow]Project '{proj.get('name', project)}' does not have intake enabled.[/]"
        )
        return

    config = get_config()
    url = _intake_url(config, workspace, proj["id"])
    resp = requests.get(url, headers=_headers(config), timeout=30)
    resp.raise_for_status()
    body = resp.json()

    results = [_enrich_intake(item) for item in body.get("results", [])]
    output(results, INTAKE_COLUMNS, title=f"Intake Queue ({proj.get('identifier', '')})", as_json=json)


@intake_app.command(alias="new")
async def create(
    name: str,
    *,
    project: Annotated[str, Parameter(alias="-p")] = None,
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    priority: Annotated[str | None, Parameter(alias="-P")] = None,
    json: bool = False,
) -> None:
    """Create a new intake item in a project's intake queue.

    Parameters
    ----------
    name
        Item title (required).
    project
        Project name, identifier, or UUID. Required.
    description
        Item description. Automatically wrapped in <p> for HTML.
    priority
        Priority: none, low, medium, high, urgent. Default: none.
    """
    import requests

    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    if not proj.get("intake_view"):
        from planecli.exceptions import ValidationError
        raise ValidationError(
            f"Project '{proj.get('name', project)}' does not have intake enabled."
        )

    issue = {"name": name, "priority": priority or "none"}
    if description:
        issue["description_html"] = f"<p>{description}</p>"

    config = get_config()
    url = _intake_url(config, workspace, proj["id"])
    resp = requests.post(url, headers=_headers(config), json={"issue": issue}, timeout=30)
    resp.raise_for_status()
    body = resp.json()

    data = _enrich_intake(body)
    output_single(data, INTAKE_FIELDS, title="Intake Item Created", as_json=json)


@intake_app.command
async def accept(
    intake_id: str,
    *,
    project: Annotated[str, Parameter(alias="-p")] = None,
) -> None:
    """Accept (triage) an intake item, converting it to a regular work item.

    Parameters
    ----------
    intake_id
        Intake item ID (UUID). The issue_detail UUID also works.
    project
        Project name, identifier, or UUID. Required.
    """
    import requests

    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    config = get_config()
    url = (
        f"{config.base_url}/api/v1/workspaces/{workspace}"
        f"/projects/{proj['id']}/intake-issues/{intake_id}/"
    )
    resp = requests.patch(
        url, headers=_headers(config), json={"status": 1}, timeout=30
    )
    resp.raise_for_status()
    console.print(f"[green]Intake item {intake_id} accepted.[/]")


@intake_app.command
async def decline(
    intake_id: str,
    *,
    project: Annotated[str, Parameter(alias="-p")] = None,
) -> None:
    """Decline an intake item.

    Parameters
    ----------
    intake_id
        Intake item ID (UUID). The issue_detail UUID also works.
    project
        Project name, identifier, or UUID. Required.
    """
    import requests

    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    config = get_config()
    url = (
        f"{config.base_url}/api/v1/workspaces/{workspace}"
        f"/projects/{proj['id']}/intake-issues/{intake_id}/"
    )
    resp = requests.patch(
        url, headers=_headers(config), json={"status": -1}, timeout=30
    )
    resp.raise_for_status()
    console.print(f"[green]Intake item {intake_id} declined.[/]")


@intake_app.command
async def delete(intake_id: str, *, project: Annotated[str, Parameter(alias="-p")] = None) -> None:
    """Delete an intake item.

    Parameters
    ----------
    intake_id
        The issue_detail UUID (the actual issue ID, not the intake wrapper ID).
    project
        Project name, identifier, or UUID. Required.
    """
    import requests

    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    config = get_config()
    url = (
        f"{config.base_url}/api/v1/workspaces/{workspace}"
        f"/projects/{proj['id']}/intake-issues/{intake_id}/"
    )
    resp = requests.delete(url, headers=_headers(config), timeout=30)
    resp.raise_for_status()
    console.print(f"[green]Intake item {intake_id} deleted.[/]")


@intake_app.command
async def enabled(
    project: str,
    *,
    json: bool = False,
) -> None:
    """Check if a project has intake enabled.

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

    intake_view = proj.get("intake_view", False)
    if json:
        import sys
        sys.stdout.write(f'{{"intake_enabled": {str(intake_view).lower()}, "project_id": "{proj["id"]}"}}\n')
    elif intake_view:
        console.print(f"[green]Intake is enabled[/] for {proj.get('name', project)} (ID: {proj['id']})")
    else:
        console.print(
            f"[yellow]Intake is NOT enabled[/] for {proj.get('name', project)} (ID: {proj['id']})"
        )
