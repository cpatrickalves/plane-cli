"""Work item attachment commands (file upload)."""

from __future__ import annotations

import mimetypes
import os
from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.async_sdk import run_sdk
from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.exceptions import APIError, ValidationError
from planecli.formatters import output, output_single
from planecli.utils.resolve import (
    resolve_work_item_across_projects_async,
    resolve_work_item_async,
)

attachment_app = cyclopts.App(
    name=["attachment", "attachments"],
    help="Manage work item file attachments.",
)

ATTACHMENT_COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("type", "Type"),
    ("size", "Size"),
    ("is_uploaded", "Uploaded"),
    ("created_at", "Created"),
]


def _enrich_attachment(data: dict) -> dict:
    """Flatten the nested `attributes` dict into top-level display fields.

    The attachment API stores the original filename/MIME under `attributes`
    and the byte count at the top level; flatten both so formatters and
    `--json` consumers see one consistent shape.
    """
    attrs = data.get("attributes") or {}
    data["name"] = attrs.get("name", "")
    data["type"] = attrs.get("type", "")
    data["size"] = data.get("size") if data.get("size") is not None else attrs.get("size")
    return data


def _guess_mime(filename: str) -> str:
    """Guess a MIME type, defaulting to application/octet-stream."""
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


async def _resolve_item(issue: str, project: str | None):
    """Resolve a work item to (item_dict, project_id), with or without -p."""
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
    return item, project_id


def embed_html(asset_id: str) -> str:
    """Build an <img> paragraph embedding an uploaded asset into a description.

    The editor's image node stores the asset UUID in src — not a URL. The web
    app resolves it at render time (getEditorAssetSrc); a full path here is
    mistaken for an asset id and the image fails to load.
    """
    return f'<p><img src="{asset_id}" /></p>'


def _app_post_json(url: str, api_key: str, payload: dict):
    """POST JSON to a session-only app endpoint, authenticating with an API token."""
    import requests

    return requests.post(
        url,
        headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )


def _app_patch_json(url: str, api_key: str, payload: dict | None = None):
    import requests

    return requests.patch(
        url,
        headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
        json=payload or {},
        timeout=60,
    )


def _app_get(url: str, api_key: str):
    import requests

    return requests.get(url, headers={"X-Api-Key": api_key}, timeout=60)


async def upload_embed_image(
    client, workspace: str, project_id: str, item_id: str, path: str, force: bool = False
) -> str:
    """Upload an image for description embedding; return the asset UUID.

    Prefers the native app asset endpoint (entity_type=ISSUE_DESCRIPTION — the
    image renders inline and does not clutter the attachment list). Servers
    whose app endpoints are session-only answer 401/403/404, in which case we
    fall back to a v1 ISSUE_ATTACHMENT upload (see PLANE-4 for the server-side
    fix that removes the need for the fallback).
    """
    from planecli.api.client import get_config

    cfg = get_config()
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        raise ValidationError(f"File not found: {path}")
    name = os.path.basename(path)
    size = os.path.getsize(path)
    mime = _guess_mime(name)

    v2_url = f"{cfg.base_url}/api/assets/v2/workspaces/{workspace}/projects/{project_id}/"
    # NOTE: raw requests + X-Api-Key, same pattern as documents.py — the SDK
    # only covers /api/v1/ endpoints (see ADR-0003).
    resp = await run_sdk(
        _app_post_json,
        v2_url,
        cfg.api_key,
        {
            "name": name,
            "type": mime,
            "size": size,
            "entity_type": "ISSUE_DESCRIPTION",
            "entity_identifier": item_id,
        },
    )
    if resp.status_code in (401, 403, 404):
        att = await upload_attachment(
            client, workspace, project_id, item_id, path, force=force
        )
        return att["id"]
    if resp.status_code != 200:
        raise APIError(f"Asset upload failed: HTTP {resp.status_code}")

    created = resp.json()
    upload = created["upload_data"]
    import requests

    with open(path, "rb") as fh:
        up = await run_sdk(
            requests.post,
            upload["url"],
            data=upload["fields"],
            files={"file": (name, fh, mime)},
        )
    if up.status_code not in (200, 201, 204):
        raise APIError(f"File upload failed: HTTP {up.status_code}")

    asset_id = created["asset_id"]
    mark = await run_sdk(
        _app_patch_json, f"{v2_url}{asset_id}/", cfg.api_key, {"is_uploaded": True}
    )
    if mark.status_code not in (200, 204):
        raise APIError(f"Asset confirm failed: HTTP {mark.status_code}")

    # Read back through the v1 generic-asset endpoint (workspace-scoped, works
    # for any entity type) — a 2xx on the PATCH is not proof of the write
    # (see ADR-0007).
    check = await run_sdk(
        _app_get,
        f"{cfg.base_url}/api/v1/workspaces/{workspace}/assets/{asset_id}/",
        cfg.api_key,
    )
    if check.status_code != 200:
        raise APIError("Image asset was not confirmed by the server after upload.")
    return asset_id


def _confirm_duplicate(name: str, existing: list[dict]) -> bool:
    """Ask before uploading a file whose name is already attached.

    Interactive (TTY): prompt y/N. Non-interactive: refuse — scripts must
    pass --force explicitly.
    """
    import sys

    if not sys.stdin.isatty():
        return False
    try:
        answer = input(
            f"An attachment named '{name}' already exists "
            f"({len(existing)}x). Upload anyway? [y/N] "
        )
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


async def upload_attachment(
    client, workspace: str, project_id: str, item_id: str, path: str, force: bool = False
) -> dict:
    """Upload a file to a work item (dup-check -> register -> push -> mark -> verify).

    Returns the raw attachment dict with is_uploaded=True. Raises
    ValidationError if the file does not exist (or the upload is cancelled at
    the duplicate-name prompt), APIError if the server does not confirm the
    upload (see ADR-0007).
    """
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        raise ValidationError(f"File not found: {path}")
    name = os.path.basename(path)
    size = os.path.getsize(path)
    endpoint = f"{workspace}/projects/{project_id}/work-items/{item_id}/attachments"

    # Guard against duplicate uploads: same-named attachments are easy to
    # create by accident and hard to tell apart in the web UI (deleting the
    # wrong one breaks embedded images). Confirm before adding another.
    listed = await run_sdk(client.work_items.attachments._get, endpoint)
    items = listed if isinstance(listed, list) else listed.get("results", [])
    existing = [
        a
        for a in items
        if not a.get("is_deleted") and (a.get("attributes") or {}).get("name") == name
    ]
    if existing and not force and not _confirm_duplicate(name, existing):
        raise ValidationError(
            f"Upload cancelled: '{name}' is already attached "
            f"({len(existing)}x). Re-run with --force to upload anyway."
        )

    mime = _guess_mime(name)

    # Three-step upload, mirroring what the Plane web app does:
    # NOTE: the SDK's typed attachment methods drop `upload_data` (the
    # presigned form), so the raw resource methods are used throughout —
    # same escape hatch as the resolvers (see ADR-0003).
    # 1. Register the attachment -> get a presigned upload target.
    created = await run_sdk(
        client.work_items.attachments._post,
        endpoint,
        {"name": name, "type": mime, "size": size},
    )
    asset_id = created["asset_id"]
    upload = created["upload_data"]

    # 2. Push the bytes to the presigned URL. The signature lives in the
    # form fields — no X-Api-Key header here.
    import requests

    with open(path, "rb") as fh:
        resp = await run_sdk(
            requests.post,
            upload["url"],
            data=upload["fields"],
            files={"file": (name, fh, mime)},
        )
    if resp.status_code not in (200, 201, 204):
        raise APIError(f"File upload failed: HTTP {resp.status_code}")

    # 3. Mark the attachment uploaded, then read it back — a 2xx on the
    # PATCH is not proof the write landed (see ADR-0007).
    await run_sdk(
        client.work_items.attachments._patch,
        f"{endpoint}/{asset_id}",
        {"is_uploaded": True},
    )
    listed = await run_sdk(client.work_items.attachments._get, endpoint)
    items = listed if isinstance(listed, list) else listed.get("results", [])
    mine = next((a for a in items if a.get("id") == asset_id), None)
    if not mine or not mine.get("is_uploaded"):
        raise APIError("Attachment was not confirmed by the server after upload.")
    return mine


@attachment_app.command(alias=["upload", "new"])
async def attach(
    issue: str,
    file: Annotated[str, Parameter(alias="-f")],
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    force: bool = False,
    json: bool = False,
) -> None:
    """Upload a file attachment to a work item.

    Parameters
    ----------
    issue
        Work item identifier (ABC-123) or UUID.
    file
        Path to the file to upload.
    project
        Project name/ID (required for name-based lookup).
    force
        Upload even if an attachment with the same file name already exists.
    """
    from planecli.formatters import console

    try:
        item, project_id = await _resolve_item(issue, project)
        client = get_client()
        workspace = get_workspace()
        mine = await upload_attachment(
            client, workspace, project_id, item["id"], file, force=force
        )
    except PlaneError as e:
        raise handle_api_error(e)

    data = _enrich_attachment(mine)
    if json:
        output_single(data, [], as_json=True)
    else:
        console.print(
            f"[green]Attached {data['name']} ({data['size']} bytes) to {issue}.[/]"
        )


@attachment_app.command(name="list", alias="ls")
async def list_(
    issue: str,
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """List attachments on a work item.

    Parameters
    ----------
    issue
        Work item identifier (ABC-123) or UUID.
    project
        Project name/ID (required for name-based lookup).
    """
    try:
        item, project_id = await _resolve_item(issue, project)
        client = get_client()
        workspace = get_workspace()
        endpoint = (
            f"{workspace}/projects/{project_id}/work-items/{item['id']}/attachments"
        )
        listed = await run_sdk(client.work_items.attachments._get, endpoint)
    except PlaneError as e:
        raise handle_api_error(e)

    items = listed if isinstance(listed, list) else listed.get("results", [])
    data = [_enrich_attachment(a) for a in items]
    output(data, ATTACHMENT_COLUMNS, title=f"Attachments on {issue}", as_json=json)
