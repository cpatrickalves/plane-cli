"""Document / page commands."""

from __future__ import annotations

import asyncio
from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.async_sdk import run_sdk
from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.formatters import output, output_single
from planecli.utils.resolve import resolve_project_async

doc_app = cyclopts.App(
    name=["document", "documents", "doc", "docs"],
    help="Manage project documents / pages.",
)

DOC_COLUMNS = [
    ("id", "ID"),
    ("name", "Title"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]

DOC_FIELDS = [
    ("id", "UUID"),
    ("name", "Title"),
    ("content_text", "Content"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]


def _enrich_doc(data: dict) -> dict:
    """Add convenience fields to a document dict."""
    desc_html = data.get("description_html") or ""
    if desc_html:
        import re
        data["content_text"] = re.sub(r"<[^>]+>", "", desc_html).strip()
    else:
        data["content_text"] = ""
    return data


@doc_app.command(name="list", alias="ls")
async def list_(
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """List documents.

    Parameters
    ----------
    project
        Project name, identifier, or UUID. If not specified, lists workspace pages.

    Note: The SDK has limited page listing support. This command uses direct API calls
    as a fallback.
    """
    import requests

    from planecli.exceptions import ValidationError

    try:
        client = get_client()
        workspace = get_workspace()

        if project:
            proj = await resolve_project_async(project, client, workspace)
            project_id = proj["id"]
            # Use direct API call since SDK doesn't have list_project_pages
            from planecli.api.client import get_config
            config = get_config()
            url = f"{config.base_url}/api/v1/workspaces/{workspace}/projects/{project_id}/pages/"
            headers = {"X-Api-Key": config.api_key}
            resp = await asyncio.to_thread(
                requests.get, url, headers=headers, timeout=30
            )
            resp.raise_for_status()
            resp_data = resp.json()
            # Handle paginated response
            if isinstance(resp_data, dict) and "results" in resp_data:
                pages = resp_data["results"]
            elif isinstance(resp_data, list):
                pages = resp_data
            else:
                pages = []
        else:
            raise ValidationError(
                "Project is required for listing documents.",
                hint="Use --project <name-or-id> to specify the project.",
            )
    except PlaneError as e:
        raise handle_api_error(e)

    data = [_enrich_doc(p if isinstance(p, dict) else p.model_dump()) for p in pages]
    output(data, DOC_COLUMNS, title="Documents", as_json=json)


@doc_app.command(alias="read")
async def show(
    document: str,
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """Show document details.

    Parameters
    ----------
    document
        Document UUID.
    project
        Project name/ID (required for project-level pages).
    """
    try:
        client = get_client()
        workspace = get_workspace()

        if project:
            proj = await resolve_project_async(project, client, workspace)
            project_id = proj["id"]
            page = await run_sdk(
                client.pages.retrieve_project_page, workspace, project_id, document
            )
        else:
            page = await run_sdk(
                client.pages.retrieve_workspace_page, workspace, document
            )

        data = _enrich_doc(page.model_dump())
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, DOC_FIELDS, title="Document Details", as_json=json)


@doc_app.command(alias="new")
async def create(
    *,
    title: str,
    content: Annotated[str | None, Parameter(alias="-c")] = None,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """Create a new document.

    Parameters
    ----------
    title
        Document title.
    content
        Document content (plain text / markdown, converted to HTML).
    project
        Project to create the document in. If not specified, creates a workspace page.
    """
    from plane.models.pages import CreatePage

    try:
        client = get_client()
        workspace = get_workspace()

        page_data = CreatePage(name=title)
        if content:
            page_data.description_html = f"<p>{content}</p>"

        if project:
            proj = await resolve_project_async(project, client, workspace)
            project_id = proj["id"]
            page = await run_sdk(
                client.pages.create_project_page, workspace, project_id, page_data
            )
        else:
            page = await run_sdk(
                client.pages.create_workspace_page, workspace, page_data
            )

        data = _enrich_doc(page.model_dump())
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, DOC_FIELDS, title="Document Created", as_json=json)


@doc_app.command
async def update(
    document: str,
    *,
    title: str | None = None,
    content: Annotated[str | None, Parameter(alias="-c")] = None,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """Update a document.

    Parameters
    ----------
    document
        Document UUID.
    title
        New document title.
    content
        New content (plain text / markdown).
    project
        Project name/ID (required for project-level pages).

    Note: Uses direct API call since the SDK doesn't support page updates.
    """
    import requests

    try:
        client = get_client()
        workspace = get_workspace()
        from planecli.api.client import get_config
        config = get_config()

        update_payload: dict = {}
        if title:
            update_payload["name"] = title
        if content:
            update_payload["description_html"] = f"<p>{content}</p>"

        if project:
            proj = await resolve_project_async(project, client, workspace)
            project_id = proj["id"]
            base = f"{config.base_url}/api/v1/workspaces/{workspace}"
            url = f"{base}/projects/{project_id}/pages/{document}/"
        else:
            url = f"{config.base_url}/api/v1/workspaces/{workspace}/pages/{document}/"

        headers = {"X-Api-Key": config.api_key, "Content-Type": "application/json"}
        resp = await asyncio.to_thread(
            requests.patch, url, headers=headers, json=update_payload, timeout=30
        )
        resp.raise_for_status()
        data = _enrich_doc(resp.json())
    except PlaneError as e:
        raise handle_api_error(e)

    output_single(data, DOC_FIELDS, title="Document Updated", as_json=json)


@doc_app.command
async def delete(
    document: str,
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
) -> None:
    """Delete (trash) a document.

    Parameters
    ----------
    document
        Document UUID.
    project
        Project name/ID (required for project-level pages).

    Note: Uses direct API call since the SDK doesn't support page deletion.
    """
    import requests

    from planecli.formatters import console

    try:
        client = get_client()
        workspace = get_workspace()
        from planecli.api.client import get_config
        config = get_config()

        if project:
            proj = await resolve_project_async(project, client, workspace)
            project_id = proj["id"]
            base = f"{config.base_url}/api/v1/workspaces/{workspace}"
            url = f"{base}/projects/{project_id}/pages/{document}/"
        else:
            url = f"{config.base_url}/api/v1/workspaces/{workspace}/pages/{document}/"

        headers = {"X-Api-Key": config.api_key}
        resp = await asyncio.to_thread(
            requests.delete, url, headers=headers, timeout=30
        )
        resp.raise_for_status()
    except PlaneError as e:
        raise handle_api_error(e)

    console.print(f"[green]Document {document} deleted.[/]")
