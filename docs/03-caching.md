# Caching

PlaneCLI uses a persistent disk-based cache to reduce redundant API calls. Most CLI commands resolve resources by name (fuzzy matching), which requires fetching full lists of projects, states, labels, and members from the Plane API. Without caching, a single `planecli wi list` across 10 projects can trigger 30+ API calls. With caching, warm runs eliminate >80% of those calls.

## How It Works

The cache sits between the CLI commands and the Plane API. When a command needs a list of resources (e.g., all states in a project), it first checks the local cache. On a cache hit, the data is returned instantly without any API call. On a miss, the data is fetched from the API, stored in the cache, and then returned.

```
Command → resolve/enrich → cache check → [HIT] → return cached data
                                        → [MISS] → Plane API → store in cache → return data
```

The cache is backed by SQLite (via [diskcache](https://github.com/grantjenks/python-diskcache)) and managed through the [cashews](https://github.com/Krukov/cashews) library.

### Storage Location

| Platform | Path |
|----------|------|
| macOS | `~/Library/Caches/planecli/` |
| Linux | `$XDG_CACHE_HOME/planecli/` (default: `~/.cache/planecli/`) |

The cache is limited to **100 MB** with LRU eviction.

## What Is Cached

Only **slowly-changing resource definitions** are cached. Data that changes frequently is always fetched fresh.

### Cached Resources

| Resource | TTL | What It Is | Used For |
|----------|-----|------------|----------|
| Workspace members | 1 hour | The list of users in the workspace | Resolving `--assignee` flags, displaying assignee names |
| Project list | 5 min | All projects in the workspace | Resolving `--project` flags, `wi list` across all projects |
| States | 10 min | State definitions per project (e.g., Todo, In Progress, Done) | Resolving `--state` flags, displaying state names/colors |
| Labels | 10 min | Label definitions per project | Resolving `--labels` flags, displaying label names/colors |
| Modules | 5 min | Module list per project | Resolving `--module` flags |
| Cycles | 5 min | Cycle list per project | Resolving cycle names |

### NOT Cached

| Resource | Reason |
|----------|--------|
| Work items | Change frequently; stale data would be confusing |
| Comments | Change frequently |
| Documents / Pages | Change frequently |
| Individual resource lookups (by UUID/identifier) | Single-resource fetches should always be fresh |

**Important distinction**: The *state assigned to a work item* is always fresh (work items are never cached). What's cached is the *list of state definitions* — the lookup table that maps state UUIDs to display names and colors.

## Cache Keys

All cache keys are prefixed with a hash of the Plane `base_url` to isolate data across different Plane instances. This prevents returning cached data from one instance when you switch to another.

Key format: `{url_hash}:{resource}:{workspace}[:{project_id}]`

Examples:
- `a1b2c3d4e5f6:members:my-workspace`
- `a1b2c3d4e5f6:states:my-workspace:project-uuid-123`

## Cache Invalidation

### Automatic (After Writes)

Write commands automatically invalidate the relevant cache entry:

| Operation | Invalidates |
|-----------|-------------|
| `project create/update/delete` | Project list for the workspace |
| `state create/update/delete` | States for that project |
| `label create/update/delete` | Labels for that project |
| `module create/update/delete` | Modules for that project |
| `cycle create/update/delete` | Cycles for that project |
| `configure` | Entire cache (credentials may have changed) |

Members are not mutated via the CLI, so they rely on TTL expiry only.

### Manual

Clear the entire cache:

```bash
planecli cache clear
```

## Bypassing the Cache

### Per-Command

Use `--no-cache` to skip cache reads for a single invocation. The fresh data still gets written to the cache, so subsequent runs benefit from it:

```bash
planecli --no-cache project list
```

### Via Environment Variable

```bash
export PLANECLI_NO_CACHE=1
planecli project list
```

Accepted values: `1`, `true`, `yes`.

## Error Handling

Cache failures never block CLI usage. If the cache is corrupted or the disk is full:

1. A warning is printed to stderr (e.g., `Warning: Cache read error, fetching from API: ...`)
2. The CLI falls back to direct API calls
3. The command completes normally

If the cache becomes corrupted beyond recovery, run `planecli cache clear` to delete it entirely.
