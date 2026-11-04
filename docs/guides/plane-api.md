# Plane API quirks

Places where the Plane API or `plane-sdk` behaves differently from what you would expect. Check here when calling the API or when a response does not match the SDK's model.

## SDK escape hatches

See [ADR-0003](../adr/0003-sdk-escape-hatches.md) for the reasoning.

- **Work items:** `WorkItemDetail` validation fails because the API returns `assignees`/`labels` as UUID strings. Resolvers use the raw `client.work_items._get(path)`, which returns a dict directly. Each site has a `NOTE:` comment.
- **Documents (Pages):** SDK support is incomplete. In `commands/documents.py`, `show` and `create` use the SDK through `run_sdk`. `list`, `update`, and `delete` call the HTTP API with `requests` and an `X-Api-Key` header through `asyncio.to_thread`, so they run with no concurrency semaphore and no retries.
- **Estimate points:** there is no API endpoint. `cached_list_estimate_points` derives them from work items fetched with `expand=estimate_point`.

## Writes the API can ignore

A `200` is not always a write. Some endpoints accept a mutation and ignore it: the intake `PATCH` returns `200` with the record unchanged when the caller is not a project Admin. Where that is known, read the raw response and compare the field you meant to change *before* enriching it for display, then raise `APIError`. See [ADR-0007](../adr/0007-verify-writes-the-api-can-silently-ignore.md).

## Intake

Intake mutations take the work item UUID, not the intake wrapper `id`: use the `Issue ID` column of `intake ls`. `intake delete` also deletes the underlying work item for any status other than `accepted`.
