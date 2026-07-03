# Architecture

## Overview

PlaneCLI is a Python command-line interface for [Plane.so](https://plane.so) (SaaS or self-hosted). Its defining feature is **fuzzy resource resolution**: any resource — project, work item, cycle, module, label, state, user — can be referenced by name, identifier (`ABC-123`), or UUID, and the CLI resolves it to the underlying record before making a change.

The codebase is organized as a set of thin layers. A command never talks to the Plane SDK directly; every request flows through resolution, an async wrapper, and a cache before reaching the network, and every result flows back through a formatter that separates human output from machine output.

## Request Flow

```
command  →  resolve  →  async SDK wrapper  →  (cache | Plane SDK)  →  formatter
```

1. **command** (`commands/<resource>.py`) — a cyclopts subcommand parses flags and orchestrates the work. All command functions are `async`.
2. **resolve** (`utils/resolve.py`) — turns a user-supplied name/identifier/UUID into a concrete record. See [ADR-0002](adr/0002-fuzzy-resource-resolution.md).
3. **async SDK wrapper** (`api/async_sdk.py`) — runs the synchronous Plane SDK in a thread pool, bounded by a semaphore, with automatic retry on transient errors. See [ADR-0001](adr/0001-async-wrapper-over-sync-sdk.md).
4. **cache** (`cache.py`) — read-through disk cache for slowly-changing resource lists. See [ADR-0004](adr/0004-disk-cache-ttls-and-keys.md) and [caching.md](caching.md).
5. **formatter** (`formatters/`) — renders a Rich table to **stderr** or JSON to **stdout**. See [ADR-0005](adr/0005-dual-output-contract.md).

## Components

**`app.py`** — the root cyclopts `App`. Registers every sub-app (`project_app`, `wi_app`, …) and defines `main()`, the entry point. `main()` strips the global `--verbose`/`-v` and `--no-cache` flags from `sys.argv` *before* cyclopts parses (cyclopts does not own these), configures logging and the cache, runs the app, and translates any `PlaneCLIError` into a formatted message plus exit code.

**`commands/`** — one module per resource, each exposing a `cyclopts.App` with `list`/`show`/`create`/`update`/`delete` subcommands. This is where new features are added.

**`utils/resolve.py`** — the resolution layer. Each resource has a `resolve_<x>` / `resolve_<x>_async` pair that tries **UUID → identifier → fuzzy name** in that order. Commands call the `_async` versions, which read through the cache.

**`api/`** — `client.py` holds the `PlaneClient` singleton (`get_client`) plus `get_config`/`get_workspace`; `async_sdk.py` wraps the blocking SDK.

**`cache.py`** — the disk cache (cashews). One `cached_list_<x>` per resource, returning plain dicts. TTLs vary by volatility.

**`formatters/`** — `output()` (lists) and `output_single()` (records).

**`exceptions.py`** — `PlaneCLIError` subclasses carrying `message`, `hint`, and `exit_code` (Auth=2, NotFound=3, API=4, Validation=5).

**`utils/fuzzy.py`** — rapidfuzz `token_sort_ratio` matching with a default threshold of 60.

## Data Flow — resolving and updating a work item

`planecli wi update ABC-123 --state "review"`:

1. The `wi update` command resolves `ABC-123`. Because it matches the `ABC-123` identifier pattern, `resolve_work_item_async` fetches it directly via the raw SDK path (bypassing broken SDK validation — see [ADR-0003](adr/0003-sdk-escape-hatches.md)).
2. `--state "review"` is resolved: `resolve_state_async` reads the project's **cached** state list and fuzzy-matches "review" to "In Review".
3. The update call runs through `run_sdk()` — in a thread, rate-limited, retried on 429/5xx.
4. The relevant cache entry is invalidated via `invalidate_resource(...)`.
5. The result is rendered as a table (stderr) or JSON (stdout).

## Key Decisions

Major architecture decisions are documented as ADRs in [docs/adr/](adr/):

- [ADR-0001](adr/0001-async-wrapper-over-sync-sdk.md) — Async wrapper over the synchronous Plane SDK
- [ADR-0002](adr/0002-fuzzy-resource-resolution.md) — Fuzzy resource resolution (UUID → identifier → name)
- [ADR-0003](adr/0003-sdk-escape-hatches.md) — SDK escape hatches for API/model mismatches
- [ADR-0004](adr/0004-disk-cache-ttls-and-keys.md) — Disk cache with volatility-based TTLs and instance-scoped keys
- [ADR-0005](adr/0005-dual-output-contract.md) — Dual output contract (table → stderr, JSON → stdout)

## External Dependencies

| Service / Library | Purpose |
|---|---|
| [Plane.so API](https://developers.plane.so) | The system of record for all resources |
| [plane-sdk](https://github.com/makeplane/plane-python-sdk) | Official Python SDK (wrapped, never called directly from commands) |
| [cyclopts](https://cyclopts.readthedocs.io/) | CLI framework |
| [rapidfuzz](https://github.com/rapidfuzz/RapidFuzz) | Fuzzy matching |
| [cashews](https://github.com/Krukov/cashews) | Disk-based response cache |
| [tenacity](https://tenacity.readthedocs.io/) | Retry on transient errors |
| [Rich](https://rich.readthedocs.io/) | Table rendering |
