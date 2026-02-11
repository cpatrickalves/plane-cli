"""Async wrapper for synchronous plane-sdk calls.

Uses asyncio.to_thread() to run blocking SDK calls in a thread pool,
and asyncio.Semaphore to limit concurrent API calls.
"""

from __future__ import annotations

import asyncio
from typing import Any

from plane.client import PlaneClient

from planecli.api.client import get_config

# Limit concurrent API calls to prevent rate limiting
_api_semaphore = asyncio.Semaphore(10)


async def run_sdk(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a sync SDK function in a thread pool with concurrency limiting."""
    async with _api_semaphore:
        return await asyncio.to_thread(fn, *args, **kwargs)


def create_client() -> PlaneClient:
    """Create a fresh PlaneClient for thread-safe concurrent use.

    Each concurrent batch should use its own client instance to avoid
    sharing requests.Session objects across threads.
    """
    config = get_config()
    return PlaneClient(base_url=config.base_url, api_key=config.api_key)


async def paginate_all_async(list_fn: Any, *args: Any, **kwargs: Any) -> list[Any]:
    """Async version of _paginate_all -- runs entire pagination in a thread."""
    from planecli.utils.resolve import _paginate_all

    return await run_sdk(_paginate_all, list_fn, *args, **kwargs)
