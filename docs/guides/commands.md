# Writing commands

Rules for adding or changing a command in `src/planecli/commands/`.

## Plane SDK access

- Wrap single SDK calls in `run_sdk(fn, *args)` and paginated lists in `paginate_all_async(list_fn, ...)`, because the SDK is synchronous. Both run in a thread pool behind a concurrency semaphore and retry 429/502/503/504 via tenacity. See [ADR-0001](../adr/0001-async-wrapper-over-sync-sdk.md).
- Use `create_client()` for concurrent batches, so each thread gets its own client instead of sharing the singleton's `requests.Session`.
- Check [Plane API quirks](plane-api.md) for the known exceptions.

## Resolving references

Call the `resolve_<x>_async` functions from `utils/resolve.py`. They try UUID, then identifier, then fuzzy name. See [ADR-0002](../adr/0002-fuzzy-resource-resolution.md).

## Cache

For a resource with a `cached_list_<x>`:

- Read through `cached_list_<x>(...)`, which returns **plain dicts**, not Pydantic models.
- After any create, update, or delete, call `await invalidate_resource("<resource>", workspace, project_id)`.

Everything else goes straight to the API: see [Not Cached](../caching.md#not-cached). The reasoning is in [ADR-0004](../adr/0004-disk-cache-ttls-and-keys.md).

## Errors

Wrap SDK calls in `try/except PlaneError` and `raise handle_api_error(e)`. Raise `ValidationError` or `ResourceNotFoundError` for user-facing problems.

## Output

- Commands that return data or a record (list, show, create, update, and the like) take `json: bool = False` and pass `as_json=json` to the formatter. Action-only commands have no `--json`: delete, `cycle add-item`, `cycle remove-item`, `wi assign`, and `cache clear`.
- Keep table output on **stderr**, so `--json 2>/dev/null` yields clean JSON. See [ADR-0005](../adr/0005-dual-output-contract.md).
- Document destructive behaviour rather than prompting for confirmation. See [ADR-0008](../adr/0008-destructive-deletes-are-documented-not-prompted.md).

## Flags and parameters

- Guard a flag with `is not None` when its value is validated or an empty value means something, so `--priority ""` reaches the validator and is rejected. A plain presence check such as `if project:` is fine elsewhere.
- Numpydoc parameter docstrings become `--help` text, where cyclopts/Rich renders literal angle brackets as markup and they vanish. Write "a paragraph tag", not `<p>`.
- Use the cyclopts idioms: sub-app aliases via `name=["module", "modules"]`, subcommands via `@app.command(name="list", alias="ls")`, and short flags via `Annotated[str, Parameter(alias="-p")]`.
- Add a new global flag the way `--verbose`/`-v` and `--no-cache` work: strip it from `sys.argv` in `main()` before cyclopts parses, because cyclopts does not own them.

## Imports

Import SDK models and cache helpers *inside* the command function, to keep CLI startup fast. Sub-app registration in `app.py` uses `# noqa: E402` deliberately.
