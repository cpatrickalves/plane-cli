# PlaneCLI Command Reference

## Table of Contents
- [Global Options](#global-options)
- [Work Items](#work-items)
- [Projects](#projects)
- [Cycles](#cycles)
- [Modules](#modules)
- [Labels](#labels)
- [States](#states)
- [Documents](#documents)
- [Comments](#comments)
- [Attachments](#attachments)
- [Intake](#intake)
- [Users](#users)
- [Cache](#cache)

## Global Options

| Flag | Description |
|---|---|
| `--verbose` / `-v` | Enable verbose logging |
| `--no-cache` | Bypass cache for this command |
| `--json` | Output JSON to stdout (available on most commands) |
| `--version` | Show version |
| `--help` / `-h` | Show help |

Environment variable `PLANECLI_NO_CACHE=1` disables cache globally.

### Command aliases

| Full | Aliases |
|---|---|
| `work-item` | `wi`, `issues`, `issue` |
| `project` | `projects` |
| `document` | `doc`, `docs`, `documents` |
| `comment` | `comments` |
| `attachment` | `attachments` |
| `module` | `modules` |
| `label` | `labels` |
| `state` | `states` |
| `cycle` | `cycles` |
| `user` | `users` |
| `list` | `ls` |
| `show` | `read` |
| `create` | `new` |
| `attachment attach` | `upload`, `new` |

## Work Items

Command group: `planecli wi` (aliases: `work-item`, `issues`, `issue`)

### wi ls

```
planecli wi ls [OPTIONS]
```

| Flag | Description |
|---|---|
| `--project` / `-p` | Project name, identifier, or UUID (omit for all projects) |
| `--assignee` | Filter by assignee name or `me` |
| `--state` | Filter by state name (comma-separated for OR) |
| `--labels` | Filter by label name (comma-separated for OR) |
| `--sort` | Sort by: `created` (default), `updated` |
| `--limit` / `-l` | Max results (default: 50) |
| `--json` | JSON output |

### wi show

```
planecli wi show ISSUE [OPTIONS]
```

| Parameter | Description |
|---|---|
| `ISSUE` | Work item identifier (ABC-123), UUID, or name (required) |
| `--project` / `-p` | Project (required for name-based lookup) |
| `--no-comments` | Skip fetching the work item's comments |
| `--json` | JSON output |

Bundles the work item's comments in the same call (chronological, oldest → newest;
same data `comment ls` returns). In `--json` output, the `comments` field is a list
(`[]` if there are none), or `null` if the comment fetch failed — the work item
itself still returns and the command still exits 0. In human output, a `Comments`
section follows the work item details, showing `(none)` or `(failed to load)` as
appropriate. Pass `--no-comments` to skip the fetch entirely (the `comments` key is
then omitted from JSON output).

### wi create

```
planecli wi create TITLE [OPTIONS]
```

| Parameter | Description |
|---|---|
| `TITLE` | Work item title (required) |
| `--project` / `-p` | Project (required) |
| `--assignee` / `--assign` | Assignee name, email, or `me` |
| `--state` | State name (e.g. `Todo`, `In Progress`) |
| `--labels` | Comma-separated label names |
| `--priority` | `urgent`, `high`, `medium`, `low`, `none` (or 0-4) |
| `--module` | Module name or UUID |
| `--parent` | Parent work item identifier (ABC-123) for sub-issues |
| `--estimate` / `-e` | Story point estimate |
| `--description` / `-d` | Description. Stored as raw HTML, not markdown — see the Gotchas in SKILL.md |
| `--image` / `-i` | Image file to embed in the description (repeatable). Every path is checked before the item is created; the images are uploaded after the create and appended to the `-d` text as `<p><img src="ASSET_UUID" /></p>` |
| `--json` | JSON output |

### wi update

```
planecli wi update ISSUE [OPTIONS]
```

| Parameter | Description |
|---|---|
| `ISSUE` | Work item identifier, UUID, or name (required) |
| `--project` / `-p` | Project (required for name-based lookup) |
| `--state` | New state name |
| `--priority` | New priority |
| `--assignee` / `--assign` | New assignee name or `me` |
| `--labels` | Comma-separated labels to set |
| `--clear-labels` | Remove all labels |
| `--name` | New title |
| `--description` / `-d` | New description. Stored as raw HTML, not markdown |
| `--image` / `-i` | Image file to embed (repeatable). Appended to the new `-d` text, or to the existing description. Uploaded only after every other option resolved, so a typo in `--state` uploads nothing |
| `--force` | Upload an image even if an attachment with the same name exists. Applies only when the server falls back to v1 attachments |
| `--json` | JSON output |

### wi delete

```
planecli wi delete ISSUE [OPTIONS]
```

| Parameter | Description |
|---|---|
| `ISSUE` | Work item identifier, UUID, or name (required) |
| `--project` / `-p` | Project (required for name-based lookup) |

### wi search

```
planecli wi search QUERY [OPTIONS]
```

| Parameter | Description |
|---|---|
| `QUERY` | Search text (required) |
| `--project` / `-p` | Project (required) |
| `--sort` | Sort by: `created` (default), `updated` |
| `--limit` / `-l` | Max results (default: 50) |
| `--json` | JSON output |

### wi assign

```
planecli wi assign ISSUE [OPTIONS]
```

| Parameter | Description |
|---|---|
| `ISSUE` | Work item identifier, UUID, or name (required) |
| `--assignee` / `--assign` | Assignee (default: `me`) |
| `--project` / `-p` | Project (required for name-based lookup) |

## Projects

Command group: `planecli project` (alias: `projects`)

### project ls

```
planecli project ls [OPTIONS]
```

| Flag | Description |
|---|---|
| `--state` / `-s` | Filter: `planned`, `started`, `paused`, `completed`, `canceled` |
| `--limit` / `-l` | Max results (default: 50) |
| `--sort` | Sort: `linear` (default), `created`, `updated` |
| `--json` | JSON output |

### project show

```
planecli project show PROJECT [OPTIONS]
```

### project create

```
planecli project create NAME [OPTIONS]
```

| Parameter | Description |
|---|---|
| `NAME` | Project name (required) |
| `--identifier` / `-i` | Short identifier (e.g. `API`). Optional. Defaults to the first 5 letters of the name, uppercased. Pass `-i` if that is taken or the name has no usable letters |
| `--description` / `-d` | Description |
| `--json` | JSON output |

### project update / delete

```
planecli project update PROJECT [OPTIONS]
planecli project delete PROJECT
```

## Cycles

Command group: `planecli cycle` (alias: `cycles`)

### cycle ls / show / create / update / delete

```
planecli cycle ls -p PROJECT
planecli cycle show CYCLE -p PROJECT
planecli cycle create NAME -p PROJECT --start-date YYYY-MM-DD --end-date YYYY-MM-DD
planecli cycle update CYCLE -p PROJECT [OPTIONS]
planecli cycle delete CYCLE -p PROJECT
```

### cycle add-item / remove-item / items

```
planecli cycle add-item CYCLE ISSUE -p PROJECT
planecli cycle remove-item CYCLE ISSUE -p PROJECT
planecli cycle items CYCLE -p PROJECT
```

## Modules

Command group: `planecli module` (alias: `modules`)

```
planecli module ls -p PROJECT
planecli module show MODULE -p PROJECT
planecli module create NAME -p PROJECT [-d DESCRIPTION] [--start-date DATE] [--end-date DATE] [--status STATUS]
planecli module update MODULE -p PROJECT [--name NAME] [-d DESCRIPTION] [--start-date DATE] [--end-date DATE] [--status STATUS]
planecli module delete MODULE -p PROJECT
```

**Module status values** (`--status`): `backlog`, `planned`, `in-progress`, `paused`, `completed`, `cancelled`.
Also accepts Portuguese aliases: `planejado`, `em andamento`, `pausado`, `concluído`, `cancelado` (and `canceled`, `in progress`).

## Labels

Command group: `planecli label` (alias: `labels`)

```
planecli label ls -p PROJECT
planecli label show LABEL -p PROJECT
planecli label create NAME -p PROJECT [--color "#HEX"]
planecli label update LABEL -p PROJECT [--name NAME] [--color "#HEX"]
planecli label delete LABEL -p PROJECT
```

## States

Command group: `planecli state` (alias: `states`)

State groups: `backlog`, `unstarted`, `started`, `completed`, `cancelled`, `triage`

```
planecli state ls -p PROJECT [--group GROUP]
planecli state show STATE -p PROJECT
planecli state create NAME -p PROJECT --group GROUP [--color "#HEX"]
planecli state update STATE -p PROJECT [--color "#HEX"]
planecli state delete STATE -p PROJECT
```

## Documents

Command group: `planecli doc` (aliases: `document`, `documents`, `docs`)

```
planecli doc ls -p PROJECT
planecli doc show TITLE -p PROJECT
planecli doc create --title TITLE --content CONTENT -p PROJECT
planecli doc update TITLE --content CONTENT -p PROJECT
planecli doc delete TITLE -p PROJECT
```

`doc delete` is permanent. Some self-hosted servers answer 405 to `doc update` and `doc delete`. `--content` is plain text: blank lines split paragraphs, newlines become line breaks, URLs become links, and backticks and fences become code.

## Comments

Command group: `planecli comment` (alias: `comments`)

```
planecli comment ls ISSUE [--project/-p PROJECT] [--limit/-l N]
planecli comment create ISSUE --body "TEXT" [--project/-p PROJECT]
planecli comment update COMMENT_ID --issue ISSUE --body "TEXT" [--project/-p PROJECT]
planecli comment delete COMMENT_ID --issue ISSUE [--project/-p PROJECT]
```

`--limit` (default 50) selects the **most recent** N comments, still rendered
oldest → newest — not the first N chronologically. A limit of `0` or a negative
value returns no comments (consistent with the `[:limit]` semantics used elsewhere,
where `0` means "none").

## Attachments

Command group: `planecli attachment` (alias: `attachments`)

```
planecli attachment attach ISSUE -f FILE [--project/-p PROJECT] [--force] [--json]
planecli attachment ls ISSUE [--project/-p PROJECT] [--json]
```

- `attach` checks that `FILE` exists before any API call (exit 5 if not), uploads it in three
  steps (register, push to the presigned storage URL, mark uploaded), and reads it back: exit 4
  if the server does not confirm the upload.
- **Duplicate names.** If a file with the same name is already attached, `attach` asks
  `Upload anyway? [y/N]` on stderr when stdin is a terminal. Without a terminal it refuses with
  exit 5 and names `--force`, so a script never blocks on stdin
  ([ADR-0008](../../docs/adr/0008-destructive-deletes-are-documented-not-prompted.md)).
  `--force` uploads without asking.
- `ls` shows `ID`, `Name`, `Type`, `Size`, `Uploaded`, `Created`. In `--json`, `name`, `type` and
  `size` are copied to the top level from the API's `attributes`.
- **Images in descriptions** (`wi create/update -i`) first try the app endpoint
  `/api/assets/v2/` (entity type `ISSUE_DESCRIPTION`, not listed by `attachment ls`). Servers that
  answer 401/403/404 to an API token there fall back to a v1 attachment, which `attachment ls`
  shows and which the duplicate-name check covers. The `img` tag stores only the asset UUID; the
  web editor resolves it.
- MIME types come from the file extension. `.md`, `.markdown` and `.log` always upload as
  `text/plain`, because some Plane servers reject `text/markdown` with `400 Invalid file type.`
  Unknown types upload as `application/octet-stream`. Other types a server's allow list
  rejects fail with exit 4.

## Intake

Command group: `planecli intake` (no alias)

```
planecli intake ls -p PROJECT
planecli intake create NAME -p PROJECT [--description/-d TEXT] [--priority/-P PRIORITY]
planecli intake accept ISSUE_ID -p PROJECT
planecli intake decline ISSUE_ID -p PROJECT
planecli intake delete ISSUE_ID -p PROJECT
planecli intake enabled PROJECT
```

| Parameter | Description |
|---|---|
| `ISSUE_ID` | **Work item UUID** — the `Issue ID` column of `intake ls`, not the intake wrapper `Intake ID` |
| `--project` / `-p` | Project name, identifier, or UUID (required on every subcommand except `enabled`, which takes the project as its argument) |
| `--description` / `-d` | Item description, plain text (wrapped in a paragraph tag and HTML-escaped) |
| `--priority` / `-P` | `none` (default), `low`, `medium`, `high`, `urgent` — an unknown value exits `5` |
| `--json` | JSON output (all subcommands except `delete`) |

Item `status` is reported as a label: `pending`, `rejected`, `snoozed`, `accepted`, `duplicate`.

`accept` and `decline` **require the project Admin role**. Plane answers `HTTP 200` with the
record unchanged for lower roles, so the CLI compares the returned status against the requested
one and exits `4` ("the intake status was not changed") instead of reporting a false success.

`delete` is destructive beyond the queue: for any status other than `accepted` it also
**permanently deletes the underlying work item**. There is no confirmation prompt and no undo —
use `decline` when the intent is only to reject the submission.

`ls` returns an empty list when the project's intake view is off; `enabled` reports the same
project flag (`intake_enabled`).

## Users

```
planecli users ls        # List workspace members
planecli whoami          # Show authenticated user
```

## Cache

```
planecli cache clear     # Clear all cached data
```
