"""Disk-based caching for API responses using cashews."""

from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path
from typing import Any, Awaitable, Callable

from cashews import Cache
from loguru import logger

cache = Cache()

# TTL constants
TTL_STATIC = "1h"  # members
TTL_CONFIG = "10m"  # states, labels
TTL_MODERATE = "5m"  # projects, modules, cycles
TTL_WORK_ITEMS = "2m"  # work items: short TTL to avoid stale data

# Module-level flag for --no-cache behavior
_no_cache = False


def get_cache_dir() -> Path:
    """Get platform-appropriate cache directory."""
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Caches" / "planecli"
    # Linux / other
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "planecli"
    return Path.home() / ".cache" / "planecli"


def setup_cache(*, enable: bool = True) -> None:
    """Initialize the cache backend.

    Args:
        enable: If False, cache operations become no-ops.
    """
    if not enable:
        cache.setup("mem://", size=0)
        return
    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    Mb = 1048576
    cache.setup(
        "disk://",
        directory=str(cache_dir),
        size_limit=100 * Mb,
        shards=0,
    )


def set_no_cache(value: bool) -> None:
    """Set the no-cache flag (skip reads, still write)."""
    global _no_cache
    _no_cache = value


def _url_hash() -> str:
    """Short hash of base_url for key scoping across Plane instances."""
    from planecli.api.client import get_config

    config = get_config()
    return hashlib.sha256(config.base_url.encode()).hexdigest()[:12]


def _cache_key(resource: str, workspace: str, project_id: str | None = None) -> str:
    """Build a cache key."""
    url_hash = _url_hash()
    if project_id:
        return f"{url_hash}:{resource}:{workspace}:{project_id}"
    return f"{url_hash}:{resource}:{workspace}"


async def _cached_list(
    key: str,
    ttl: str,
    fetch_fn: Callable[[], Awaitable[list[Any]]],
) -> list[dict[str, Any]]:
    """Generic cached list fetch.

    On cache hit: returns cached data (list of dicts).
    On miss: calls fetch_fn(), converts to dicts via model_dump(), stores, and returns.
    Respects the --no-cache flag (skip reads, still write).
    """
    # Try cache read (unless --no-cache)
    if not _no_cache:
        try:
            cached = await cache.get(key)
            if cached is not None:
                return cached
        except Exception as exc:
            logger.warning("Cache read error, fetching from API: {}", exc)

    # Cache miss or --no-cache: fetch from API
    results = await fetch_fn()

    # Convert Pydantic models to dicts
    data = [item.model_dump() if hasattr(item, "model_dump") else item for item in results]

    # Store in cache
    try:
        await cache.set(key, data, expire=ttl)
    except Exception as exc:
        logger.warning("Cache write error: {}", exc)

    return data


# --- Cached fetch functions ---
# Each uses create_client() for thread-safe API calls (only on cache miss).


async def cached_list_projects(workspace: str) -> list[dict[str, Any]]:
    """Fetch projects with caching (TTL: 5m)."""
    from planecli.api.async_sdk import create_client, paginate_all_async

    key = _cache_key("projects", workspace)

    async def _fetch() -> list[Any]:
        client = create_client()
        return await paginate_all_async(client.projects.list, workspace)

    return await _cached_list(key, TTL_MODERATE, _fetch)


async def cached_list_members(workspace: str) -> list[dict[str, Any]]:
    """Fetch workspace members with caching (TTL: 1h)."""
    from planecli.api.async_sdk import create_client, run_sdk

    key = _cache_key("members", workspace)

    async def _fetch() -> list[Any]:
        client = create_client()
        return await run_sdk(client.workspaces.get_members, workspace)

    return await _cached_list(key, TTL_STATIC, _fetch)


async def cached_list_states(workspace: str, project_id: str) -> list[dict[str, Any]]:
    """Fetch states with caching (TTL: 10m)."""
    from planecli.api.async_sdk import create_client, paginate_all_async

    key = _cache_key("states", workspace, project_id)

    async def _fetch() -> list[Any]:
        client = create_client()
        return await paginate_all_async(client.states.list, workspace, project_id)

    return await _cached_list(key, TTL_CONFIG, _fetch)


async def cached_list_labels(workspace: str, project_id: str) -> list[dict[str, Any]]:
    """Fetch labels with caching (TTL: 10m)."""
    from planecli.api.async_sdk import create_client, paginate_all_async

    key = _cache_key("labels", workspace, project_id)

    async def _fetch() -> list[Any]:
        client = create_client()
        return await paginate_all_async(client.labels.list, workspace, project_id)

    return await _cached_list(key, TTL_CONFIG, _fetch)


async def cached_list_estimate_points(
    workspace: str, project_id: str
) -> list[dict[str, Any]]:
    """Fetch estimate points by expanding them from work items (TTL: 10m).

    Plane's external API has no dedicated endpoint for estimate points.
    Instead, we fetch work items with expand=estimate_point and extract
    the unique {id, value} pairs from the expanded data.
    """
    from planecli.api.async_sdk import create_client, run_sdk

    key = _cache_key("estimate_points", workspace, project_id)

    async def _fetch() -> list[Any]:
        # Use raw _get() to bypass SDK Pydantic validation which fails
        # when estimate_point is expanded from str to dict.
        client = create_client()
        raw = await run_sdk(
            client.work_items._get,
            f"{workspace}/projects/{project_id}/work-items",
            {"expand": "estimate_point", "per_page": "100"},
        )
        items = raw.get("results", []) if isinstance(raw, dict) else raw

        seen: dict[str, str] = {}
        for item in items:
            ep = item.get("estimate_point")
            if isinstance(ep, dict) and ep.get("id") and ep.get("value"):
                seen[ep["id"]] = ep["value"]

        return [{"id": uid, "value": val} for uid, val in seen.items()]

    return await _cached_list(key, TTL_CONFIG, _fetch)


async def cached_list_work_items(workspace: str, project_id: str) -> list[dict[str, Any]]:
    """Fetch work items with short-lived caching (TTL: 2m).

    Work items change more frequently than states/labels, but caching for 2min
    avoids repeated API calls when running wi ls multiple times in sequence.
    """
    from planecli.api.async_sdk import create_client, paginate_all_async

    key = _cache_key("work_items", workspace, project_id)

    async def _fetch() -> list[Any]:
        client = create_client()
        return await paginate_all_async(client.work_items.list, workspace, project_id)

    return await _cached_list(key, TTL_WORK_ITEMS, _fetch)


async def cached_get_me(workspace: str) -> dict[str, Any]:
    """Cache the current user (TTL: 1h)."""
    from planecli.api.async_sdk import create_client, run_sdk

    key = _cache_key("me", workspace)

    async def _fetch() -> list[Any]:
        client = create_client()
        me = await run_sdk(client.users.get_me)
        return [me]  # Wrap in list for _cached_list compatibility

    result = await _cached_list(key, TTL_STATIC, _fetch)
    return result[0] if result else {}


async def cached_list_modules(workspace: str, project_id: str) -> list[dict[str, Any]]:
    """Fetch modules with caching (TTL: 5m)."""
    from planecli.api.async_sdk import create_client, paginate_all_async

    key = _cache_key("modules", workspace, project_id)

    async def _fetch() -> list[Any]:
        client = create_client()
        return await paginate_all_async(client.modules.list, workspace, project_id)

    return await _cached_list(key, TTL_MODERATE, _fetch)


async def cached_list_cycles(workspace: str, project_id: str) -> list[dict[str, Any]]:
    """Fetch cycles with caching (TTL: 5m)."""
    from planecli.api.async_sdk import create_client, paginate_all_async

    key = _cache_key("cycles", workspace, project_id)

    async def _fetch() -> list[Any]:
        client = create_client()
        return await paginate_all_async(client.cycles.list, workspace, project_id)

    return await _cached_list(key, TTL_MODERATE, _fetch)


# --- Invalidation ---


async def invalidate_resource(
    resource: str, workspace: str, project_id: str | None = None
) -> None:
    """Invalidate a specific cached resource."""
    key = _cache_key(resource, workspace, project_id)
    try:
        await cache.delete(key)
    except Exception as exc:
        logger.warning("Cache invalidation error: {}", exc)


async def invalidate_all() -> None:
    """Clear the entire cache."""
    try:
        await cache.clear()
    except Exception:
        # Fallback: delete cache directory
        import shutil

        cache_dir = get_cache_dir()
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)
