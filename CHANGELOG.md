# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- `--status` option in the `module create` and `module update` commands (values: `backlog`, `planned`, `in-progress`, `paused`, `completed`, `cancelled`), with English and Portuguese aliases (e.g., `em andamento`, `concluído`, `cancelado`) and validation with a clear error message

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
