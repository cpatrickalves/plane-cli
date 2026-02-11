# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Color styling for labels, states, priorities, and work item tables
- Commands for cycles, labels, and states
- Comment update and delete operations
- Made `--project` optional in `wi list`, listing all projects when omitted
- Row separator lines and vertical padding in table output

### Changed
- Added Makefile with development tasks
- Updated README with development section

## [0.1.0] - 2026-02-11

### Added
- Initial release of PlaneCLI
- CLI application with commands for projects, work items, comments, documents, users, and modules
- Configuration via arguments, environment variables (`PLANE_BASE_URL`, `PLANE_API_KEY`, `PLANE_WORKSPACE`), and `~/.plane_api` file
- Fuzzy resource search using rapidfuzz
- Rich table output (stderr) and JSON output (stdout) with `--json` flag
- Smart resource resolution: UUID, identifier (e.g., `ABC-123`), or name search
- Cursor-based pagination for resource listing
- Test coverage for config, fuzzy matching, and resource resolution utilities
- Installation documentation with `uv tool install` option
