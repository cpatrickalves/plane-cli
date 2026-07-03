---
status: accepted
date: 2026-07-03
decision-makers: PlaneCLI maintainers
---

# ADR-0001: Async wrapper over the synchronous Plane SDK

## Context and Problem Statement

The official `plane-sdk` is fully synchronous: every method issues a blocking HTTP request via `requests`. A single PlaneCLI command frequently needs many such calls — for example, `wi list` with no `--project` fetches work items for every project in the workspace, and resolving `--assignee`/`--state`/`--labels` each needs a resource list. Doing these one at a time is slow, and firing them all at once risks hitting Plane's rate limits (HTTP 429) and transient gateway errors (502/503/504). We need a way to run blocking SDK calls concurrently, bound the concurrency, and survive transient failures — without rewriting the SDK or making commands aware of any of it.

## Considered Options

- **A. Wrap the sync SDK in an async helper** (`asyncio.to_thread` + `asyncio.Semaphore` + tenacity retry).
- **B. Call the SDK synchronously** and parallelize with a `ThreadPoolExecutor` where needed.
- **C. Replace `plane-sdk` with a hand-written async HTTP client** (`httpx`).

## Decision Outcome

Chosen option: **A**, because it keeps the official SDK (and its models) while letting every command be `async` and issue concurrent, rate-limited, self-healing requests through a single choke point.

The wrapper lives in `api/async_sdk.py`:

- `run_sdk(fn, *args, **kwargs)` runs a blocking SDK call in a thread pool (`asyncio.to_thread`), gated by a module-level `asyncio.Semaphore(4)` so at most 4 requests are in flight at once.
- It is decorated with tenacity `@retry`: retry when the exception is an `HttpError` with status `429` or `502/503/504`, `wait_random_exponential(min=1, max=60)`, `stop_after_attempt(5)`, `reraise=True`. Non-transient errors propagate immediately.
- `paginate_all_async(list_fn, ...)` runs an entire cursor-paginated fetch inside one `run_sdk` call.
- `create_client()` returns a **fresh** `PlaneClient` for concurrent batches, so threads never share the singleton's `requests.Session` (which is not thread-safe).

Commands therefore never call the SDK directly — they `await run_sdk(...)` / `await paginate_all_async(...)`.

### Pros and Cons of the Options

#### A. Async wrapper over sync SDK
- Good, because the official SDK and its Pydantic models are reused as-is.
- Good, because concurrency, rate limiting, and retry are centralized — a command gets all three for free.
- Bad, because thread-pool hops add a small per-call overhead and each concurrent batch needs its own client.

#### B. Synchronous + ad-hoc thread pools
- Good, because it avoids an async runtime.
- Bad, because rate limiting and retry would be re-implemented per call site, inviting drift and missed 429 handling.

#### C. Hand-written async HTTP client
- Good, because it would be natively async with no thread hops.
- Bad, because it discards the SDK's endpoint coverage and models, and every future Plane API change becomes our maintenance burden.

## Consequences

**Positive:**
- One place governs concurrency (`Semaphore(4)`), retry policy, and thread safety.
- Commands read as straightforward `async` code.

**Negative:**
- Concurrency is capped at 4 in-flight requests; very large workspaces are throughput-bound by that cap (a deliberate trade-off against rate limiting).
- Each concurrent batch must call `create_client()` rather than reuse the singleton.

**Neutral:**
- Retry is scoped to transient statuses only (429/502/503/504); a mirror of this policy exists in the synchronous `resolve.py` pagination path (`_fetch_page`).

## Confirmation

`_is_retryable()` in `api/async_sdk.py` defines the exact retryable set; any change to concurrency or retry policy should be made there and nowhere else. Tests assert that non-transient SDK errors propagate rather than being retried.
