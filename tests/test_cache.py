"""Tests for the disk-based API cache module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from planecli.cache import (
    _cache_key,
    _cached_list,
    cache,
    cached_list_cycles,
    cached_list_labels,
    cached_list_members,
    cached_list_modules,
    cached_list_projects,
    cached_list_states,
    get_cache_dir,
    invalidate_all,
    invalidate_resource,
    set_no_cache,
)

# --- Helpers ---


def _make_model(data: dict) -> MagicMock:
    """Create a mock Pydantic model with model_dump()."""
    m = MagicMock()
    m.model_dump.return_value = data
    for k, v in data.items():
        setattr(m, k, v)
    return m


# --- Tests for get_cache_dir ---


def test_get_cache_dir_macos():
    with patch("planecli.cache.platform.system", return_value="Darwin"):
        d = get_cache_dir()
    assert "Library/Caches/planecli" in str(d)


def test_get_cache_dir_linux():
    with patch("planecli.cache.platform.system", return_value="Linux"):
        with patch.dict("os.environ", {}, clear=True):
            d = get_cache_dir()
    assert ".cache/planecli" in str(d)


def test_get_cache_dir_linux_xdg():
    with patch("planecli.cache.platform.system", return_value="Linux"):
        with patch.dict("os.environ", {"XDG_CACHE_HOME": "/custom/cache"}):
            d = get_cache_dir()
    assert str(d) == "/custom/cache/planecli"


# --- Tests for _cache_key ---


@patch("planecli.cache._url_hash", return_value="abc123")
def test_cache_key_without_project(mock_hash):
    key = _cache_key("projects", "my-workspace")
    assert key == "abc123:projects:my-workspace"


@patch("planecli.cache._url_hash", return_value="abc123")
def test_cache_key_with_project(mock_hash):
    key = _cache_key("states", "my-workspace", "proj-uuid")
    assert key == "abc123:states:my-workspace:proj-uuid"


# --- Tests for _cached_list ---


@patch("planecli.cache._url_hash", return_value="abc123")
async def test_cached_list_miss_then_hit(mock_hash):
    """First call fetches from API (miss), second returns from cache (hit)."""
    model = _make_model({"id": "1", "name": "Test Project"})
    fetch_fn = AsyncMock(return_value=[model])

    # First call: cache miss
    result1 = await _cached_list("test:key", "5m", fetch_fn)
    assert result1 == [{"id": "1", "name": "Test Project"}]
    assert fetch_fn.call_count == 1

    # Second call: cache hit (fetch_fn not called again)
    result2 = await _cached_list("test:key", "5m", fetch_fn)
    assert result2 == [{"id": "1", "name": "Test Project"}]
    assert fetch_fn.call_count == 1


@patch("planecli.cache._url_hash", return_value="abc123")
async def test_cached_list_no_cache_flag(mock_hash):
    """--no-cache skips reads but still writes."""
    model = _make_model({"id": "1", "name": "Fresh"})
    fetch_fn = AsyncMock(return_value=[model])

    # Seed the cache
    await cache.set("nocache:key", [{"id": "0", "name": "Stale"}], expire="5m")

    # With --no-cache, should skip cache and fetch fresh
    set_no_cache(True)
    result = await _cached_list("nocache:key", "5m", fetch_fn)
    assert result == [{"id": "1", "name": "Fresh"}]
    assert fetch_fn.call_count == 1

    # The fresh data should now be in cache
    set_no_cache(False)
    result2 = await _cached_list("nocache:key", "5m", fetch_fn)
    assert result2 == [{"id": "1", "name": "Fresh"}]
    # fetch_fn still called only once total (cache hit now)
    assert fetch_fn.call_count == 1


@patch("planecli.cache._url_hash", return_value="abc123")
async def test_cached_list_handles_fetch_with_plain_dicts(mock_hash):
    """Items without model_dump are stored as-is."""
    fetch_fn = AsyncMock(return_value=[{"id": "1", "name": "Dict Item"}])

    result = await _cached_list("dict:key", "5m", fetch_fn)
    assert result == [{"id": "1", "name": "Dict Item"}]


# --- Tests for cached_list_* functions ---
# Patch at the source module (planecli.api.async_sdk) since cached functions
# import create_client/paginate_all_async/run_sdk inside their function bodies.


@patch("planecli.cache._url_hash", return_value="abc123")
@patch("planecli.api.async_sdk.create_client")
@patch("planecli.api.async_sdk.paginate_all_async")
async def test_cached_list_projects(mock_paginate, mock_create_client, mock_hash):
    project = _make_model({"id": "p1", "name": "My Project", "identifier": "MP"})
    mock_paginate.return_value = [project]

    result = await cached_list_projects("my-ws")
    assert len(result) == 1
    assert result[0]["name"] == "My Project"

    # Second call should hit cache
    result2 = await cached_list_projects("my-ws")
    assert result2 == result
    assert mock_paginate.call_count == 1  # only called once


@patch("planecli.cache._url_hash", return_value="abc123")
@patch("planecli.api.async_sdk.create_client")
@patch("planecli.api.async_sdk.run_sdk", new_callable=AsyncMock)
async def test_cached_list_members(mock_run_sdk, mock_create_client, mock_hash):
    member = _make_model({
        "id": "u1",
        "display_name": "Alice",
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice@example.com",
    })
    mock_run_sdk.return_value = [member]

    result = await cached_list_members("my-ws")
    assert len(result) == 1
    assert result[0]["display_name"] == "Alice"

    # Second call should hit cache
    result2 = await cached_list_members("my-ws")
    assert result2 == result
    assert mock_run_sdk.call_count == 1


@patch("planecli.cache._url_hash", return_value="abc123")
@patch("planecli.api.async_sdk.create_client")
@patch("planecli.api.async_sdk.paginate_all_async")
async def test_cached_list_states(mock_paginate, mock_create_client, mock_hash):
    state = _make_model({"id": "s1", "name": "Todo", "color": "#000", "group": "unstarted"})
    mock_paginate.return_value = [state]

    result = await cached_list_states("my-ws", "proj-1")
    assert result[0]["name"] == "Todo"

    result2 = await cached_list_states("my-ws", "proj-1")
    assert result2 == result
    assert mock_paginate.call_count == 1


@patch("planecli.cache._url_hash", return_value="abc123")
@patch("planecli.api.async_sdk.create_client")
@patch("planecli.api.async_sdk.paginate_all_async")
async def test_cached_list_labels(mock_paginate, mock_create_client, mock_hash):
    label = _make_model({"id": "l1", "name": "Bug", "color": "#f00"})
    mock_paginate.return_value = [label]

    result = await cached_list_labels("my-ws", "proj-1")
    assert result[0]["name"] == "Bug"
    assert mock_paginate.call_count == 1


@patch("planecli.cache._url_hash", return_value="abc123")
@patch("planecli.api.async_sdk.create_client")
@patch("planecli.api.async_sdk.paginate_all_async")
async def test_cached_list_modules(mock_paginate, mock_create_client, mock_hash):
    module = _make_model({"id": "m1", "name": "Sprint 1"})
    mock_paginate.return_value = [module]

    result = await cached_list_modules("my-ws", "proj-1")
    assert result[0]["name"] == "Sprint 1"
    assert mock_paginate.call_count == 1


@patch("planecli.cache._url_hash", return_value="abc123")
@patch("planecli.api.async_sdk.create_client")
@patch("planecli.api.async_sdk.paginate_all_async")
async def test_cached_list_cycles(mock_paginate, mock_create_client, mock_hash):
    cycle = _make_model({"id": "c1", "name": "Cycle 1"})
    mock_paginate.return_value = [cycle]

    result = await cached_list_cycles("my-ws", "proj-1")
    assert result[0]["name"] == "Cycle 1"
    assert mock_paginate.call_count == 1


# --- Tests for invalidation ---


@patch("planecli.cache._url_hash", return_value="abc123")
async def test_invalidate_resource(mock_hash):
    """invalidate_resource removes the specific cache entry."""
    await cache.set("abc123:states:ws:p1", [{"id": "s1"}], expire="10m")

    # Verify it's there
    cached = await cache.get("abc123:states:ws:p1")
    assert cached is not None

    await invalidate_resource("states", "ws", "p1")

    # Verify it's gone
    cached = await cache.get("abc123:states:ws:p1")
    assert cached is None


async def test_invalidate_all():
    """invalidate_all clears the entire cache."""
    await cache.set("key1", "value1", expire="5m")
    await cache.set("key2", "value2", expire="5m")

    await invalidate_all()

    assert await cache.get("key1") is None
    assert await cache.get("key2") is None


# --- Tests for cache error recovery ---


@patch("planecli.cache._url_hash", return_value="abc123")
async def test_cache_read_error_falls_back_to_api(mock_hash, capsys):
    """If cache.get raises, fall back to API fetch."""
    model = _make_model({"id": "1", "name": "Fallback"})
    fetch_fn = AsyncMock(return_value=[model])

    with patch.object(cache, "get", side_effect=Exception("SQLite corrupted")):
        result = await _cached_list("broken:key", "5m", fetch_fn)

    assert result == [{"id": "1", "name": "Fallback"}]
    assert fetch_fn.call_count == 1
    captured = capsys.readouterr()
    assert "Cache read error" in captured.err


@patch("planecli.cache._url_hash", return_value="abc123")
async def test_cache_write_error_still_returns_data(mock_hash, capsys):
    """If cache.set raises, data is still returned from API."""
    model = _make_model({"id": "1", "name": "WriteError"})
    fetch_fn = AsyncMock(return_value=[model])

    with patch.object(cache, "set", side_effect=Exception("Disk full")):
        result = await _cached_list("writeerr:key", "5m", fetch_fn)

    assert result == [{"id": "1", "name": "WriteError"}]
    captured = capsys.readouterr()
    assert "Cache write error" in captured.err


# --- Tests for different workspaces/projects isolation ---


@patch("planecli.cache._url_hash", return_value="abc123")
async def test_different_projects_have_separate_cache(mock_hash):
    """States for different projects are cached independently."""
    await cache.set("abc123:states:ws:proj-A", [{"id": "sA"}], expire="10m")
    await cache.set("abc123:states:ws:proj-B", [{"id": "sB"}], expire="10m")

    result_a = await cache.get("abc123:states:ws:proj-A")
    result_b = await cache.get("abc123:states:ws:proj-B")
    assert result_a == [{"id": "sA"}]
    assert result_b == [{"id": "sB"}]
