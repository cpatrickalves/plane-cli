"""Work item relation commands (blocking, duplicate, relates_to, ...)."""

from __future__ import annotations

import asyncio
from typing import Annotated

import cyclopts
from cyclopts import Parameter
from loguru import logger
from plane.errors import HttpError, PlaneError

from planecli.api.async_sdk import create_client, run_sdk
from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.exceptions import APIError, ValidationError
from planecli.formatters import output
from planecli.utils.resolve import (
    resolve_work_item_across_projects_async,
    resolve_work_item_and_project_async,
    resolve_work_item_async,
)

relation_app = cyclopts.App(
    name=["relation", "relations"],
    help="Manage relations between work items (blocking, duplicate, relates_to, ...).",
)

# The keys of the relations response, read as "ISSUE <type> TARGET".
RELATION_TYPES = (
    "blocking",
    "blocked_by",
    "duplicate",
    "relates_to",
    "start_before",
    "start_after",
    "finish_before",
    "finish_after",
)

RELATION_COLUMNS = [
    ("relation_type", "Relation"),
    ("identifier", "ID"),
    ("name", "Title"),
    ("issue_id", "UUID"),
]


def _normalize_type(value: str) -> str:
    """Accept blocked-by / Blocked By / blocked_by; reject unknown types."""
    norm = value.strip().lower().replace("-", "_").replace(" ", "_")
    if norm not in RELATION_TYPES:
        raise ValidationError(
            f"Unknown relation type: {value!r}.",
            hint=f"Use one of: {', '.join(RELATION_TYPES)}.",
        )
    return norm


def _relations_endpoint(workspace: str, project_id: str, item_id: str) -> str:
    return f"{workspace}/projects/{project_id}/work-items/{item_id}/relations"


def _flatten(raw: dict) -> list[dict]:
    """Turn the type-keyed response into one row per related work item.

    Plane v1.4 lists {project_id, issue_id} objects under each type; the
    SDK model expects bare UUID strings. Accept both.
    """
    rows = []
    for rel_type in RELATION_TYPES:
        for entry in (raw or {}).get(rel_type) or []:
            if isinstance(entry, dict):
                issue_id, project_id = entry.get("issue_id"), entry.get("project_id")
            else:
                issue_id, project_id = str(entry), None
            rows.append({"relation_type": rel_type, "issue_id": issue_id, "project_id": project_id})
    return rows


async def _fetch_raw_relations(client, workspace: str, project_id: str, item_id: str) -> dict:
    # NOTE: raw _get — WorkItemRelationResponse expects lists of UUID strings
    # and fails on the {project_id, issue_id} objects the API returns
    # (see ADR-0003).
    return await run_sdk(
        client.work_items.relations._get, _relations_endpoint(workspace, project_id, item_id)
    )


async def fetch_issue_relations(
    client, workspace: str, project_id: str, item_id: str
) -> list[dict]:
    """Fetch a work item's relations, one row per related item.

    Each row carries relation_type, issue_id, project_id and, when the
    related item can be read, its identifier (ABC-123) and name; a related
    item that fails to load keeps null for both. Shared by `relation ls`
    and `wi show`. Raises if the relation list itself fails.
    """
    from planecli.cache import cached_list_projects

    rows = _flatten(await _fetch_raw_relations(client, workspace, project_id, item_id))
    if not rows:
        return []
    try:
        projects = await cached_list_projects(workspace)
    except PlaneError:
        projects = []
    identifiers = {p["id"]: p.get("identifier", "") for p in projects if p.get("id")}

    async def _describe(row: dict) -> dict:
        row["identifier"], row["name"] = None, None
        # A fresh client per concurrent call: the SDK session is not
        # thread-safe (ADR-0001).
        item_client = create_client()
        pid = row["project_id"] or project_id
        try:
            item = await run_sdk(
                item_client.work_items._get,
                f"{workspace}/projects/{pid}/work-items/{row['issue_id']}",
            )
        except PlaneError as exc:
            logger.warning("Failed to fetch related work item {}: {}", row["issue_id"], exc)
            return row
        row["project_id"] = item.get("project") or pid
        prefix = identifiers.get(row["project_id"])
        seq = item.get("sequence_id")
        row["identifier"] = f"{prefix}-{seq}" if prefix and seq is not None else None
        row["name"] = item.get("name")
        return row

    return list(await asyncio.gather(*[_describe(r) for r in rows]))


async def _resolve_targets(
    targets: tuple[str, ...], project: str | None, client, workspace: str, project_id: str
) -> list[dict]:
    """Resolve target work items (identifiers, UUIDs; names with -p)."""
    if project:
        lookups = [resolve_work_item_async(t, client, workspace, project_id) for t in targets]
        return list(await asyncio.gather(*lookups))
    results = await asyncio.gather(
        *[resolve_work_item_across_projects_async(t, client, workspace) for t in targets]
    )
    return [item for item, _ in results]


def _types_for(rows: list[dict], issue_id: str) -> set[str]:
    return {r["relation_type"] for r in rows if r["issue_id"] == issue_id}


@relation_app.command(name="list", alias="ls")
async def list_(
    issue: str,
    *,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """List the relations of a work item.

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
        rows = await fetch_issue_relations(client, workspace, project_id, item["id"])
    except PlaneError as e:
        raise handle_api_error(e)

    output(rows, RELATION_COLUMNS, title=f"Relations of {issue}", as_json=json)


@relation_app.command(alias=["create", "new"])
async def add(
    issue: str,
    relation_type: str,
    *targets: str,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """Relate a work item to others: ISSUE RELATION_TYPE TARGET...

    Reads as a sentence: "relation add ABC-1 blocking ABC-2" means ABC-1
    blocks ABC-2. On self-hosted Plane up to v1.4.2 the API cannot remove a
    relation again; only the web app can.

    Parameters
    ----------
    issue
        Work item identifier (ABC-123) or UUID.
    relation_type
        One of: blocking, blocked_by, duplicate, relates_to, start_before,
        start_after, finish_before, finish_after.
    targets
        Related work items (ABC-123 or UUID; names need --project).
    project
        Project name/ID (required for name-based lookup).
    """
    rel_type = _normalize_type(relation_type)
    if not targets:
        raise ValidationError("Give at least one target work item.")

    try:
        client = get_client()
        workspace = get_workspace()
        item, project_id = await resolve_work_item_and_project_async(
            issue, project, client, workspace
        )
        related = await _resolve_targets(targets, project, client, workspace, project_id)
        if any(r["id"] == item["id"] for r in related):
            raise ValidationError("A work item cannot be related to itself.")
        await run_sdk(
            client.work_items.relations._post,
            _relations_endpoint(workspace, project_id, item["id"]),
            {"relation_type": rel_type, "issues": [r["id"] for r in related]},
        )
        rows = await fetch_issue_relations(client, workspace, project_id, item["id"])
    except PlaneError as e:
        raise handle_api_error(e)

    # The API skips targets it cannot see (another workspace) and still
    # answers 201, so check the relations that actually exist (ADR-0007).
    missing = [t for t, r in zip(targets, related) if rel_type not in _types_for(rows, r["id"])]
    if missing:
        raise APIError(
            f"The server did not create the {rel_type} relation to: {', '.join(missing)}."
        )

    ids = {r["id"] for r in related}
    added = [r for r in rows if r["issue_id"] in ids and r["relation_type"] == rel_type]
    output(added, RELATION_COLUMNS, title=f"Relations added to {issue}", as_json=json)


@relation_app.command(alias=["rm", "delete"])
async def remove(
    issue: str,
    *targets: str,
    project: Annotated[str | None, Parameter(alias="-p")] = None,
) -> None:
    """Remove the relation between a work item and each TARGET.

    Plane removes one relation per pair, whatever its type. Self-hosted
    Plane up to v1.4.2 has no API endpoint for this (only the web app can
    remove relations); the command then fails without changing anything.

    Parameters
    ----------
    issue
        Work item identifier (ABC-123) or UUID.
    targets
        Related work items (ABC-123 or UUID; names need --project).
    project
        Project name/ID (required for name-based lookup).
    """
    from planecli.formatters import console

    if not targets:
        raise ValidationError("Give at least one target work item.")

    try:
        client = get_client()
        workspace = get_workspace()
        item, project_id = await resolve_work_item_and_project_async(
            issue, project, client, workspace
        )
        related = await _resolve_targets(targets, project, client, workspace, project_id)
        endpoint = _relations_endpoint(workspace, project_id, item["id"])
        before = _flatten(await _fetch_raw_relations(client, workspace, project_id, item["id"]))
        unrelated = [t for t, r in zip(targets, related) if not _types_for(before, r["id"])]
        if unrelated:
            raise ValidationError(f"{issue} has no relation to: {', '.join(unrelated)}.")
        for target, rel in zip(targets, related):
            try:
                await run_sdk(
                    client.work_items.relations._post,
                    f"{endpoint}/remove",
                    {"related_issue": rel["id"]},
                )
            except HttpError as e:
                if e.status_code in (404, 405):
                    raise APIError(
                        "This Plane server's API cannot remove relations "
                        "(no relations/remove endpoint). Remove it in the web app.",
                        status_code=e.status_code,
                    )
                raise
        after = _flatten(await _fetch_raw_relations(client, workspace, project_id, item["id"]))
    except PlaneError as e:
        raise handle_api_error(e)

    # Verify against the server, not the status code (ADR-0007).
    for target, rel in zip(targets, related):
        was, now = _types_for(before, rel["id"]), _types_for(after, rel["id"])
        if now == was:
            raise APIError(f"The server did not remove the relation to {target}.")
        if now:
            console.print(
                f"{issue} is still related to {target} as: {', '.join(sorted(now))}.",
                style="yellow",
                markup=False,
            )
    console.print(
        f"Removed relation(s) between {issue} and {', '.join(targets)}.",
        style="green",
        markup=False,
    )
