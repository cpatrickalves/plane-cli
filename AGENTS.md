# PlaneCLI

A Python CLI for [Plane.so](https://plane.so) (SaaS or self-hosted) that manages projects, work items, cycles, modules, documents, labels, states, and comments. Its defining feature is **fuzzy resource resolution**: any resource can be referenced by name, identifier (`ABC-123`), or UUID. Built with cyclopts, Rich, rapidfuzz, cashews, and the official `plane-sdk`.

## Language

All docs, comments, and commit messages in English.

## Commands

Everything runs through `uv`; common tasks are wrapped in the Makefile.

```bash
make install                       # uv sync (dev environment)
make test                          # uv run pytest tests/
make lint                          # ruff check src/
make lint-fix                      # ruff check --fix src/
make format                        # ruff format src/ tests/
make check                         # lint + test — run before committing
make run ARGS="wi ls -p Frontend"  # run the CLI
```

Single test: `uv run pytest tests/test_resolve.py::test_name -v`. Line length 100, Python >= 3.11, ruff selects `E, F, I, W`.

## Structure

```
src/planecli/
  app.py           # Root cyclopts App; main() entry point; sub-app registration
  commands/        # One module per resource (list/show/create/update/delete). New features go here.
  utils/resolve.py # Resolution layer: resolve_<x>/resolve_<x>_async (UUID → identifier → fuzzy name)
  utils/fuzzy.py   # rapidfuzz token_sort_ratio, threshold 60
  api/             # client.py (PlaneClient singleton); async_sdk.py (async wrapper)
  cache.py         # cashews disk cache; one cached_list_<x> per resource
  formatters/      # output() / output_single() — table to stderr, JSON to stdout
  exceptions.py    # PlaneCLIError subclasses with message/hint/exit_code
```

Request flow: **command → resolve → async SDK wrapper → (cache | Plane SDK) → formatter**. See [docs/architecture.md](docs/architecture.md).

## Conventions

- **Never call the sync Plane SDK directly from a command.** Wrap single calls in `run_sdk(fn, *args)` and paginated lists in `paginate_all_async(list_fn, ...)`. For concurrent batches use `create_client()` (a fresh client per thread — don't share the singleton's `requests.Session`). See [ADR-0001](docs/adr/0001-async-wrapper-over-sync-sdk.md).
- **Reads go through the cache layer.** Resolvers and list commands call `cached_list_<x>(...)`, which returns **plain dicts** (not Pydantic models). After any create/update/delete, call `await invalidate_resource("<resource>", workspace, project_id)`. See [ADR-0004](docs/adr/0004-disk-cache-ttls-and-keys.md).
- **Error handling.** Wrap SDK calls in `try/except PlaneError` and `raise handle_api_error(e)`. Raise `ValidationError`/`ResourceNotFoundError` for user-facing problems. Exit codes: Auth=2, NotFound=3, API=4, Validation=5.
- **`--json` flag.** Every read/mutate command takes `json: bool = False` and passes `as_json=json` to the formatter. Table output stays on **stderr** so `--json 2>/dev/null` yields clean JSON. See [ADR-0005](docs/adr/0005-dual-output-contract.md).
- **Lazy imports.** Import SDK models and cache helpers *inside* the command function to keep CLI startup fast (sub-app registration in `app.py` uses `# noqa: E402` deliberately).
- **cyclopts idioms.** Sub-apps declare aliases via `name=["module", "modules"]`; subcommands via `@app.command(name="list", alias="ls")`; short flags via `Annotated[str, Parameter(alias="-p")]`. Numpydoc parameter docstrings become `--help` text.

## Gotchas

- **`--verbose`/`-v` and `--no-cache` are stripped from `sys.argv` in `main()` before cyclopts parses** — cyclopts does not own them. Add new global flags the same way.
- **SDK model mismatches require escape hatches** (see [ADR-0003](docs/adr/0003-sdk-escape-hatches.md)):
  - Work items: `WorkItemDetail` validation fails because the API returns `assignees`/`labels` as UUID strings. Resolvers use raw `client.work_items._get(path)` to get a dict directly. Each site has a `NOTE:` comment.
  - Documents (Pages): SDK support is incomplete; `commands/documents.py` calls the HTTP API directly with `requests` + `X-Api-Key` via `run_sdk(requests.get, ...)`.
  - Estimate points: no API endpoint; `cached_list_estimate_points` derives them from work items with `expand=estimate_point`.
- **Reference versioned docs, not tracker issues.** Do not cite Plane/Linear issue IDs or external tracker URLs in code comments — they are unreachable after delivery. Point to an ADR or guide instead.
- **Tests never hit a real Plane instance.** `conftest.py` autouses a `mem://` cache backend and provides a `mock_plane_client` fixture. Mock the SDK/resolvers; prefer testing pure logic (normalizers, fuzzy matching, resolution) directly.

## Key docs

- [Architecture](docs/architecture.md) — layers and request flow
- [Caching](docs/caching.md) — TTLs, keys, invalidation
- [ADRs](docs/adr/) — the decisions behind the design
