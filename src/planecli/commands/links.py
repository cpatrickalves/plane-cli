"""Work item link commands (URLs attached to a work item)."""

from __future__ import annotations

from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.async_sdk import run_sdk
from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.exceptions import APIError, ValidationError
from planecli.formatters import output
from planecli.utils.resolve import resolve_work_item_and_project_async

link_app = cyclopts.App(
    name=["link", "links"],
    help="Manage work item links (URLs).",
)

LINK_COLUMNS = [
    ("id", "ID"),
    ("title", "Title"),
    ("url", "URL"),
    ("created_at", "Created"),
]


def _enrich_link(data: dict) -> dict:
    """Fill a missing title from the crawled metadata and drop the favicon.

    Plane crawls each URL and stores its favicon as a base64 data URI in
    metadata — kilobytes of noise in every --json payload.
    """
    meta = data.get("metadata")
    if isinstance(meta, dict):
        meta.pop("favicon", None)
        if not data.get("title"):
            data["title"] = meta.get("title") or ""
    data.setdefault("title", "")
    return data


def _links_endpoint(workspace: str, project_id: str, item_id: str) -> str:
    return f"{workspace}/projects/{project_id}/work-items/{item_id}/links"


async def fetch_issue_links(client, workspace: str, project_id: str, item_id: str) -> list[dict]:
    """Fetch all links of a work item, oldest first.

    Shared by `link ls` and `wi show`. Always raises on failure — callers
    own the failure policy.
    """
    # NOTE: raw _get — the typed list drops nothing today, but create needs
    # the raw method anyway (CreateWorkItemLink has no title), so both use
    # the same dict shape (see ADR-0003).
    endpoint = _links_endpoint(workspace, project_id, item_id)
    links: list[dict] = []
    cursor = None
    while True:
        params = {"per_page": 100, **({"cursor": cursor} if cursor else {})}
        page = await run_sdk(client.work_items.links._get, endpoint, params)
        if isinstance(page, list):
            links.extend(page)
            break
        links.extend(page.get("results") or [])
        cursor = page.get("next_cursor")
        if page.get("next_page_results") is not True or not isinstance(cursor, str):
            break
    links = [_enrich_link(lk) for lk in links]
    links.sort(key=lambda lk: lk.get("created_at") or "")
    return links


@link_app.command(name="list", alias="ls")
async def list_(
    issue: str,
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """List the links of a work item.

    Parameters
    ----------
    issue
        Work item identifier (ABC-123) or UUID.
    project
        Project name/ID (required for name-based lookup).
    """
    try:
        client = get_client()
        workspace = get_workspace()
        item, project_id = await resolve_work_item_and_project_async(
            issue, project, client, workspace
        )
        links = await fetch_issue_links(client, workspace, project_id, item["id"])
    except PlaneError as e:
        raise handle_api_error(e)

    output(links, LINK_COLUMNS, title=f"Links on {issue}", as_json=json)


@link_app.command(name="add", alias=["create", "new"])
async def add(
    issue: str,
    url: str,
    *,
    title: Annotated[str | None, Parameter(alias="-t")] = None,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """Add a link (URL) to a work item.

    Parameters
    ----------
    issue
        Work item identifier (ABC-123) or UUID.
    url
        The URL to link (http or https).
    title
        Link title. Without one, Plane fills it in from the page.
    project
        Project name/ID (required for name-based lookup).
    """
    from planecli.formatters import console, output_single

    if not url.startswith(("http://", "https://")):
        raise ValidationError(f"Not an http(s) URL: {url}")
    payload = {"url": url}
    if title is not None:
        payload["title"] = title

    try:
        client = get_client()
        workspace = get_workspace()
        item, project_id = await resolve_work_item_and_project_async(
            issue, project, client, workspace
        )
        endpoint = _links_endpoint(workspace, project_id, item["id"])
        created = await run_sdk(client.work_items.links._post, endpoint, payload)
    except PlaneError as e:
        raise handle_api_error(e)

    # A 2xx is not proof the write landed (ADR-0007): the echo must carry an
    # id and the URL that was sent.
    if not isinstance(created, dict) or not created.get("id") or created.get("url") != url:
        raise APIError("The server did not confirm the new link.")

    data = _enrich_link(created)
    if json:
        output_single(data, [], as_json=True)
    else:
        console.print(f"Linked {url} to {issue} ({data['id']}).", style="green", markup=False)


@link_app.command(alias=["rm", "remove"])
async def delete(
    issue: str,
    link: str,
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
) -> None:
    """Delete a link from a work item.

    Parameters
    ----------
    issue
        Work item identifier (ABC-123) or UUID.
    link
        Link id, or the exact URL (a URL is linked at most once per work item).
    project
        Project name/ID (required for name-based lookup).
    """
    from planecli.formatters import console

    try:
        client = get_client()
        workspace = get_workspace()
        item, project_id = await resolve_work_item_and_project_async(
            issue, project, client, workspace
        )
        links = await fetch_issue_links(client, workspace, project_id, item["id"])
        match = next((lk for lk in links if link in (lk.get("id"), lk.get("url"))), None)
        if match is None:
            listing = "\n".join(f"  {lk['id']}  {lk.get('url')}" for lk in links)
            raise ValidationError(
                f"No link on {issue} matches '{link}'.",
                hint=f"Links on {issue}:\n{listing}" if links else f"{issue} has no links.",
            )
        endpoint = _links_endpoint(workspace, project_id, item["id"])
        await run_sdk(client.work_items.links._delete, f"{endpoint}/{match['id']}")
    except PlaneError as e:
        raise handle_api_error(e)

    console.print(f"Link {match.get('url')} removed from {issue}.", style="green", markup=False)
