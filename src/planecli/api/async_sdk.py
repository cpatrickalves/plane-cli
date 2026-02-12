"""Async wrapper for synchronous plane-sdk calls.

Uses asyncio.to_thread() to run blocking SDK calls in a thread pool,
asyncio.Semaphore to limit concurrent API calls, and tenacity for
automatic retry on transient errors (429, 502, 503, 504).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from plane.client import PlaneClient
from plane.errors import HttpError
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from planecli.api.client import get_config

logger = logging.getLogger(__name__)

# Limit concurrent API calls to prevent rate limiting
_api_semaphore = asyncio.Semaphore(10)


def _is_retryable(exc: BaseException) -> bool:
    """Check if an exception is retryable (429 or 502/503/504)."""
    if isinstance(exc, HttpError):
        return exc.status_code == 429 or exc.status_code in (502, 503, 504)
    return False


def _log_retry(retry_state: RetryCallState) -> None:
    """Log retry attempts via logging (stderr)."""
    logger.warning(
        "Rate limited, retrying (%d/%d) in %.1fs...",
        retry_state.attempt_number,
        5,
        retry_state.idle_for,
    )


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(5),
    before_sleep=_log_retry,
    reraise=True,
)
async def run_sdk(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a sync SDK function in a thread pool with concurrency limiting and retry."""
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
