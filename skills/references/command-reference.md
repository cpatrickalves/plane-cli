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
| `--description` / `-d` | Description (plain text) |
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
| `--description` / `-d` | New description |
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
| `--identifier` / `-i` | Short identifier (e.g. `API`) |
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

## Comments

Command group: `planecli comment` (alias: `comments`)

```
planecli comment ls ISSUE [--project/-p PROJECT] [--limit/-l N]
planecli comment create ISSUE --body "TEXT" [--project/-p PROJECT]
planecli comment update COMMENT_ID --issue ISSUE --body "TEXT" [--project/-p PROJECT]
planecli comment delete COMMENT_ID --issue ISSUE [--project/-p PROJECT]
```

`--limit` (default 50) selects the **most recent** N comments, still rendered
oldest → newest — not the first N chronologically.

## Users

```
planecli users ls        # List workspace members
planecli whoami          # Show authenticated user
```

## Cache

```
planecli cache clear     # Clear all cached data
```
