# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/)
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.6.0] - 2026-11-06

### Added
- `planecli attachment get` (aliases `download`, `dl`) downloads work item attachments: `get ISSUE [SELECTOR] [--all] [--dir DIR | -o FILE] [--force] [--json]`. SELECTOR is an attachment id or exact file name; a name shared by several attachments needs an id or `--all`, which saves every match with repeated names suffixed (`image-2.png`). Files stream to disk through the presigned storage redirect, and existing files are not overwritten without `--force`
- `planecli intake` command group: `ls`, `create`, `accept`, `decline`, `delete`, `enabled` for project intake queues. Mutations take the work item UUID shown in the `Issue ID` column of `intake ls`. `accept`/`decline` require the project Admin role (the API silently ignores the change for lower roles, so the CLI verifies it and fails loudly). `delete` also permanently deletes the underlying work item for any status other than `accepted`
- `planecli --version` shows the commit that runs when installed from git or as an editable checkout (for example `0.6.0+5c93a2e`)

### Changed
- The bundled `planecli` agent skill (`skills/SKILL.md`) is shorter and now covers rate limits, partial creates, search, `-d` wrapping, and the fact that descriptions take raw HTML, not markdown. Command aliases moved to `skills/references/command-reference.md`

### Fixed
- `project create` no longer fails with a validation error on every call: `CreateProject` now receives the required `identifier` at construction. Thanks to Jay Smith (#5)
- `project create` without `-i` now derives the identifier from the first 5 ASCII letters of the name (accents folded, digits and symbols dropped), instead of the first 3 raw characters, which could include spaces and punctuation. Names with no usable letters fail with a validation error asking for `-i`, and a 409 on a derived identifier names the value and suggests `-i`. Thanks to Omar Adel (#8)
- `document create` no longer crashes before the API call: `CreatePage` now receives the required `description_html` at construction (`<p></p>` when `--content` is omitted)
- `doc create` and `doc update` convert `--content` to HTML: blank lines separate paragraphs, single newlines become line breaks, bare URLs become links, and backticks and fences become code. Before, the text went into one paragraph and lost its line breaks. `doc update --content ""` clears the content. Thanks to Liewzheng (#21)
- `doc delete` reports an HTTP error with exit code 4 (2 for a 401) instead of a traceback. Some self-hosted servers answer 405 to page deletes
- `doc show`, `create`, `update` and `list` keep line and paragraph breaks in the `Content` field (`content_text` in `--json`) and show entities such as `&lt;` as text

## [0.5.1] - 2026-07-03

### Added
- `wi show` now includes the work item's comments in the same call. In `--json` output, the `comments` field is a list (`[]` when there are no comments) or `null` if the comment fetch fails — the work item is still returned and the command exits with code 0. In human-readable output, a `Comments` section follows the details, showing `(none)` or `(failed to load)` as appropriate
- `--no-comments` flag on `wi show` to skip fetching comments (the `comments` key is then omitted from JSON)
- `--limit` / `-l` option on `comment ls` (default 50): selects the N most recent comments, still rendered oldest to newest
- Per-work-item comment cache (1-minute TTL), invalidated on `comment create`/`update`/`delete`
- `--parent` filter on `wi list` to list the child work items of a parent, referenced by identifier (`ABC-123`), UUID, or name
- `--status` option on the `module create` and `module update` commands (values: `backlog`, `planned`, `in-progress`, `paused`, `completed`, `cancelled`), with English and Portuguese aliases (e.g. `em andamento`, `concluído`, `cancelado`) and validation with a clear error message

### Fixed
- `comment ls --limit 0` (or a negative value) now returns no results
- `wi show` no longer claims comments "failed to load" when the fetch was never attempted
- A failure to fetch members now degrades gracefully instead of aborting the comment fetch

### Documentation
- Added the Architecture Decision Records in `docs/adr/`, `docs/architecture.md`, and `AGENTS.md` at the root
- Renamed `docs/03-caching.md` to `docs/caching.md` and fixed the reference to the cached resource

## [0.3.0] - 2026-02-12

### Added
- Structured logging with loguru and fewer API calls via smart caching
- Automatic retry with tenacity for rate limits and transient API errors
- estimate_point UUID resolution in the `--estimate` parameter of the `wi` command

### Changed
- Removed the redundant Project column from the `wi list` output
- Updated the README terminology from "API Key" to "Personal Access Token"

### Fixed
- Fixed the SDK validation bypass for assignees/labels in work item resolution
- Removed the silent suppression of exceptions in the `wi` command's assignees filter

## [0.2.0] - 2026-02-11

### Added
- Disk caching of API responses with cashews for faster repeated requests
- Async execution of all API calls using `asyncio.to_thread` and parallel execution
- Comma-separated state and label filtering in the `wi list` command
- Color styling for labels, states, priorities, and work item tables
- Commands for managing cycles, labels, and states
- Comment update and delete operations
- `--project` became optional in `wi list`, listing all projects when omitted
- Separator lines and vertical spacing in table output
- Comprehensive test coverage for config, fuzzy matching, and resource resolution

### Changed
- Migrated all API calls from synchronous to asynchronous with a thread pool and semaphore-based rate limiting
- Rewrote the README with improved structure, a quick-start guide, and a complete command reference
- Added a Makefile with development tasks
- Updated the installation instructions with the `uv tool install` option

## [0.1.0] - 2026-02-11

### Added
- Initial release of PlaneCLI
- CLI application with commands for projects, work items, comments, documents, users, and modules
- Configuration via arguments, environment variables (`PLANE_BASE_URL`, `PLANE_API_KEY`, `PLANE_WORKSPACE`), and the `~/.plane_api` file
- Fuzzy resource search using rapidfuzz
- Rich table output (stderr) and JSON output (stdout) with the `--json` flag
- Smart resource resolution: UUID, identifier (e.g. `ABC-123`), or name search
- Cursor-based pagination in resource listing
