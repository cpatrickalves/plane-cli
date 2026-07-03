---
name: planecli
description: "Manage Plane.so project management via the planecli CLI — list, create, update, and search work items, projects, cycles/sprints, modules, labels, states, documents, and comments. ALWAYS use this skill when the user mentions Plane, Plane.so, planecli, or references work item identifiers like ABC-123, FE-234, MOB-45. Also invoke when the user asks to manage tasks, issues, sprints, backlogs, or project boards AND either explicitly mentions Plane or the project context indicates Plane is the tool in use. Do NOT use for other project management tools (Jira, Linear, Asana, Trello, Azure DevOps Boards)."
allowed-tools: Bash(planecli *)
metadata:
  author: Patrick Alves
  version: "1.3"
---

# PlaneCLI

CLI for [Plane.so](https://plane.so) project management. Installed as `planecli`.

## Key Concepts

- **Fuzzy resolution**: All resource arguments (projects, states, labels, users, work items) accept names, identifiers (e.g. `ABC-123`), or UUIDs. Fuzzy matching with 60% threshold finds close matches.
- **"me" shortcut**: Pass `me` as the assignee value to reference the authenticated user.
- **Output**: Always pass `--json` to get structured JSON output. JSON is the preferred output format.
- **Caching**: Responses are cached on disk. Pass `--no-cache` to bypass or run `planecli cache clear` to reset.
- **Project scoping**: Most commands require `-p PROJECT`. Work items with identifier format (ABC-123) auto-resolve across projects.

## Quick Reference

### Identity & Configuration

```bash
planecli whoami --json          # Show authenticated user
planecli configure                          # Interactive setup
planecli users ls --json        # List workspace members
```

### Work Items (most common)

```bash
# List / filter
planecli wi ls -p "Project" --state "In Progress" --assignee me --limit 10 --json
planecli wi ls -p "Project" --labels "bug,critical" --sort updated --json

# Create
planecli wi create "Title" -p "Project" --assign me --priority urgent --state "Todo" --json
planecli wi create "Sub-task" --parent ABC-123 --assign "Patrick" --labels "backend" --json

# Create with description (-d / --description). Accepts markdown (headers, code fences,
# lists) — Plane renders it. For long/multiline bodies, write to a file and pipe it in:
planecli wi create "Title" -p "Project" -d "Short description" --json
planecli wi create "Title" -p "Project" -d "$(cat /tmp/body.md)" --json   # long/rich body

# Update
planecli wi update ABC-123 --state "Done" --priority none --json
planecli wi update ABC-123 --assign "Patrick" --labels "bug,urgent" --json

# Other
planecli wi show ABC-123 --json                     # Bundles comments (comments: [...] / [] / null)
planecli wi show ABC-123 --no-comments --json        # Skip the comment fetch
planecli wi assign ABC-123 --json                   # Assign to yourself
planecli wi assign ABC-123 --assign "Name" --json   # Assign to someone
planecli wi search "login bug" -p "Project" --json
planecli wi delete ABC-123
```

### Projects

```bash
planecli project ls --state started --sort created --json
planecli project show "Frontend" --json
planecli project create "New Project" -i "NP" -d "Description" --json
planecli project update "Name" --name "New Name" --json
planecli project delete "Name"
```

### Cycles (Sprints)

```bash
planecli cycle ls -p "Project" --json
planecli cycle create "Sprint 1" -p "Project" --start-date 2026-02-17 --end-date 2026-03-02 --json
planecli cycle add-item "Sprint 1" ABC-123 -p "Project"
planecli cycle remove-item "Sprint 1" ABC-123 -p "Project"
planecli cycle items "Sprint 1" -p "Project" --json
```

### Modules, Labels, States, Documents, Comments

```bash
# Modules (--status: backlog, planned, in-progress, paused, completed, cancelled)
planecli module ls -p "Project" --json
planecli module create "Auth" -p "Project" -d "Login flows" --status in-progress --json
planecli module update "Auth" -p "Project" --status completed --json

# Labels
planecli label ls -p "Project" --json
planecli label create "urgent" -p "Project" --color "#FF0000" --json

# States (groups: backlog, unstarted, started, completed, cancelled)
planecli state ls -p "Project" --group started --json
planecli state create "In Review" -p "Project" --group started --color "#FFA500" --json

# Documents
planecli doc ls -p "Project" --json
planecli doc create --title "Spec" --content "## Details..." -p "Project" --json

# Comments
planecli comment ls ABC-123 --json
planecli comment create ABC-123 --body "Fixed in PR #456" --json
```

## Command Aliases

| Full | Aliases |
|---|---|
| `work-item` | `wi`, `issues`, `issue` |
| `project` | `projects` |
| `document` | `doc`, `docs`, `documents` |
| `comment` | `comments` |
| `module` | `modules` |
| `label` | `labels` |
| `state` | `states` |
| `cycle` | `cycles` |
| `user` | `users` |
| `list` | `ls` |
| `show` | `read` |
| `create` | `new` |

## Priority Values

`urgent` (1), `high` (2), `medium` (3), `low` (4), `none` (0). Accept names or numbers.

## Gotchas

- **Descriptions accept markdown.** The `-d` / `--description` flag (on `wi create` and `wi update`) is documented as "plain text", but Plane renders markdown — headers, `code fences`, lists, tables. For long or multiline bodies with code, write the content to a file and pass it with command substitution: `-d "$(cat body.md)"`. Building a huge inline string is error-prone; a file is more reliable. After a bulk create, verify one item with `wi show <ID> --json` to confirm the body rendered before creating the rest.
- **`sequence_id` shape differs between commands.** `wi show`/`wi create` return it as an integer (`204`); `wi ls` returns it already prefixed as a string (`"PIPERAG-204"`). Don't re-prefix the list value (you'd get `PIPERAG-PIPERAG-204`). To build an identifier, use `sequence_id` directly from `wi ls`, or `"{project_identifier}-{sequence_id}"` from `wi show`.
- **`wi show` bundles comments, and can degrade to `comments: null`.** `comments` is `[]` when there are none, a list when there are, or `null` if the comment fetch failed — the work item itself still returns and the command still exits 0 (a comment fetch failure never fails `wi show`). Check for `null` explicitly if your script needs to distinguish "no comments" from "couldn't load comments". Pass `--no-comments` to skip the fetch (then the `comments` key is absent from JSON entirely).

## Common Patterns

```bash
# Get my in-progress items across all projects
planecli wi ls --assignee me --state "In Progress" --json

# JSON output piped to jq
planecli wi ls -p "Project" --json | jq '.[].name'

# Create sub-issue under parent
planecli wi create "Sub-task" --parent ABC-123 -p "Project" --json

# Bulk check: list then update
planecli wi ls -p "Project" --state "In Review" --json
planecli wi update ABC-456 --state "Done" --json
```

## Full Command Reference

For complete flag details on every command, see [references/command-reference.md](references/command-reference.md).
