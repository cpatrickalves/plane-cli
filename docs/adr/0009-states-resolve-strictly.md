---
status: accepted
date: 2026-10-20
decision-makers: PlaneCLI maintainers
---

# ADR-0009: States resolve strictly, not fuzzily

## Context and Problem Statement

[ADR-0002](0002-fuzzy-resource-resolution.md) resolves every resource name with rapidfuzz at a
threshold of 60. For states that is the wrong trade-off. State names are short and a workflow
often has several that share words — "pronto p/ qa", "em qa", "pronto p/ hml", "em hml" — so
`wi update ABC-1 --state qa` fuzzy-matched whichever name scored highest and moved the work item
to a column the user never named. `wi ls --state` had the opposite problem: a substring filter
that silently ORed every state containing the text. Either way the command succeeded, so the
mistake surfaced only later, on the board.

## Considered Options

- **A. Strict matching with a unique partial fallback** — exact name, else the only name that
  contains the query, else fail with the list of states.
- **B. Keep fuzzy, raise the threshold** — fewer wrong picks, but still a guess.
- **C. Exact names only** — unambiguous, but `--state review` for "code review" stops working.

## Decision Outcome

Chosen option: **A**, because a state change is a write that is easy to miss, so the CLI must
never guess between candidates, while a partial name that fits exactly one state is still
convenient and safe.

- A UUID is looked up directly, as before.
- An exact, case-insensitive name wins.
- Otherwise the only name containing the query as a whole word is used, then the only name
  containing it as a substring. Either prints `State matched: "query" -> "name"` on stderr.
- Several candidates, or none, raise `ValidationError` (exit 5) listing the project's states.
  A fuzzy-only resemblance is not a match.
- `wi ls --state` matches each name per project. With `--project` the rules above apply as is.
  Across projects a name may be missing from some projects, but it must match in at least one
  and be ambiguous in none.
- Other resources keep fuzzy resolution (ADR-0002).

## Confirmation

`match_state_name` / `resolve_state_name` in `utils/resolve.py` implement the rules and back
`resolve_state` / `resolve_state_async`; `_resolve_state_filter` in `commands/work_items.py`
applies them to `wi ls --state`. Covered by `tests/test_resolve.py` and the `TestStateFilter`
tests in `tests/test_commands/test_work_items.py`.

## Consequences

**Positive:**
- A state name either lands where the user meant or fails before anything is written.
- The error lists the valid names, so the fix is one retry away.

**Negative:**
- Inputs that used to resolve by fuzzy resemblance (typos such as "dne" for "Done") now fail.
- `wi ls --state qa` no longer ORs every state containing "qa"; list the states explicitly.

**Neutral:**
- An unknown state name now exits with 5 (ValidationError) instead of 3 (not found).
