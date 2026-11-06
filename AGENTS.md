# PlaneCLI

Python CLI for Plane.so (SaaS or self-hosted) that resolves any resource by name, identifier (`ABC-123`), or UUID.

## Commands

Uses `uv`, with tasks in the Makefile (`make help` lists them).

- `make check`: lint, format check, and tests. CI runs it too, so run it before committing.
- `make run ARGS="wi ls -p Frontend"`: run the CLI.
- `uv run pytest tests/test_resolve.py::test_name -v`: run a single test.

## Always

- Write docs, comments, and commit messages in English.
- Cite ADRs or guides in code comments, because tracker issue IDs and URLs are unreachable after delivery.

## Read when relevant

- [Writing commands](docs/guides/commands.md): before adding or changing a command, flag, or output.
- [Plane API quirks](docs/guides/plane-api.md): before calling the Plane API or SDK, or when a response does not match the model.
- [Testing](docs/guides/testing.md): before writing tests or running a PR's code.
- [Architecture](docs/architecture.md): to find where code lives or how a request flows.
- [Caching](docs/caching.md): when touching cached reads, TTLs, or invalidation.
- [Glossary](CONTEXT.md): when naming anything users see.
- [ADRs](docs/adr/): before changing a design decision.
