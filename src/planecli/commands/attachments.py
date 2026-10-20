"""Work item attachment commands (upload, list, download)."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
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


_EXTRA_MIME = {".md": "text/markdown", ".markdown": "text/markdown", ".log": "text/plain"}


def _guess_mime(filename: str) -> str:
    """Guess a MIME type, defaulting to application/octet-stream."""
    mime, _ = mimetypes.guess_type(filename)
    # The platform MIME database is not the same everywhere (macOS lacks .md).
    return mime or _EXTRA_MIME.get(Path(filename).suffix.lower(), "application/octet-stream")


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

    # Fail on a bad path before touching the config or the network.
    if not os.path.isfile(file):
        raise ValidationError(f"File not found: {file}")
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


DOWNLOAD_COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("size", "Size"),
    ("path", "Saved To"),
]


def _describe(attachments: list[dict]) -> str:
    """One line per attachment ('id  name') for error messages."""
    return "\n".join(f"  {a['id']}  {a['name']}" for a in attachments)


def _select_attachments(
    attachments: list[dict], selector: str | None, all_: bool
) -> list[dict]:
    """Pick the attachments to download.

    SELECTOR matches an attachment id or its exact file name. Several
    attachments may share a name (pasted screenshots are all "image.png"),
    so a name that matches more than one is ambiguous unless --all is given.
    Without a SELECTOR, --all takes everything and a lone attachment is
    taken as-is.
    """
    if selector is not None:
        by_id = [a for a in attachments if a.get("id") == selector]
        if by_id:
            return by_id
        by_name = [a for a in attachments if a["name"] == selector]
        if not by_name:
            raise ValidationError(
                f"No attachment matches '{selector}'.",
                hint="Available attachments:\n" + _describe(attachments)
                if attachments
                else "The work item has no attachments.",
            )
        if len(by_name) > 1 and not all_:
            raise ValidationError(
                f"{len(by_name)} attachments are named '{selector}'.",
                hint="Pass one id, or --all to save them all:\n" + _describe(by_name),
            )
        return by_name

    if not attachments:
        raise ValidationError("The work item has no attachments.")
    if all_ or len(attachments) == 1:
        return attachments
    raise ValidationError(
        f"The work item has {len(attachments)} attachments; choose one.",
        hint="Pass an id or file name, or --all to save them all:\n"
        + _describe(attachments),
    )


def _safe_filename(name: str, fallback: str) -> str:
    """Reduce an attachment name to a bare file name (no directories)."""
    base = os.path.basename(name.replace("\\", "/")).strip()
    return base if base not in ("", ".", "..") else fallback


def _plan_paths(selected: list[dict], directory: Path, overwrite: bool) -> list[Path]:
    """Choose a target path per attachment, suffixing duplicate names.

    Names repeated within the batch become name-2.ext, name-3.ext, ...; an
    existing file on disk is sidestepped the same way unless overwrite is set.
    """
    taken: set[Path] = set()
    paths: list[Path] = []
    for att in selected:
        name = _safe_filename(att["name"], att["id"])
        stem, suffix = os.path.splitext(name)
        candidate = directory / name
        n = 1
        while candidate in taken or (not overwrite and candidate.exists()):
            n += 1
            candidate = directory / f"{stem}-{n}{suffix}"
        taken.add(candidate)
        paths.append(candidate)
    return paths


def _download_attachment(url: str, api_key: str, dest: Path) -> int:
    """Stream one attachment to dest; return the bytes written.

    The detail endpoint answers with a redirect to a presigned storage URL.
    The redirect is followed by hand so the API key is not sent to the
    storage host — the signature lives in the URL. Bytes go to a .part file
    that is renamed on success, so a failed download leaves no partial file.
    """
    from urllib.parse import urljoin

    import requests

    resp = requests.get(
        url, headers={"X-Api-Key": api_key}, allow_redirects=False, stream=True, timeout=60
    )
    if resp.is_redirect:
        location = urljoin(url, resp.headers["Location"])
        resp.close()
        resp = requests.get(location, stream=True, timeout=60)
    if resp.status_code == 401:
        from planecli.exceptions import AuthenticationError

        raise AuthenticationError()
    if resp.status_code != 200:
        raise APIError(f"Download failed: HTTP {resp.status_code}", status_code=resp.status_code)

    part = dest.with_name(dest.name + ".part")
    written = 0
    try:
        with resp, open(part, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                fh.write(chunk)
                written += len(chunk)
        part.replace(dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return written


@attachment_app.command(name="get", alias=["download", "dl"])
async def get(
    issue: str,
    selector: str | None = None,
    *,
    all_: Annotated[bool, Parameter(name="--all")] = False,
    dir: Annotated[str | None, Parameter(alias="-d")] = None,
    output_file: Annotated[str | None, Parameter(name=["--output", "-o"])] = None,
    force: bool = False,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """Download work item attachments to disk.

    Parameters
    ----------
    issue
        Work item identifier (ABC-123) or UUID.
    selector
        Attachment id or exact file name. Optional when the work item has a
        single attachment or --all is given.
    all_
        Download every attachment (or every one named SELECTOR). Repeated
        file names are saved as name-2.ext, name-3.ext, ...
    dir
        Directory to save into (default: the current directory).
    output_file
        File path to save a single attachment to (overwrites).
    force
        Overwrite existing files in --dir instead of adding a numeric suffix.
    project
        Project name/ID (required for name-based lookup).
    """
    from planecli.api.client import get_config

    if output_file is not None and dir is not None:
        raise ValidationError("Use either --output or --dir, not both.")
    directory = Path(os.path.expanduser(dir)) if dir is not None else Path.cwd()
    if not directory.is_dir():
        raise ValidationError(f"Directory not found: {directory}")

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
    attachments = [_enrich_attachment(a) for a in items if not a.get("is_deleted")]
    selected = _select_attachments(attachments, selector, all_)

    if output_file is not None:
        if len(selected) > 1:
            raise ValidationError(
                f"--output takes a single attachment, but {len(selected)} were selected.",
                hint="Use --dir to save several files.",
            )
        paths = [Path(os.path.expanduser(output_file))]
    else:
        paths = _plan_paths(selected, directory, overwrite=force)

    # NOTE: raw requests + X-Api-Key, same pattern as documents.py — the SDK
    # has no download method, and its session would carry the API key across
    # the storage redirect (see ADR-0003).
    cfg = get_config()
    base = f"{cfg.base_url}/api/v1/workspaces/{endpoint}"
    saved = []
    for att, path in zip(selected, paths):
        written = await run_sdk(
            _download_attachment, f"{base}/{att['id']}/", cfg.api_key, path
        )
        saved.append(
            {
                "id": att["id"],
                "name": att["name"],
                "type": att["type"],
                "size": written,
                "path": str(path.resolve()),
            }
        )

    output(saved, DOWNLOAD_COLUMNS, title=f"Downloaded from {issue}", as_json=json)
