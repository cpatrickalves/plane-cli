"""Comment commands for work items."""

from __future__ import annotations

from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.async_sdk import run_sdk
from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.formatters import output, output_single
from planecli.utils.resolve import (
    resolve_work_item_across_projects_async,
    resolve_work_item_async,
)

comment_app = cyclopts.App(
    name=["comment", "comments"],
    help="Manage work item comments.",
)

COMMENT_COLUMNS = [
    ("id", "ID"),
    ("actor_name", "Author"),
    ("body_text", "Comment"),
    ("created_at", "Created"),
]


def _enrich_comment(data: dict) -> dict:
    """Add convenience fields to a comment dict."""
    # Extract actor name
    actor = data.get("actor_detail") or data.get("actor") or {}
    if isinstance(actor, dict):
        data["actor_name"] = actor.get("display_name") or actor.get("first_name", "")
    else:
        data["actor_name"] = str(actor) if actor else ""

    # Strip HTML from comment body
    body_html = data.get("comment_html") or ""
    if body_html:
        import re
        data["body_text"] = re.sub(r"<[^>]+>", "", body_html).strip()
    else:
        data["body_text"] = ""

    return data


@comment_app.command(name="list", alias="ls")
async def list_(
    issue: str,
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    limit: Annotated[int, Parameter(alias="-l")] = 50,
    json: bool = False,
) -> None:
    """List comments on a work item.

    Parameters
    ----------
    issue
        Work item identifier (ABC-123) or UUID.
    project
        Project name/ID (required for name-based lookup).
    limit
        Maximum comments to show.
    """
    try:
        client = get_client()
        workspace = get_workspace()

        if project:
            from planecli.utils.resolve import resolve_project_async
            proj = await resolve_project_async(project, client, workspace)
            project_id = proj["id"]
            item = await resolve_work_item_async(issue, client, workspace, project_id)
        else:
            item, project_id = await resolve_work_item_across_projects_async(
                issue, client, workspace
            )

        item_id = item["id"]
        response = await run_sdk(
            client.work_items.comments.list, workspace, project_id, item_id
        )
        comments = response.results if hasattr(response, "results") else []
    except PlaneError as e:
        raise handle_api_error(e)

    data = [_enrich_comment(c.model_dump()) for c in comments]
    data = data[:limit]
    output(data, COMMENT_COLUMNS, title=f"Comments on {issue}", as_json=json)


@comment_app.command(alias="new")
async def create(
    issue: str,
    *,
    body: Annotated[str, Parameter(alias="-b")],
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """Add a comment to a work item.

    Parameters
    ----------
    issue
        Work item identifier (ABC-123) or UUID.
    body
        Comment text (plain text, converted to HTML).
    project
        Project name/ID (required for name-based lookup).
    """
    from plane.models.work_items import CreateWorkItemComment

    try:
        client = get_client()
        workspace = get_workspace()

        if project:
            from planecli.utils.resolve import resolve_project_async
            proj = await resolve_project_async(project, client, workspace)
            project_id = proj["id"]
            item = await resolve_work_item_async(issue, client, workspace, project_id)
        else:
            item, project_id = await resolve_work_item_across_projects_async(
                issue, client, workspace
            )

        item_id = item["id"]

        comment_data = CreateWorkItemComment(comment_html=f"<p>{body}</p>")
        comment = await run_sdk(
            client.work_items.comments.create,
            workspace, project_id, item_id, comment_data,
        )
        data = _enrich_comment(comment.model_dump())
    except PlaneError as e:
        raise handle_api_error(e)

    if json:
        output_single(data, [], as_json=True)
    else:
        from planecli.formatters import console
        console.print(f"[green]Comment added to {issue}.[/]")


@comment_app.command
async def update(
    comment_id: str,
    *,
    issue: str,
    body: Annotated[str, Parameter(alias="-b")],
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """Update a comment on a work item.

    Parameters
    ----------
    comment_id
        Comment UUID.
    issue
        Work item identifier (ABC-123) or UUID.
    body
        New comment text (plain text, converted to HTML).
    project
        Project name/ID (required for name-based lookup).
    """
    from plane.models.work_items import UpdateWorkItemComment

    try:
        client = get_client()
        workspace = get_workspace()

        if project:
            from planecli.utils.resolve import resolve_project_async
            proj = await resolve_project_async(project, client, workspace)
            project_id = proj["id"]
            item = await resolve_work_item_async(issue, client, workspace, project_id)
        else:
            item, project_id = await resolve_work_item_across_projects_async(
                issue, client, workspace
            )

        item_id = item["id"]

        update_data = UpdateWorkItemComment(comment_html=f"<p>{body}</p>")
        comment = await run_sdk(
            client.work_items.comments.update,
            workspace, project_id, item_id, comment_id, update_data,
        )
        data = _enrich_comment(comment.model_dump())
    except PlaneError as e:
        raise handle_api_error(e)

    if json:
        output_single(data, [], as_json=True)
    else:
        from planecli.formatters import console
        console.print(f"[green]Comment updated on {issue}.[/]")


@comment_app.command
async def delete(
    comment_id: str,
    *,
    issue: str,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
) -> None:
    """Delete a comment from a work item.

    Parameters
    ----------
    comment_id
        Comment UUID.
    issue
        Work item identifier (ABC-123) or UUID.
    project
        Project name/ID (required for name-based lookup).
    """
    from planecli.formatters import console

    try:
        client = get_client()
        workspace = get_workspace()

        if project:
            from planecli.utils.resolve import resolve_project_async
            proj = await resolve_project_async(project, client, workspace)
            project_id = proj["id"]
            item = await resolve_work_item_async(issue, client, workspace, project_id)
        else:
            item, project_id = await resolve_work_item_across_projects_async(
                issue, client, workspace
            )

        item_id = item["id"]
        await run_sdk(
            client.work_items.comments.delete,
            workspace, project_id, item_id, comment_id,
        )
    except PlaneError as e:
        raise handle_api_error(e)

    console.print("[green]Comment deleted.[/]")
