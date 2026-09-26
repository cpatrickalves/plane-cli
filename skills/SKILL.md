---
name: planecli
description: "Manage Plane.so through the planecli CLI — work items, projects, cycles/sprints, modules, labels, states, documents, intake queue, comments. Use when the user mentions Plane, planecli, or a work-item identifier like ABC-123, or asks about tasks, sprints, or backlogs in a project where Plane is the tracker."
allowed-tools: Bash(planecli *)
metadata:
  author: Patrick Alves
  version: "1.6"
---

# PlaneCLI

CLI for [Plane.so](https://plane.so). Installed as `planecli`.

## Key Concepts

- **Fuzzy resolution**: every resource argument (project, state, label, user, work item) accepts a name, an identifier (`ABC-123`), or a UUID; close names resolve.
- **`me`**: the authenticated user, valid wherever an assignee is expected.
- **`--json`**: pass it on every command; JSON goes to stdout, the human table to stderr.
- **Workspaces**: every command runs in the default workspace of `~/.plane_api`; `-w NAME` (a `[NAME]` section or any slug) switches for one command, `planecli workspaces` lists them.
- **Caching**: reads are cached on disk. `--no-cache` bypasses it for one command; `planecli cache clear` resets it. Read back your own writes with `--no-cache`.
- **Project scoping**: most commands take `-p PROJECT`. Identifiers (`ABC-123`) resolve across projects, and `wi ls` without `-p` spans all projects.

## Quick Reference

Flags below are the common ones; every flag of every command is in
[references/command-reference.md](references/command-reference.md) — read it before guessing a
flag, filter, or sort key.

### Identity & Configuration

```bash
planecli whoami --json          # authenticated user
planecli configure              # interactive setup
planecli users ls --json        # workspace members
planecli workspaces --json      # configured workspaces; add -w NAME to any command
```

### Work Items (most common)

```bash
# List / filter
planecli wi ls -p "Project" --state "In Progress" --assignee me --limit 10 --json
planecli wi ls -p "Project" --labels "bug,critical" --sort updated --json
planecli wi ls --assignee me --state "In Progress" --json      # across all projects

# Create
planecli wi create "Title" -p "Project" --assign me --priority urgent --state "Todo" --json
planecli wi create "Sub-task" --parent ABC-123 --assign "Patrick" --labels "backend" --json
planecli wi create "Title" -p "Project" -d "<p>Body.</p>" --json   # -d is HTML — see Gotchas

# Update
planecli wi update ABC-123 --state "Done" --priority none --json
planecli wi update ABC-123 --assign "Patrick" --labels "bug,urgent" --json

# Other
planecli wi show ABC-123 --json                     # bundles comments (see Gotchas)
planecli wi show ABC-123 --no-comments --json       # skip the comment fetch
planecli wi assign ABC-123 --json                   # assign to yourself
planecli wi assign ABC-123 --assign "Name" --json
planecli wi search "login bug" -p "Project" --json
planecli wi delete ABC-123
```

Priority: `urgent`, `high`, `medium`, `low`, `none` (or `1`–`4`, `0`).

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

### Intake

`intake ls` returns two ids per row: `id` (the queue wrapper) and `issue_id` (the work item).
`accept`, `decline`, and `delete` take `issue_id`.

```bash
planecli intake ls -p "Project" --json
planecli intake enabled "Project" --json                        # is intake on for the project?
planecli intake create "Login button broken" -p "Project" -d "Steps..." -P high --json

# Triage needs the project Admin role: exit 0 = triaged, exit 4 = the API left the record unchanged
planecli intake accept <issue_id> -p "Project" --json
planecli intake decline <issue_id> -p "Project" --json

# Destructive, no prompt, no undo: for any status other than `accepted` this also deletes the
# work item. Read the status from `intake ls` first; `decline` merely removes it from the queue.
planecli intake delete <issue_id> -p "Project"
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

## Gotchas

- **Work-item descriptions are HTML.** `wi create` / `wi update -d` store the value verbatim inside
  the Plane editor's HTML, so markdown renders literally (`##`, backticks). Pass `<h2>`, `<p>`,
  `<ul>`, `<code>`, `<pre><code>`. From a markdown source, convert first and pass
  `-d "$(cat body.html)"` — a file beats a huge inline string. Plane prepends a cosmetic empty
  `<p></p>`. Verify the stored value: `wi show ABC-123 --no-cache --json | jq -r .description_html`
  must contain real tags; a non-empty description proves nothing, since malformed input is stored
  happily. Work items only: `intake create -d` HTML-escapes its input, so tags show up as text.
- **Confirm a create against the server before retrying it.** `wi create` prints the created item
  as JSON, so a broken `jq` filter over that output looks exactly like a failed create. Check with
  `wi ls -p PROJECT --no-cache --json | jq -r '.[] | select(.parent=="<parent-uuid>") | .sequence_id'`.
  There is no idempotency key — retrying a create that succeeded silently duplicates the item.
- **`wi show` occasionally returns non-JSON** (`jq: parse error`). Transient — retry once before
  investigating.
- **`*_names` fields hold UUIDs.** `assignee_names`, `label_names`, `label_detail_names`, and
  `state_detail_name` from `wi show` are raw UUIDs. Build lookup maps with `label ls`, `state ls`,
  `users ls`, or read `priority` and `name` from `wi ls`, which are human-readable.
- **`sequence_id` shape differs.** `wi show` / `wi create` return an integer (`204`); `wi ls`
  returns the full identifier as a string (`"PIPERAG-204"`). Build identifiers as
  `sequence_id` from `wi ls`, or `"{project_identifier}-{sequence_id}"` from `wi show`.
- **`wi show` bundles comments and can degrade to `comments: null`.** `[]` = none, a list = some,
  `null` = the comment fetch failed while the work item still returned and the command exited 0.
  Check for `null` explicitly when "no comments" and "couldn't load comments" differ for you.
  `--no-comments` omits the key entirely.

## Bulk create with rich descriptions

One file per item, convert to HTML, prove the first one renders, then create the rest and count
what landed on the server.

```bash
# 1. write one body per item (01.md, 02.md, ...) and convert to HTML
npx marked -i 01.md -o 01.html          # or any md-to-html converter

# 2. create the FIRST item and inspect its stored HTML before going further
planecli wi create "First title" -p "Project" --parent ABC-1 --assign "Name" \
  --state "Todo" --priority high --labels "bug,backend" -d "$(cat 01.html)" --json
planecli wi show ABC-2 --no-cache --json | jq -r .description_html   # expect <h2>, <pre>

# 3. create the remaining items, then verify the whole batch by parent
planecli wi ls -p "Project" --no-cache --json \
  | jq -r '.[] | select(.parent=="<parent-uuid>") | "\(.sequence_id) \(.priority) \(.name)"'
```
