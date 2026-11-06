---
status: accepted
date: 2026-08-18
decision-makers: PlaneCLI maintainers
---

# ADR-0008: Destructive deletes are documented, not prompted

## Context and Problem Statement

Every `delete` subcommand in the CLI (`wi`, `project`, `cycle`, `module`, `label`, `state`,
`doc`, `comment`, `intake`) removes data immediately, with no confirmation step. That was
uncontroversial while "delete X" removed exactly X.

`intake delete` broke that symmetry. The Plane API deletes the **underlying work item** — not
just the intake queue entry — whenever the intake item's status is anything other than
`accepted` (i.e. `pending`, `rejected`, `snoozed`, `duplicate`). Only for an already-accepted
item is the work item spared and just the queue wrapper removed. So a single command can
destroy an issue the user believed they were merely dequeuing, and neither the command name
nor its arguments hint at that.

The question this raises is broader than intake: does the CLI protect destructive commands with
an interactive confirmation, and if so, which ones?

## Considered Options

- **A. Document the blast radius, keep deletes unprompted** — state the cascade in the
  docstring (`--help`), README, CHANGELOG, and the skill reference; add no prompt.
- **B. Prompt on the destructive cases** — add an interactive confirmation plus a `--yes` /
  `-y` bypass to `intake delete` (and later to the other deletes).
- **C. Refuse the destructive case** — make `intake delete` reject non-accepted items and
  require the user to decline first.

## Decision Outcome

Chosen option: **A**, because the CLI's primary consumers are scripts and AI agents
(`allowed-tools: Bash(planecli *)`), and a prompt that only some commands raise is worse than
no prompt at all: it silently hangs an automated caller that has no TTY, and it teaches
interactive users that "no prompt" means "safe" — which is exactly the wrong lesson for the
eight other deletes that would still be unprompted.

Option B is only defensible applied uniformly to every delete, with a `--yes` bypass and
TTY detection; that is a separate, larger change to the CLI's interaction model, not something
to introduce on one command. Option C removes a capability the API offers and would strand
anyone who genuinely wants the item and its work item gone in one call.

The obligation this decision creates: **when a delete's blast radius is larger than its name
suggests, the docstring must say so in the first two lines** (it becomes the `--help` text),
and the same warning must appear in the README usage example and in `skills/`.

## Confirmation

`commands/intake.py::delete` documents the cascade in its docstring; the README's Intake
section and `skills/references/command-reference.md` carry the same warning. Any new delete
command with a cascade is expected to follow the same pattern in code review.

## Consequences

**Positive:**
- Behaviour stays uniform and scriptable: no `planecli` command blocks on stdin.
- The warning reaches the user where they actually are — `--help`, README, and the agent skill.

**Negative:**
- A user who does not read `--help` can still destroy a work item with one command; the CLI
  offers no undo and Plane has no trash for API deletes.
- Documentation is the only safeguard, so it must be kept accurate as the API changes.

**Neutral:**
- Revisit if the CLI ever adopts a uniform confirmation model; this ADR would then be
  superseded rather than amended per command.

## Amendment (2026-11-06): duplicate-name confirmation on uploads

`attachment attach` and `wi update -i` (when the image upload falls back to v1 attachments) ask
before uploading a file whose name is already attached to the work item. Same-named attachments
are easy to create by accident and hard to tell apart in the web UI, and deleting the wrong one
breaks an image embedded in the description. This is the one exception to "no `planecli` command
blocks on stdin", and it is bounded so that it keeps the reason behind the rule (never hang an
automated caller):

- A command may confirm only when `sys.stdin.isatty()` is true.
- The prompt goes to stderr, never stdout, so `--json` output stays clean ([ADR-0005](0005-dual-output-contract.md)).
- Without a TTY the command does not wait: it refuses with exit 5 and a message that names
  `--force`. An answer other than `y`/`yes`, or EOF, also refuses.
- `--force` skips the check. It is documented in `--help`, the README and the skill's command
  reference.

The prompt guards against a duplicate, not against data loss, so it does not change the decision
above for deletes: they stay unprompted and documented.
