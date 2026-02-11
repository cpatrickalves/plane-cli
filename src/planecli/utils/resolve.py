"""Resource name/ID/UUID resolution layer.

Tries resolution in order: UUID direct lookup -> identifier match -> fuzzy name match.
"""

from __future__ import annotations

import re
from typing import Any

from plane.client import PlaneClient
from plane.errors import HttpError

from planecli.exceptions import ResourceNotFoundError
from planecli.utils.fuzzy import find_best_match, find_matches

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)

# Matches identifiers like ABC-123
ISSUE_ID_PATTERN = re.compile(r"^([A-Z]{1,10})-(\d+)$", re.IGNORECASE)


def _is_uuid(value: str) -> bool:
    return bool(UUID_PATTERN.match(value))


def _paginate_all(list_fn, *args, **kwargs) -> list[Any]:
    """Fetch all pages from a paginated SDK method."""
    from plane.models.query_params import PaginatedQueryParams

    all_results = []
    cursor = None
    while True:
        params = PaginatedQueryParams(per_page=100, cursor=cursor)
        response = list_fn(*args, params=params, **kwargs)
        all_results.extend(response.results)
        if not response.next_page_results:
            break
        cursor = response.next_cursor
    return all_results


def resolve_project(query: str, client: PlaneClient, workspace: str) -> dict[str, Any]:
    """Resolve a project by UUID, identifier, or fuzzy name match.

    Returns the project as a dict.
    """
    # Try UUID direct lookup
    if _is_uuid(query):
        try:
            project = client.projects.retrieve(workspace, query)
            return project.model_dump()
        except HttpError:
            raise ResourceNotFoundError("Project", query)

    # Fetch all projects for matching
    projects = _paginate_all(client.projects.list, workspace)

    # Try exact identifier match (case-insensitive)
    for p in projects:
        if hasattr(p, "identifier") and p.identifier and p.identifier.upper() == query.upper():
            return p.model_dump()

    # Fuzzy name match
    match = find_best_match(query, projects, key=lambda p: p.name or "")
    if match:
        return match.item.model_dump()

    # Show suggestions
    suggestions = find_matches(query, projects, key=lambda p: p.name or "", threshold=30)
    if suggestions:
        names = ", ".join(f'"{m.matched_value}"' for m in suggestions[:3])
        raise ResourceNotFoundError("Project", f"{query} (did you mean: {names}?)")
    raise ResourceNotFoundError("Project", query)


def resolve_work_item(
    query: str, client: PlaneClient, workspace: str, project_id: str
) -> dict[str, Any]:
    """Resolve a work item by UUID, identifier (ABC-123), or fuzzy name match.

    Returns the work item as a dict.
    """
    # Try UUID direct lookup
    if _is_uuid(query):
        try:
            item = client.work_items.retrieve(workspace, project_id, query)
            return item.model_dump()
        except HttpError:
            raise ResourceNotFoundError("Work item", query)

    # Try identifier pattern (ABC-123) using SDK's retrieve_by_identifier
    id_match = ISSUE_ID_PATTERN.match(query)
    if id_match:
        project_identifier = id_match.group(1).upper()
        issue_number = int(id_match.group(2))
        try:
            item = client.work_items.retrieve_by_identifier(
                workspace, project_identifier, issue_number
            )
            return item.model_dump()
        except HttpError:
            raise ResourceNotFoundError("Work item", query)

    # Fuzzy name match - fetch all work items in project
    items = _paginate_all(client.work_items.list, workspace, project_id)

    match = find_best_match(query, items, key=lambda i: i.name or "")
    if match:
        return match.item.model_dump()

    raise ResourceNotFoundError("Work item", query)


def resolve_work_item_across_projects(
    query: str, client: PlaneClient, workspace: str
) -> tuple[dict[str, Any], str]:
    """Resolve a work item across all projects when no project is specified.

    For identifier patterns (ABC-123), extracts the project identifier and resolves directly.
    Returns (work_item_dict, project_id).
    """
    # Identifier pattern resolves directly via SDK
    id_match = ISSUE_ID_PATTERN.match(query)
    if id_match:
        project_identifier = id_match.group(1).upper()
        issue_number = int(id_match.group(2))
        try:
            item = client.work_items.retrieve_by_identifier(
                workspace, project_identifier, issue_number
            )
            item_dict = item.model_dump()
            return item_dict, item_dict.get("project", "")
        except HttpError:
            raise ResourceNotFoundError("Work item", query)

    # UUID - need project context
    if _is_uuid(query):
        # Try each project
        projects = _paginate_all(client.projects.list, workspace)
        for p in projects:
            try:
                item = client.work_items.retrieve(workspace, p.id, query)
                return item.model_dump(), p.id
            except HttpError:
                continue
        raise ResourceNotFoundError("Work item", query)

    raise ResourceNotFoundError(
        "Work item",
        f"{query} (specify --project for fuzzy name search)",
    )


def resolve_user(query: str, client: PlaneClient, workspace: str) -> dict[str, Any]:
    """Resolve a user by UUID, email, display_name, or fuzzy name match.

    Returns the user as a dict.
    """
    # Handle "me" shortcut
    if query.lower() == "me":
        me = client.users.get_me()
        return me.model_dump()

    members = client.workspaces.get_members(workspace)

    # Try UUID
    if _is_uuid(query):
        for m in members:
            if m.id == query:
                return m.model_dump()
        raise ResourceNotFoundError("User", query)

    # Try exact email match
    for m in members:
        if hasattr(m, "email") and m.email and m.email.lower() == query.lower():
            return m.model_dump()

    # Fuzzy match on display_name or first_name + last_name
    def user_name(u: Any) -> str:
        if hasattr(u, "display_name") and u.display_name:
            return u.display_name
        parts = []
        if hasattr(u, "first_name") and u.first_name:
            parts.append(u.first_name)
        if hasattr(u, "last_name") and u.last_name:
            parts.append(u.last_name)
        return " ".join(parts) if parts else ""

    match = find_best_match(query, members, key=user_name)
    if match:
        return match.item.model_dump()

    raise ResourceNotFoundError("User", query)


def resolve_module(
    query: str, client: PlaneClient, workspace: str, project_id: str
) -> dict[str, Any]:
    """Resolve a module by UUID or fuzzy name match.

    Returns the module as a dict.
    """
    if _is_uuid(query):
        try:
            module = client.modules.retrieve(workspace, project_id, query)
            return module.model_dump()
        except HttpError:
            raise ResourceNotFoundError("Module", query)

    modules = _paginate_all(client.modules.list, workspace, project_id)

    match = find_best_match(query, modules, key=lambda m: m.name or "")
    if match:
        return match.item.model_dump()

    raise ResourceNotFoundError("Module", query)


def resolve_state(
    query: str, client: PlaneClient, workspace: str, project_id: str
) -> dict[str, Any]:
    """Resolve a state by UUID or fuzzy name match.

    Returns the state as a dict.
    """
    if _is_uuid(query):
        try:
            state = client.states.retrieve(workspace, project_id, query)
            return state.model_dump()
        except HttpError:
            raise ResourceNotFoundError("State", query)

    states = _paginate_all(client.states.list, workspace, project_id)

    match = find_best_match(query, states, key=lambda s: s.name or "")
    if match:
        return match.item.model_dump()

    raise ResourceNotFoundError("State", query)


def resolve_cycle(
    query: str, client: PlaneClient, workspace: str, project_id: str
) -> dict[str, Any]:
    """Resolve a cycle by UUID or fuzzy name match.

    Returns the cycle as a dict.
    """
    if _is_uuid(query):
        try:
            cycle = client.cycles.retrieve(workspace, project_id, query)
            return cycle.model_dump()
        except HttpError:
            raise ResourceNotFoundError("Cycle", query)

    cycles = _paginate_all(client.cycles.list, workspace, project_id)

    match = find_best_match(query, cycles, key=lambda c: c.name or "")
    if match:
        return match.item.model_dump()

    raise ResourceNotFoundError("Cycle", query)


def resolve_label(
    name: str, client: PlaneClient, workspace: str, project_id: str
) -> dict[str, Any]:
    """Resolve a label by UUID or fuzzy name match.

    Returns the label as a dict.
    """
    if _is_uuid(name):
        try:
            label = client.labels.retrieve(workspace, project_id, name)
            return label.model_dump()
        except HttpError:
            raise ResourceNotFoundError("Label", name)

    labels = _paginate_all(client.labels.list, workspace, project_id)

    match = find_best_match(name, labels, key=lambda lbl: lbl.name or "")
    if match:
        return match.item.model_dump()

    raise ResourceNotFoundError("Label", name)


# ---------------------------------------------------------------------------
# Async versions -- use run_sdk() / paginate_all_async() from async_sdk
# ---------------------------------------------------------------------------


async def resolve_project_async(
    query: str, client: PlaneClient, workspace: str
) -> dict[str, Any]:
    """Async version of resolve_project."""
    from planecli.api.async_sdk import paginate_all_async, run_sdk

    if _is_uuid(query):
        try:
            project = await run_sdk(client.projects.retrieve, workspace, query)
            return project.model_dump()
        except HttpError:
            raise ResourceNotFoundError("Project", query)

    projects = await paginate_all_async(client.projects.list, workspace)

    for p in projects:
        if hasattr(p, "identifier") and p.identifier and p.identifier.upper() == query.upper():
            return p.model_dump()

    match = find_best_match(query, projects, key=lambda p: p.name or "")
    if match:
        return match.item.model_dump()

    suggestions = find_matches(query, projects, key=lambda p: p.name or "", threshold=30)
    if suggestions:
        names = ", ".join(f'"{m.matched_value}"' for m in suggestions[:3])
        raise ResourceNotFoundError("Project", f"{query} (did you mean: {names}?)")
    raise ResourceNotFoundError("Project", query)


async def resolve_work_item_async(
    query: str, client: PlaneClient, workspace: str, project_id: str
) -> dict[str, Any]:
    """Async version of resolve_work_item."""
    from planecli.api.async_sdk import paginate_all_async, run_sdk

    if _is_uuid(query):
        try:
            item = await run_sdk(client.work_items.retrieve, workspace, project_id, query)
            return item.model_dump()
        except HttpError:
            raise ResourceNotFoundError("Work item", query)

    id_match = ISSUE_ID_PATTERN.match(query)
    if id_match:
        project_identifier = id_match.group(1).upper()
        issue_number = int(id_match.group(2))
        try:
            item = await run_sdk(
                client.work_items.retrieve_by_identifier,
                workspace, project_identifier, issue_number,
            )
            return item.model_dump()
        except HttpError:
            raise ResourceNotFoundError("Work item", query)

    items = await paginate_all_async(client.work_items.list, workspace, project_id)

    match = find_best_match(query, items, key=lambda i: i.name or "")
    if match:
        return match.item.model_dump()

    raise ResourceNotFoundError("Work item", query)


async def resolve_work_item_across_projects_async(
    query: str, client: PlaneClient, workspace: str
) -> tuple[dict[str, Any], str]:
    """Async version of resolve_work_item_across_projects."""
    import asyncio

    from planecli.api.async_sdk import paginate_all_async, run_sdk

    id_match = ISSUE_ID_PATTERN.match(query)
    if id_match:
        project_identifier = id_match.group(1).upper()
        issue_number = int(id_match.group(2))
        try:
            item = await run_sdk(
                client.work_items.retrieve_by_identifier,
                workspace, project_identifier, issue_number,
            )
            item_dict = item.model_dump()
            return item_dict, item_dict.get("project", "")
        except HttpError:
            raise ResourceNotFoundError("Work item", query)

    if _is_uuid(query):
        projects = await paginate_all_async(client.projects.list, workspace)

        async def _try_project(p: Any) -> tuple[dict[str, Any], str] | None:
            try:
                item = await run_sdk(client.work_items.retrieve, workspace, p.id, query)
                return item.model_dump(), p.id
            except HttpError:
                return None

        results = await asyncio.gather(*[_try_project(p) for p in projects])
        for result in results:
            if result is not None:
                return result
        raise ResourceNotFoundError("Work item", query)

    raise ResourceNotFoundError(
        "Work item",
        f"{query} (specify --project for fuzzy name search)",
    )


async def resolve_user_async(
    query: str, client: PlaneClient, workspace: str
) -> dict[str, Any]:
    """Async version of resolve_user."""
    from planecli.api.async_sdk import run_sdk

    if query.lower() == "me":
        me = await run_sdk(client.users.get_me)
        return me.model_dump()

    members = await run_sdk(client.workspaces.get_members, workspace)

    if _is_uuid(query):
        for m in members:
            if m.id == query:
                return m.model_dump()
        raise ResourceNotFoundError("User", query)

    for m in members:
        if hasattr(m, "email") and m.email and m.email.lower() == query.lower():
            return m.model_dump()

    def user_name(u: Any) -> str:
        if hasattr(u, "display_name") and u.display_name:
            return u.display_name
        parts = []
        if hasattr(u, "first_name") and u.first_name:
            parts.append(u.first_name)
        if hasattr(u, "last_name") and u.last_name:
            parts.append(u.last_name)
        return " ".join(parts) if parts else ""

    match = find_best_match(query, members, key=user_name)
    if match:
        return match.item.model_dump()

    raise ResourceNotFoundError("User", query)


async def resolve_module_async(
    query: str, client: PlaneClient, workspace: str, project_id: str
) -> dict[str, Any]:
    """Async version of resolve_module."""
    from planecli.api.async_sdk import paginate_all_async, run_sdk

    if _is_uuid(query):
        try:
            module = await run_sdk(client.modules.retrieve, workspace, project_id, query)
            return module.model_dump()
        except HttpError:
            raise ResourceNotFoundError("Module", query)

    modules = await paginate_all_async(client.modules.list, workspace, project_id)

    match = find_best_match(query, modules, key=lambda m: m.name or "")
    if match:
        return match.item.model_dump()

    raise ResourceNotFoundError("Module", query)


async def resolve_state_async(
    query: str, client: PlaneClient, workspace: str, project_id: str
) -> dict[str, Any]:
    """Async version of resolve_state."""
    from planecli.api.async_sdk import paginate_all_async, run_sdk

    if _is_uuid(query):
        try:
            state = await run_sdk(client.states.retrieve, workspace, project_id, query)
            return state.model_dump()
        except HttpError:
            raise ResourceNotFoundError("State", query)

    states = await paginate_all_async(client.states.list, workspace, project_id)

    match = find_best_match(query, states, key=lambda s: s.name or "")
    if match:
        return match.item.model_dump()

    raise ResourceNotFoundError("State", query)


async def resolve_cycle_async(
    query: str, client: PlaneClient, workspace: str, project_id: str
) -> dict[str, Any]:
    """Async version of resolve_cycle."""
    from planecli.api.async_sdk import paginate_all_async, run_sdk

    if _is_uuid(query):
        try:
            cycle = await run_sdk(client.cycles.retrieve, workspace, project_id, query)
            return cycle.model_dump()
        except HttpError:
            raise ResourceNotFoundError("Cycle", query)

    cycles = await paginate_all_async(client.cycles.list, workspace, project_id)

    match = find_best_match(query, cycles, key=lambda c: c.name or "")
    if match:
        return match.item.model_dump()

    raise ResourceNotFoundError("Cycle", query)


async def resolve_label_async(
    name: str, client: PlaneClient, workspace: str, project_id: str
) -> dict[str, Any]:
    """Async version of resolve_label."""
    from planecli.api.async_sdk import paginate_all_async, run_sdk

    if _is_uuid(name):
        try:
            label = await run_sdk(client.labels.retrieve, workspace, project_id, name)
            return label.model_dump()
        except HttpError:
            raise ResourceNotFoundError("Label", name)

    labels = await paginate_all_async(client.labels.list, workspace, project_id)

    match = find_best_match(name, labels, key=lambda lbl: lbl.name or "")
    if match:
        return match.item.model_dump()

    raise ResourceNotFoundError("Label", name)
