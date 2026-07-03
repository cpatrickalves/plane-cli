# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- `wi show` now bundles the work item's comments in the same call. In `--json` output the `comments` field is a list (`[]` when there are none) or `null` if the comment fetch failed — the work item still returns and the command exits 0. In human output a `Comments` section follows the details, showing `(none)` or `(failed to load)` as appropriate
- `--no-comments` flag on `wi show` to skip the comment fetch (the `comments` key is then omitted from JSON)
- `--limit` / `-l` option on `comment ls` (default 50): selects the most recent N comments, still rendered oldest → newest
- Per-work-item comment cache (1-minute TTL), invalidated on `comment create`/`update`/`delete`

## [0.5.1] - 2026-07-03

<!-- The 0.4.x/0.5.0 tags were not documented separately; the user-facing
     changes released after 0.3.0 are consolidated in this entry. -->

### Added
- `--parent` filter in `wi list` to list the child work items of a parent, referenced by identifier (`ABC-123`), UUID, or name
- `--status` option in the `module create` and `module update` commands (values: `backlog`, `planned`, `in-progress`, `paused`, `completed`, `cancelled`), with English and Portuguese aliases (e.g., `em andamento`, `concluído`, `cancelado`) and validation with a clear error message

### Documentation
- Added the `docs/adr/` Architecture Decision Records, `docs/architecture.md`, and root `AGENTS.md`
- Renamed `docs/03-caching.md` to `docs/caching.md` and corrected the cached-resource reference

## [0.3.0] - 2026-02-12

### Added
- Structured logging with loguru and reduced API calls via smart caching
- Automatic retry with tenacity for rate limits and transient API errors
- estimate_point UUID resolution in the `--estimate` parameter of the `wi` command

### Fixed
- Fixed the SDK validation bypass for assignees/labels in work item resolution
- Removed silent exception suppression in the `wi` assignees filter

### Changed
- Removed redundant Project column from the `wi list` listing
- Updated README terminology from "API Key" to "Personal Access Token"

## [0.2.0] - 2026-02-11

### Added
- Disk-based API response caching with cashews for faster repeated requests
- Async execution for all API calls using `asyncio.to_thread` and parallel execution
- Comma-separated state and labels filtering in `wi list` command
- Color styling for labels, states, priorities, and work item tables
- Commands for cycles, labels, and states management
- Comment update and delete operations
- Made `--project` optional in `wi list`, listing all projects when omitted
- Row separator lines and vertical padding in table output
- Comprehensive test coverage for config, fuzzy matching, and resource resolution utilities

### Changed
- Migrated all API calls from synchronous to async with thread pool and semaphore rate limiting
- Rewritten README with improved structure, quick start guide, and comprehensive command reference
- Added Makefile with development tasks
- Updated installation instructions with `uv tool install` option

## [0.1.0] - 2026-02-11

### Added
- Initial release of PlaneCLI
- CLI application with commands for projects, work items, comments, documents, users, and modules
- Configuration via arguments, environment variables (`PLANE_BASE_URL`, `PLANE_API_KEY`, `PLANE_WORKSPACE`), and `~/.plane_api` file
- Fuzzy resource search using rapidfuzz
- Rich table output (stderr) and JSON output (stdout) with `--json` flag
- Smart resource resolution: UUID, identifier (e.g., `ABC-123`), or name search
- Cursor-based pagination for resource listing
