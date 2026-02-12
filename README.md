# PlaneCLI

A command-line interface for [Plane.so](https://plane.so) (SaaS or Self-hosted) that lets you manage projects, work items, cycles, modules, documents, and more — directly from the terminal.

The main differentiator is **intelligent fuzzy search**: reference any resource by name, identifier (e.g. `ABC-123`), or UUID, and PlaneCLI automatically finds the closest match.

## Features

- **Work Items**: Full CRUD with sub-issues, labels, states, priorities, assignees, search, and quick-assign
- **Projects**: List, create, view, update, and delete projects
- **Cycles**: Manage sprints — create cycles, add/remove work items, track progress
- **Modules**: Organize work into modules with date ranges
- **Labels**: Create and manage project labels with custom colors
- **States**: Configure workflow states per project
- **Documents**: Create, read, update, and delete project documents
- **Comments**: Add, update, and delete comments on work items
- **Users**: List workspace members and identify the authenticated user
- **Fuzzy Search**: Intelligent resource resolution — `--project "Front"` finds "Frontend"
- **Dual Output**: Rich tables (default) or JSON with `--json` for scripting
- **Caching**: Disk-based API response cache for faster repeated queries
- **Flexible Configuration**: Environment variables, config file, or interactive setup

## Quick Start

### 1. Install

```bash
git clone https://github.com/cpatrickalves/plane-cli.git
cd plane-cli
uv tool install -e .
```

### 2. Configure

```bash
planecli configure
```

This prompts for your Plane base URL, Personal Access Token, and workspace slug. See [Configuration](#configuration) for alternative methods.

### 3. Try it out

```bash
# Check your identity
planecli whoami

# List your projects
planecli project ls

# List work items for a project
planecli wi ls -p "Frontend"

# Create a work item
planecli wi create "Fix login bug" -p "Frontend" --assign me --priority urgent
```

## Command Reference

> If you installed with `uv sync` instead of `uv tool install`, prefix all commands with `uv run`.

### Work Items

```bash
# List all work items across all projects
planecli wi ls

# List work items for a specific project
planecli wi ls -p "Frontend"

# Filter by state and/or labels (comma-separated for OR logic)
planecli wi ls -p "Frontend" --state "In Progress,In Review"
planecli wi ls -p "Frontend" --labels "bug,critical"

# Sort and limit results
planecli wi ls -p "Frontend" --sort updated --limit 10

# Show a specific work item (by identifier or name)
planecli wi show ABC-123

# Create a work item
planecli wi create "Fix login timeout" -p "Frontend" --assign me --priority urgent
planecli wi create "Review PR #345" --parent ABC-234 --assign "Luiz" --state "In Review"

# Update a work item
planecli wi update ABC-123 --state "Done" --priority none

# Quick-assign a work item (defaults to yourself)
planecli wi assign ABC-123
planecli wi assign ABC-123 --assign "Patrick"

# Search work items
planecli wi search "login bug" -p "Frontend"

# Delete a work item
planecli wi delete ABC-123
```

### Projects

```bash
# List all projects
planecli project ls

# Show project details
planecli project show "Frontend"

# Create a project
planecli project create "Backend API" -i "API" -d "REST API service"

# Update a project
planecli project update "Backend API" --name "Backend Service"

# Delete a project
planecli project delete "Old Project"
```

### Cycles

```bash
# List cycles for a project
planecli cycle ls -p "Frontend"

# Show cycle details
planecli cycle show "Sprint 1" -p "Frontend"

# Create a cycle
planecli cycle create "Sprint 2" -p "Frontend" --start-date 2026-02-17 --end-date 2026-03-02

# Add/remove work items from a cycle
planecli cycle add-item "Sprint 2" ABC-123 -p "Frontend"
planecli cycle remove-item "Sprint 2" ABC-123 -p "Frontend"

# List items in a cycle
planecli cycle items "Sprint 2" -p "Frontend"
```

### Modules

```bash
# List modules
planecli module ls -p "Frontend"

# Show module details
planecli module show "Authentication" -p "Frontend"

# Create a module
planecli module create "Authentication" -p "Frontend" -d "Login and signup flows"

# Update a module
planecli module update "Authentication" -p "Frontend" --start-date 2026-03-01

# Delete a module
planecli module delete "Authentication" -p "Frontend"
```

### Labels

```bash
# List project labels
planecli label ls -p "Frontend"

# Create a label with a color
planecli label create "urgent" -p "Frontend" --color "#FF0000"

# Update a label
planecli label update "urgent" -p "Frontend" --name "critical" --color "#CC0000"

# Delete a label
planecli label delete "urgent" -p "Frontend"
```

### States

```bash
# List workflow states
planecli state ls -p "Frontend"

# Filter by group (backlog, unstarted, started, completed, cancelled)
planecli state ls -p "Frontend" --group started

# Create a state
planecli state create "In Review" -p "Frontend" --group started --color "#FFA500"

# Update a state
planecli state update "In Review" -p "Frontend" --color "#FF8C00"

# Delete a state
planecli state delete "In Review" -p "Frontend"
```

### Documents

```bash
# List documents
planecli doc ls -p "Frontend"

# Read a document
planecli doc show "Architecture Guide" -p "Frontend"

# Create a document
planecli doc create --title "API Spec" --content "## Endpoints..." -p "Frontend"

# Update a document
planecli doc update "API Spec" --content "Updated content" -p "Frontend"

# Delete a document
planecli doc delete "API Spec" -p "Frontend"
```

### Comments

```bash
# List comments on a work item
planecli comment ls ABC-123

# Add a comment
planecli comment create ABC-123 --body "Fixed in PR #456"

# Update a comment
planecli comment update <comment-id> --issue ABC-123 --body "Updated comment"

# Delete a comment
planecli comment delete <comment-id> --issue ABC-123
```

### Users

```bash
# List workspace members
planecli users ls

# Check authenticated user
planecli whoami
```

### Cache

```bash
# Clear the API response cache
planecli cache clear

# Bypass cache for a single command
planecli --no-cache wi ls -p "Frontend"
```

## Command Aliases

| Full command | Aliases |
|---|---|
| `planecli work-item` | `wi`, `issues`, `issue` |
| `planecli project` | `projects` |
| `planecli comment` | `comments` |
| `planecli document` | `documents`, `doc`, `docs` |
| `planecli users` | `user` |
| `planecli module` | `modules` |
| `planecli label` | `labels` |
| `planecli state` | `states` |
| `planecli cycle` | `cycles` |
| `planecli cache` | - |
| Subcommand `list` | `ls` |
| Subcommand `show` | `read` |
| Subcommand `create` | `new` |

## Configuration

PlaneCLI supports three configuration methods. Precedence: **CLI arguments > environment variables > config file**.

### Interactive Setup

```bash
planecli configure
```

Prompts for base URL, Personal Access Token, and workspace slug. Saves to `~/.plane_api` with restricted permissions (`0600`).

### Environment Variables

```bash
export PLANE_BASE_URL="https://api.plane.so"
export PLANE_API_KEY="your-personal-access-token"
export PLANE_WORKSPACE="your-workspace-slug"
```

Works with both Plane.so SaaS (`https://api.plane.so`) and self-hosted instances.

### Configuration File

Create `~/.plane_api`:

```ini
base_url=https://api.plane.so
api_key=your-personal-access-token
workspace=your-workspace-slug
```

## Output Formats

By default, PlaneCLI renders results as colored Rich tables on stderr. Add `--json` to any command to get structured JSON on stdout:

```bash
# Table output (default)
planecli wi ls -p "Frontend"

# JSON output
planecli wi ls -p "Frontend" --json

# JSON only (suppress the table)
planecli wi ls -p "Frontend" --json 2>/dev/null

# Pipe to jq
planecli wi ls -p "Frontend" --json 2>/dev/null | jq '.[].name'
```

## Fuzzy Search

PlaneCLI resolves resources using a three-step strategy:

1. **UUID** — direct lookup if the input is a valid UUID
2. **Identifier** — matches patterns like `ABC-123` against project identifiers
3. **Fuzzy name match** — uses [rapidfuzz](https://github.com/rapidfuzz/RapidFuzz) with a 60% similarity threshold

This means you don't need exact names:

```bash
planecli wi ls -p "Front"        # Matches "Frontend"
planecli wi assign ABC-123 --assign "Pat"  # Matches "Patrick"
planecli wi update ABC-123 --state "review"  # Matches "In Review"
```

## Caching

PlaneCLI caches API responses on disk (SQLite-backed) for faster repeated queries. Caching is automatic and transparent.

```bash
# Bypass cache for a single command
planecli --no-cache wi ls -p "Frontend"

# Or set the environment variable
export PLANECLI_NO_CACHE=1

# Clear all cached data
planecli cache clear
```

For details on TTLs, cache keys, and invalidation, see [docs/03-caching.md](docs/03-caching.md).

## Development

### Prerequisites

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) (package and virtual environment manager)
- A [Plane.so](https://plane.so) or self-hosted account with a [Personal Access Token](https://developers.plane.so/api-reference/introduction)

### Setup

```bash
git clone https://github.com/cpatrickalves/plane-cli.git
cd plane-cli
uv sync
uv run planecli --help
```

### Makefile

```bash
make help            # Show all available commands
make install         # Install dependencies (dev environment)
make install-tool    # Install CLI system-wide (editable)
make test            # Run tests
make test-v          # Run tests (verbose)
make lint            # Run linter
make lint-fix        # Run linter with auto-fix
make format          # Format code using ruff formatter
make check           # Run lint + tests
make build           # Build distribution packages
make clean           # Remove build artifacts and caches
make run ARGS="..."  # Run the CLI with arguments
```

### Project Structure

```
src/planecli/
    __init__.py          # Package version
    __main__.py          # python -m planecli support
    app.py               # Root cyclopts App, sub-app registration, entry point
    cache.py             # Disk-based caching with cashews
    config.py            # Config loading (args > env > file)
    exceptions.py        # Custom exception hierarchy
    api/
        client.py        # PlaneClient singleton wrapper
        async_sdk.py     # Async wrapper with rate limiter
    commands/
        cache_cmd.py     # Cache management
        comments.py      # Comment CRUD
        cycles.py        # Cycle CRUD + item management
        documents.py     # Document CRUD
        labels.py        # Label CRUD
        modules.py       # Module CRUD
        projects.py      # Project CRUD
        states.py        # State CRUD
        users.py         # User listing
        work_items.py    # Work item CRUD + search + assign
    formatters/
        __init__.py      # Rich table and JSON output
    utils/
        colors.py        # Color helpers for priorities, states, labels
        fuzzy.py         # Fuzzy search with rapidfuzz
        resolve.py       # Resource resolution (UUID/identifier/fuzzy)
tests/
    conftest.py          # Shared fixtures
    test_cache.py        # Cache tests
    test_config.py       # Config tests
    test_fuzzy.py        # Fuzzy search tests
    test_resolve.py      # Resource resolution tests
    test_commands/       # Command tests
```

### Technologies

| Technology | Purpose |
|---|---|
| [cyclopts](https://cyclopts.readthedocs.io/) | CLI framework (argument parsing, sub-commands) |
| [Rich](https://rich.readthedocs.io/) | Formatted tables and colored terminal output |
| [rapidfuzz](https://github.com/rapidfuzz/RapidFuzz) | Fuzzy search for resource resolution |
| [plane-sdk](https://github.com/makeplane/plane-python-sdk) | Official Plane.so Python SDK |
| [cashews](https://github.com/krupen/cashews) | Disk-based API response caching |
| [hatchling](https://hatch.pypa.io/) | Build backend for packaging |
| [pytest](https://docs.pytest.org/) | Testing framework |
| [ruff](https://docs.astral.sh/ruff/) | Python linter and formatter |

## Troubleshooting

| Issue | Solution |
|---|---|
| `AuthenticationError: Missing API key` | Run `planecli configure` or set `PLANE_API_KEY` (your Personal Access Token) and `PLANE_BASE_URL` environment variables |
| `AuthenticationError: Missing workspace slug` | Set `PLANE_WORKSPACE` or add `workspace=slug` to `~/.plane_api` |
| `ResourceNotFoundError` with a resource name | Check the name with `planecli <resource> list`; fuzzy search needs at least 60% similarity |
| API connection error | Verify `PLANE_BASE_URL` is correct and reachable |
| JSON output doesn't appear with table | Table goes to stderr, JSON to stdout — use `2>/dev/null` to suppress the table |
| Stale or incorrect data | Run `planecli cache clear` to reset the cache |

## Notes

- The project is in **Alpha** (v0.1.0) — the command interface may change
- The Documents (Pages) API in the Plane SDK has limited support; list, update, and delete use direct HTTP requests as a workaround
- Compatible with Plane.so SaaS and self-hosted instances
- The `~/.plane_api` file is saved with restricted permissions (`0600`)

## License

MIT
