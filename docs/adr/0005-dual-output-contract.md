---
status: accepted
date: 2026-07-03
decision-makers: PlaneCLI maintainers
---

# ADR-0005: Dual output contract (table → stderr, JSON → stdout)

## Context and Problem Statement

PlaneCLI serves two audiences at once: a human reading a terminal, who wants colored, aligned tables, and a script piping output into `jq`, which wants clean JSON on stdout and nothing else. If human-readable tables and machine-readable JSON share the same stream, a script cannot reliably parse the output, and a human running with `--json` sees raw JSON with no context. We need one predictable rule that satisfies both without a mode flag on every read.

## Considered Options

- **A. Split streams** — human tables always go to **stderr**, JSON goes to **stdout** only when `--json` is passed.
- **B. Single stream, `--json` switches the format** on stdout.
- **C. `--quiet`/`--format` matrix** — separate flags for verbosity and format.

## Decision Outcome

Chosen option: **A**, because it lets `--json 2>/dev/null` produce byte-clean JSON while a human still gets a table by default, with no per-command mode juggling.

The contract:

- The default output is a Rich table, written to **stderr** via the formatters in `formatters/` (`output()` for lists, `output_single()` for records).
- Every read/mutate command accepts `json: bool = False` and passes `as_json=json` to the formatter. When `--json` is set, structured JSON is written to **stdout**.
- Because the table is on stderr, `planecli wi ls -p Frontend --json 2>/dev/null | jq …` yields exactly the JSON, nothing else.

**Global flags are stripped before parsing.** Two flags are not owned by cyclopts and are handled in `app.py::main()` by editing `sys.argv` *before* `app()` runs:

- `--verbose` / `-v` — raises log verbosity (logs also go to stderr, keeping stdout clean).
- `--no-cache` — bypasses cache reads for the invocation (see [ADR-0004](0004-disk-cache-ttls-and-keys.md)).

Errors follow the same discipline: `PlaneCLIError` is caught in `main()` and printed to stderr with a hint, and the process exits with the error's `exit_code` (Auth=2, NotFound=3, API=4, Validation=5).

### Pros and Cons of the Options

#### A. Split streams (table→stderr, JSON→stdout)
- Good, because `--json 2>/dev/null` is always pipe-safe.
- Good, because logs and tables never pollute the machine-readable stream.
- Bad, because a user redirecting stderr loses the human table, which can surprise newcomers.

#### B. Single stream with `--json`
- Good, because it matches many simple CLIs.
- Bad, because interleaved logs/warnings on stdout corrupt JSON, and there is no clean way to keep both a human table and parseable output.

#### C. `--quiet`/`--format` matrix
- Good, because it is maximally flexible.
- Bad, because it pushes complexity onto every command and every user for a need the stream split already covers.

## Consequences

**Positive:**
- Scripting is reliable: stdout carries only JSON (and only when asked).
- Humans get rich tables by default with zero flags.

**Negative:**
- Redirecting stderr hides the default table — documented in the README so users expect it.
- The two global flags require the pre-parse `sys.argv` edit in `main()`, a small but deliberate deviation from pure cyclopts parsing.

**Neutral:**
- Logging (loguru) and error messages both target stderr, consistent with the contract.

## Confirmation

The stream split is enforced in `formatters/` (table console → stderr) and the flag stripping in `app.py::main()`. The invariant to preserve: **stdout is written to only for `--json` payloads**; anything human-facing (tables, logs, errors, hints) goes to stderr.
