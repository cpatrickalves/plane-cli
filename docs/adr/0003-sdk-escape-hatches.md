---
status: accepted
date: 2026-07-03
decision-makers: PlaneCLI maintainers
---

# ADR-0003: SDK escape hatches for API/model mismatches

## Context and Problem Statement

The `plane-sdk` Pydantic models do not always match what the live Plane API returns, and the SDK does not cover every endpoint. Three concrete mismatches break the "just call the SDK" path:

1. **Work items** — the API returns `assignees` and `labels` as lists of **UUID strings**, but the SDK's `WorkItemDetail` model expects lists of nested objects, so validation raises before we ever see the data.
2. **Documents (Pages)** — the SDK's Pages support is incomplete; `list`/`update`/`delete` are missing or broken.
3. **Estimate points** — the external API exposes no endpoint that lists a project's estimate points, yet the `--estimate` flag needs to map a value like `"3"` to its UUID.

Without a strategy, these would each surface as an opaque validation error or a missing feature. We need targeted, well-marked bypasses that keep the SDK everywhere it *does* work.

## Considered Options

- **A. Per-case escape hatches** — bypass the SDK only where it is broken, using the narrowest workaround, and mark each with a `NOTE:` in the code.
- **B. Fork/patch `plane-sdk`** — fix the models and endpoints upstream-in-a-fork and depend on the fork.
- **C. Drop the SDK entirely** — talk to the HTTP API directly everywhere.

## Decision Outcome

Chosen option: **A**, because the SDK is correct for the large majority of calls; only three spots need help, and isolating the workarounds keeps the blast radius small and the reasons discoverable.

The three escape hatches:

1. **Work items — raw `_get()`.** Resolvers call `client.work_items._get(path)`, the SDK's low-level HTTP accessor, which returns a **plain dict** and skips `WorkItemDetail` validation. This is used for UUID lookups, `ABC-123` identifier lookups, and cross-project lookups in `utils/resolve.py`. Each site carries a `NOTE:` explaining that the API returns `assignees`/`labels` as UUID strings.
2. **Documents (Pages) — direct HTTP.** For `list`, `update`, and `delete`, `commands/documents.py` calls the Plane HTTP API directly with `requests` and an `X-Api-Key` header through `asyncio.to_thread`. These calls run in a thread but deliberately skip `run_sdk`, so they get no concurrency semaphore and no retries from [ADR-0001](0001-async-wrapper-over-sync-sdk.md). `show` and `create` use the SDK through `run_sdk`.
3. **Estimate points — derive from work items.** `cached_list_estimate_points` fetches work items with `expand=estimate_point` (again via raw `_get()`, since expansion turns `estimate_point` from a string into a dict and breaks SDK validation) and collects the unique `{id, value}` pairs. `resolve_estimate_point_async` then maps a requested value to its UUID.

## Consequences

**Positive:**
- The CLI works against the real API today, without waiting on upstream SDK fixes.
- The SDK (and its models) is still used everywhere it is correct.

**Negative:**
- Raw `_get()` and direct HTTP bypass model validation, so those paths return loosely-typed dicts and must guard their own field access.
- The escape hatches are coupled to current API quirks; if the SDK is fixed upstream, these should be revisited and removed.

**Neutral:**
- The work item and estimate point bypasses still flow through the async wrapper, so they inherit concurrency limiting and retry. The direct document calls do not, so a transient error on `doc list`, `update`, or `delete` fails the command.

## Confirmation

Work item bypasses are marked with a `NOTE:` comment at their call sites. To list every bypass, grep for `_get(` in `utils/resolve.py` and `cache.py`, and for the `X-Api-Key` header in `commands/documents.py`. If a future `plane-sdk` release fixes `WorkItemDetail` validation or adds Pages/estimate-point endpoints, those call sites are the checklist for removing the workarounds.
