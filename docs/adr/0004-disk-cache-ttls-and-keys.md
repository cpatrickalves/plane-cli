---
status: accepted
date: 2026-07-03
decision-makers: PlaneCLI maintainers
---

# ADR-0004: Disk cache with volatility-based TTLs and instance-scoped keys

## Context and Problem Statement

Fuzzy resolution ([ADR-0002](0002-fuzzy-resource-resolution.md)) means that most commands must fetch full lists of projects, states, labels, and members to match a name. Without caching, a single `wi list` across 10 projects can trigger 30+ API calls, and running the CLI repeatedly re-fetches the same slowly-changing data every time. We want to eliminate that redundant traffic — but a naive cache introduces two hazards: serving **stale** data (a state that was renamed, a member who left), and serving data from the **wrong Plane instance** when a user switches between a SaaS and a self-hosted workspace.

## Considered Options

- **A. Read-through disk cache, TTL tuned per resource by volatility, keys scoped by `base_url`.**
- **B. In-memory cache only** (per-process).
- **C. No cache** — always hit the API.

## Decision Outcome

Chosen option: **A**, because the CLI is invoked as many short-lived processes, so caching must survive across invocations (rules out B), and correctness demands both freshness tiers and instance isolation.

Implemented in `cache.py` with [cashews](https://github.com/Krukov/cashews) over a SQLite-backed disk store, capped at **100 MB** with LRU eviction. The cache directory is platform-appropriate (`~/Library/Caches/planecli` on macOS; `$XDG_CACHE_HOME/planecli` or `~/.cache/planecli` on Linux).

**TTLs follow a volatility gradient** — the more often a resource changes, the shorter its lifetime:

| Tier | TTL | Resources |
|------|-----|-----------|
| `TTL_STATIC` | 1h | members, current user (`me`) |
| `TTL_MODERATE` | 5m | projects, modules, cycles |
| `TTL_CONFIG` | 10m | states, labels, estimate points |
| `TTL_WORK_ITEMS` | 2m | work items |
| `TTL_COMMENTS` | 1m | a work item's comments (scoped per item) |

Comments get the shortest TTL because they are the most volatile; work items follow at 2m. A short window still collapses repeated reads of the same list (`wi list`) or item (`wi show`, `comment ls`). Documents and single-resource lookups by UUID/identifier are **not** cached — they must always be fresh.

**Keys are scoped by a hash of `base_url`** so two Plane instances never collide. The key format is `{sha256(base_url)[:12]}:{resource}:{workspace}[:{project_id}[:{item_id}]]`. The optional `item_id` level was added so per-item resources (comments) cache independently of one another; only comments use it today.

**Invalidation** is explicit after writes: every create/update/delete calls `invalidate_resource("<resource>", workspace, project_id)`; `configure` clears the whole cache because credentials (and thus the instance) may have changed. `--no-cache` (or `PLANECLI_NO_CACHE=1`) skips reads but still writes, so the next run is warm.

**Cache failures never block the CLI.** Read/write/invalidate errors are caught, logged as a warning to stderr, and the command falls back to a direct API call.

### Pros and Cons of the Options

#### A. Read-through disk cache, per-resource TTL, url-scoped keys
- Good, because it survives across process invocations and cuts >80% of warm-run calls.
- Good, because volatility tiers bound staleness and url-scoping prevents cross-instance bleed.
- Bad, because a resource changed on the server can be up to its TTL out of date until it expires or a write invalidates it.

#### B. In-memory cache only
- Good, because it is simple and always instance-correct within a process.
- Bad, because each CLI invocation is a new process, so nothing is reused between commands — the common case.

#### C. No cache
- Good, because data is always fresh.
- Bad, because fuzzy resolution makes every command fan out into many list fetches, which is slow and rate-limit-prone.

## Consequences

**Positive:**
- Warm runs eliminate the large majority of API calls; the CLI feels responsive.
- Switching instances is safe; stale write results are corrected by explicit invalidation.

**Negative:**
- Read data can lag reality by up to its TTL when the change originated outside this CLI (e.g., someone renamed a state in the web UI).
- Members and the current user rely on TTL expiry only (they are never mutated via the CLI).

**Neutral:**
- Estimate points share the 10-minute `TTL_CONFIG` tier and are derived, not fetched (see [ADR-0003](0003-sdk-escape-hatches.md)).

## Confirmation

The TTL constants and `_cache_key()` in `cache.py` are the single source of truth for lifetimes and scoping. `tests/test_cache.py` (run against a `mem://` backend) covers hit/miss/invalidation behavior. User-facing details live in [docs/caching.md](../caching.md).
