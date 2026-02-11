# PlaneCLI

## Overview

PlaneCLI is a command-line interface for [Plane.so](https://plane.so), an open-source project management tool. The CLI allows you to manage projects, work items, modules, documents, comments, and users directly from the terminal, without needing to access the web interface.

The main differentiator of PlaneCLI is its intelligent resource resolution via **fuzzy search**: you can reference any resource by name, identifier (e.g. `ABC-123`), or UUID, and the CLI automatically finds the closest match. All commands support formatted table output (default) or JSON for integration with other tools.

## Features

- **Work Items/Issues Management**: Create, list, update, and delete work items with support for sub-issues, labels, states, priorities, and assignees
- **Projects**: List, create, and view project details with state filters
- **Modules**: Manage project modules (sprints, versions, etc.)
- **Documents**: Create, list, read, update, and delete project documents
- **Comments**: Add and list comments on work items
- **Users**: List workspace members and identify the authenticated user
- **Fuzzy Search**: Intelligent resource resolution by name, identifier, or UUID
- **Dual Output**: Formatted Rich tables (stderr) or JSON (stdout) with `--json` flag
- **Flexible Configuration**: Support for environment variables, `~/.plane_api` file, or interactive setup

## Project Structure

```bash
├── LICENSE                       # MIT License
├── pyproject.toml              # Project configuration and dependencies
├── README.md                    # Project documentation
├── src/
│   └── planecli/
│       ├── __init__.py          # Package version
│       ├── __main__.py         # Support for python -m planecli
│       ├── app.py                # Root cyclopts App, sub-app registration, and entry point
│       ├── config.py            # Config loading (args > env > file)
│       ├── exceptions.py        # Custom exception hierarchy
│       ├── api/
│       │   └── client.py       # PlaneClient singleton wrapper
│       ├── commands/
│       │   ├── comments.py       # Comment commands
│       │   ├── documents.py      # Document commands
│       │   ├── modules.py         # Module commands
│       │   ├── projects.py        # Project commands
│       │   ├── users.py            # User commands
│       │   └── work_items.py     # Work item/issue commands
│       ├── formatters/
│       │   └── __init__.py         # Output formatting (Rich table / JSON)
│       └── utils/
│           ├── fuzzy.py            # Fuzzy search with rapidfuzz
│           └── resolve.py          # Intelligent resource resolution
├── tests/
│   ├── conftest.py                # Shared fixtures
│   ├── test_config.py            # Config tests
│   ├── test_fuzzy.py             # Fuzzy search tests
│   ├── test_resolve.py           # Resource resolution tests
│   └── test_commands/          # Command tests
└── docs/
    └── plans/                      # Planning documents
```

## Prerequisites

- `Python >= 3.11`
- `uv` (package and virtual environment manager)
- A [Plane.so](https://plane.so) or self-hosted account with a generated API key
- Access to a Plane workspace

## Technologies Used

| Technology | Purpose |
|---|---|
| [cyclopts](https://cyclopts.readthedocs.io/) | CLI framework (argument parsing, sub-commands) |
| [Rich](https://rich.readthedocs.io/) | Formatted tables and colored terminal output |
| [rapidfuzz](https://github.com/rapidfuzz/RapidFuzz) | Fuzzy search for intelligent resource resolution |
| [plane-sdk](https://github.com/makeplane/plane-python-sdk) | Official Plane.so Python SDK |
| [hatchling](https://hatch.pypa.io/) | Build backend for packaging |
| [pytest](https://docs.pytest.org/) | Testing framework |
| [ruff](https://docs.astral.sh/ruff/) | Python linter and formatter |

## Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd planecli-compound
   ```

2. Install dependencies with `uv`:

   ```bash
   uv sync
   ```

3. Configure credentials (choose one option):

   **Option A - Interactive setup:**

   ```bash
   uv run planecli configure
   ```

   **Option B - Environment variables:**

   ```bash
   export PLANE_BASE_URL="https://api.plane.so"
   export PLANE_API_KEY="your-api-key"
   export PLANE_WORKSPACE="your-workspace-slug"
   ```

   **Option C - Configuration file:**
   Create the file `~/.plane_api`:

   ```ini
   base_url=https://api.plane.so
   api_key=your-api-key
   workspace=your-workspace-slug
   ```

> **Configuration precedence:** CLI arguments > environment variables > `~/.plane_api` file

## Running the Project

```bash
# Check authenticated user
uv run planecli whoami

# List projects
uv run planecli project list

# List work items for a project
uv run planecli wi list --project "Frontend"

# Create a work item
uv run planecli wi create "Fix login timeout" --project "Frontend" --assign me --priority urgent

# Create a sub-issue
uv run planecli wi create "Review PR #345" --parent ABC-234 --assign "Luiz" --state "In Review"

# Update a work item state
uv run planecli wi update ABC-123 --state "In Review"

# Add a comment to a work item
uv run planecli comment create ABC-123 --body "Fixed in PR #456"

# List comments
uv run planecli comment list ABC-123

# List documents for a project
uv run planecli document list --project "Backend"

# List workspace users
uv run planecli users list

# JSON output (useful for integration with other tools)
uv run planecli wi list --project "Frontend" --json

# Sort results
uv run planecli wi list --sort updated --limit 10
```

### Command Aliases

| Full command | Aliases |
|---|---|
| `planecli work-item` | `wi`, `issues`, `issue` |
| `planecli project` | - |
| `planecli comment` | - |
| `planecli document` | `doc` |
| `planecli users` | `user` |
| `planecli module` | - |
| Subcommand `list` | `ls` |
| Subcommand `read` | `show` |
| Subcommand `create` | `new` |

## Notes and Restrictions

- The project is in **Alpha** phase (v0.1.0) and the command interface may change
- The **Documents (Pages)** API in the Plane SDK has limited support: list, update, and delete operations use direct HTTP requests as a workaround
- Fuzzy search uses a default threshold of 60 (scale 0-100) to consider a valid match
- The `~/.plane_api` file is saved with restricted permissions (`0600`) to protect the API key
- Compatible with Plane.so SaaS and self-hosted versions

## Common Issues

| Issue | Solution |
|---|---|
| `AuthenticationError: Missing API key` | Configure credentials with `planecli configure` or set the `PLANE_API_KEY` and `PLANE_BASE_URL` environment variables |
| `AuthenticationError: Missing workspace slug` | Set the `PLANE_WORKSPACE` variable or add `workspace=slug` to the `~/.plane_api` file |
| `ResourceNotFoundError` when using resource name | Verify the name is correct with `planecli <resource> list`; fuzzy search requires at least 60% similarity |
| API connection error | Check that `PLANE_BASE_URL` is correct and accessible |
| JSON output doesn't appear with table | The table is sent to stderr and JSON to stdout; use `2>/dev/null` to see only the JSON |

