---
status: accepted
date: 2026-07-03
decision-makers: PlaneCLI maintainers
---

# ADR-0006: Secondary enrichment degrades to a null sentinel (partial success)

## Context and Problem Statement

`wi show` is growing beyond the bare work-item object: it now bundles the issue's
**comments** in a single call (see the `wi show` comments design). Comments are a
*secondary* enrichment — the user's primary intent is still "show me this issue." The
comment fetch is a separate network call that can fail (rate limit, transient 5xx, auth
edge) independently of the work-item fetch that already succeeded.

The question: when the primary resource loaded but a secondary enrichment fails, does the
whole command fail, or does it return the primary resource and degrade the enrichment?
Getting this wrong regresses the pre-feature behavior — before comments, a `wi show` whose
issue loaded always exited 0.

## Considered Options

- **A. Partial success** — return the issue, set the failed enrichment to a `null` sentinel,
  warn on stderr, exit 0.
- **B. Fail-fast** — any sub-fetch failure aborts the command with a non-zero exit code.
- **C. Structured error surface** — return the issue plus a `{comments_error: {...}}` object
  and/or a `--strict` flag so consumers can react programmatically.

## Decision Outcome

Chosen option: **A**, because a secondary enrichment must never regress the primary command.
The invariant it protects: **a `wi show` whose issue loaded exits 0**, exactly as before the
feature existed.

The contract:

- **JSON:** the enrichment key carries the data on success (`comments: [...]` / `[]`), the
  **`null` sentinel** on failure (`comments: null`), and is **omitted** when opted out
  (`--no-comments`).
- **Exit code:** a secondary-fetch failure is a *partial success* → **exit 0**. Only a failure
  of the *primary* resource (resolution/auth on the issue itself) propagates as a
  `PlaneCLIError` with its exit code, as before.
- **Human stream:** the failure is announced on **stderr** (`Comments: (failed to load)`),
  consistent with [ADR-0005](0005-dual-output-contract.md) — stdout stays clean under `--json`.
- **Narrow catch:** only API/transport errors (`PlaneError`, `PlaneCLIError`) degrade to `null`.
  A programming bug (`KeyError`, bad merge, import error) **propagates** and crashes loudly, so
  it cannot ship green behind a passing "degrades to null" test.
- **Isolation:** the degrading block lives *outside* the command's primary `try/except` with its
  own narrow catch, so the primary error handler can never turn a comment failure into an abort.

## Confirmation

The pattern is enforced in `commands/work_items.py::show`: the comment fetch is a standalone
block after work-item enrichment, wrapped in `except (PlaneError, PlaneCLIError)`, setting
`data["comments"] = None` on failure. On the comment fetch itself the shared
`fetch_issue_comments` helper is **raise-only** — each caller owns that failure policy, so
`comment ls`, whose entire purpose *is* comments, keeps hard-failing with a proper exit code.

The same "don't let a nicety sink the payload" logic applies *one level deeper, inside* the
helper. Resolving each `actor` UUID to a display name needs the workspace members list — a
**tertiary** enrichment. If that members fetch fails (`PlaneError`/`PlaneCLIError`), the helper
degrades to an empty members map and `actor_name` falls back to the raw UUID (per
`_enrich_comment`), rather than raising and losing comments that already loaded. This is the
narrow exception to "raise-only": the helper still raises when the **comments** call fails
(the payload), but absorbs a failure of the **author-name** lookup (a label on the payload).

### Pros and Cons of the Options

#### A. Partial success (null sentinel, exit 0)
- Good, because it preserves the pre-feature invariant (issue loaded → exit 0).
- Good, because machine consumers can detect degradation via `.comments == null`.
- Bad, because a piped `--json` consumer that ignores the sentinel silently sees zero comments;
  the only richer signal is the stderr warning a pipe discards.

#### B. Fail-fast
- Good, because failure is impossible to miss.
- Bad, because it regresses `wi show`: a flaky comments endpoint would break a command that used
  to always work, punishing the user for a secondary concern.

#### C. Structured error surface / `--strict`
- Good, because it gives programmatic error detail.
- Bad, because it's YAGNI — no consumer needs it yet, and it complicates every enrichment and the
  output contract. Revisit if a real need appears.

## Consequences

**Positive:**
- Enrichment failures never regress the primary command; the feature is safe to always-on.
- A reusable stance: the estimate-point re-fetch in `wi show` currently *aborts* on failure and
  could later adopt this same degrade-to-sentinel pattern for consistency.

**Negative:**
- Introduces a tri-state JSON field (`[...]` / `[]` / `null`) plus key-absence for `--no-comments`.
  Consumers must know `null` means "unavailable," not "empty."
- The estimate re-fetch and the comment fetch are, for now, asymmetric (abort vs degrade).

**Neutral:**
- The stderr warning and exit-0 both align with [ADR-0005](0005-dual-output-contract.md).
