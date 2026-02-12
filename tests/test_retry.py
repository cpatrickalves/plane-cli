"""Tests for retry logic on rate-limited API calls."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from plane.errors import HttpError
from tenacity import wait_none

from planecli.api.async_sdk import run_sdk
from planecli.utils.resolve import _fetch_page, _paginate_all


def _make_http_error(status_code: int, message: str = "") -> HttpError:
    return HttpError(message or f"HTTP {status_code}", status_code=status_code)


@pytest.fixture(autouse=True)
def _fast_retry():
    """Patch tenacity wait to zero for fast tests."""
    original_wait = run_sdk.retry.wait
    original_page_wait = _fetch_page.retry.wait
    run_sdk.retry.wait = wait_none()
    _fetch_page.retry.wait = wait_none()
    yield
    run_sdk.retry.wait = original_wait
    _fetch_page.retry.wait = original_page_wait


class TestRunSdkRetry:
    """Test retry behavior in run_sdk."""

    async def test_retries_on_429_then_succeeds(self):
        """429 on first call, success on second."""
        fn = MagicMock(side_effect=[_make_http_error(429), "ok"])
        result = await run_sdk(fn)
        assert result == "ok"
        assert fn.call_count == 2

    async def test_no_retry_on_404(self):
        """Non-retryable errors propagate immediately."""
        fn = MagicMock(side_effect=_make_http_error(404))
        with pytest.raises(HttpError) as exc_info:
            await run_sdk(fn)
        assert exc_info.value.status_code == 404
        assert fn.call_count == 1

    async def test_no_retry_on_401(self):
        """Auth errors propagate immediately."""
        fn = MagicMock(side_effect=_make_http_error(401))
        with pytest.raises(HttpError) as exc_info:
            await run_sdk(fn)
        assert exc_info.value.status_code == 401
        assert fn.call_count == 1

    async def test_exhausted_retries_reraise(self):
        """After max attempts, the original HttpError is re-raised."""
        fn = MagicMock(side_effect=_make_http_error(429))
        with pytest.raises(HttpError) as exc_info:
            await run_sdk(fn)
        assert exc_info.value.status_code == 429
        assert fn.call_count == 5

    async def test_retries_on_502(self):
        """502 Bad Gateway is retried."""
        fn = MagicMock(side_effect=[_make_http_error(502), "ok"])
        result = await run_sdk(fn)
        assert result == "ok"

    async def test_retries_on_503(self):
        """503 Service Unavailable is retried."""
        fn = MagicMock(side_effect=[_make_http_error(503), "ok"])
        result = await run_sdk(fn)
        assert result == "ok"

    async def test_retries_on_504(self):
        """504 Gateway Timeout is retried."""
        fn = MagicMock(side_effect=[_make_http_error(504), "ok"])
        result = await run_sdk(fn)
        assert result == "ok"

    async def test_no_retry_on_500(self):
        """500 Internal Server Error is NOT retried."""
        fn = MagicMock(side_effect=_make_http_error(500))
        with pytest.raises(HttpError):
            await run_sdk(fn)
        assert fn.call_count == 1

    async def test_success_without_retry(self):
        """Normal calls work without triggering retry logic."""
        fn = MagicMock(return_value="result")
        result = await run_sdk(fn)
        assert result == "result"
        assert fn.call_count == 1


class TestPaginateAllRetry:
    """Test per-page retry in _paginate_all."""

    def test_retries_single_page_429(self):
        """429 on a pagination page retries just that page."""
        page1 = MagicMock(results=["a", "b"], next_page_results=True, next_cursor="c1")
        page2_ok = MagicMock(results=["c"], next_page_results=False)

        list_fn = MagicMock(side_effect=[page1, _make_http_error(429), page2_ok])
        result = _paginate_all(list_fn)
        assert result == ["a", "b", "c"]
        assert list_fn.call_count == 3

    def test_no_retry_on_404_during_pagination(self):
        """Non-retryable errors propagate during pagination."""
        list_fn = MagicMock(side_effect=_make_http_error(404))
        with pytest.raises(HttpError) as exc_info:
            _paginate_all(list_fn)
        assert exc_info.value.status_code == 404
        assert list_fn.call_count == 1

    def test_single_page_no_retry_needed(self):
        """Normal pagination works without retry."""
        page1 = MagicMock(results=["a", "b"], next_page_results=False)
        list_fn = MagicMock(side_effect=[page1])
        result = _paginate_all(list_fn)
        assert result == ["a", "b"]
        assert list_fn.call_count == 1
