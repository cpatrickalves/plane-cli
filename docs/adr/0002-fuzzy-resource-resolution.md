---
status: accepted
date: 2026-07-03
decision-makers: PlaneCLI maintainers
---

# ADR-0002: Fuzzy resource resolution (UUID → identifier → name)

## Context and Problem Statement

Plane identifies resources by UUID, but humans do not think in UUIDs. On the command line a user wants to type `--project "Frontend"` or `--state "review"`, not paste a 36-character UUID. At the same time, scripts and power users benefit from being able to pass an exact UUID or a work-item identifier like `ABC-123`. We need a single, predictable way to turn any of these three forms into a concrete record, and to fail helpfully when nothing matches.

## Considered Options

- **A. Layered resolution** — try UUID, then identifier, then fuzzy name, in that fixed order.
- **B. Exact-match only** — require the user to pass a UUID or an exact name.
- **C. Fuzzy-only** — always fuzzy-match on name.

## Decision Outcome

Chosen option: **A**, because it accepts every input form a user might reasonably supply and resolves the unambiguous ones (UUID, identifier) cheaply before falling back to fuzzy matching.

Each resource has a `resolve_<x>` / `resolve_<x>_async` pair in `utils/resolve.py`. The order is:

1. **UUID** — if the input matches the UUID regex, do a direct single-resource lookup.
2. **Identifier** — for work items, if the input matches `^([A-Z]{1,10})-(\d+)$` (e.g. `ABC-123`), fetch it directly by identifier. Projects also accept a case-insensitive exact `identifier` match.
3. **Fuzzy name** — otherwise fetch the candidate list and pick the best name match.

Fuzzy matching (`utils/fuzzy.py`) uses rapidfuzz `token_sort_ratio` with a default threshold of **60** (`MIN_MATCH_SCORE = 60`). `find_best_match` returns the single best candidate above threshold; `find_matches` returns ranked candidates. When a project name fails to resolve, `resolve_project` lowers the threshold to 30 to build a "did you mean …?" suggestion list, turning a dead end into a helpful `ResourceNotFoundError`.

The list-fetch step in stage 3 reads through the disk cache (see [ADR-0004](0004-disk-cache-ttls-and-keys.md)), so repeated fuzzy resolutions in one session avoid re-fetching. Async resolvers call the `cached_list_<x>` helpers, which return plain dicts.

### Pros and Cons of the Options

#### A. Layered resolution
- Good, because it supports UUIDs, identifiers, and human names with one consistent contract.
- Good, because unambiguous inputs (UUID/identifier) skip fetching a full list.
- Bad, because fuzzy matching can, in principle, pick the wrong record when two names are very similar (mitigated by the 60 threshold and suggestions).

#### B. Exact-match only
- Good, because it is unambiguous.
- Bad, because it defeats the CLI's main ergonomic advantage — nobody wants to type UUIDs or exact names.

#### C. Fuzzy-only
- Good, because it is simple.
- Bad, because it wastes a list fetch when the user already gave a UUID/identifier, and it can misfire on inputs that were meant to be exact.

## Consequences

**Positive:**
- `--project "Front"` finds "Frontend"; `wi show ABC-123` works; UUIDs work — all through one code path per resource.
- Failed matches produce actionable suggestions instead of a bare error.

**Negative:**
- A too-low threshold could resolve to an unintended record; the value (60) is a deliberate balance and lives in one constant.

**Neutral:**
- The identifier pattern is currently meaningful only for work items; other resources fall through from UUID straight to fuzzy name.

## Confirmation

The threshold constant `MIN_MATCH_SCORE` in `utils/fuzzy.py` is the single knob for match strictness. `tests/test_fuzzy.py` and `tests/test_resolve.py` cover the ordering and threshold behavior; changes to resolution order should keep those tests green.
