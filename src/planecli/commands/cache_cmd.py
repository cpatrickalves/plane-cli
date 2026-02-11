"""Cache management commands."""

from __future__ import annotations

import shutil

import cyclopts

from planecli.cache import get_cache_dir

cache_app = cyclopts.App(
    name="cache",
    help="Manage the local API cache.",
)


@cache_app.command
def clear() -> None:
    """Clear the entire local cache."""
    from planecli.formatters import console

    cache_dir = get_cache_dir()
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)
        console.print(f"[green]Cache cleared: {cache_dir}[/]")
    else:
        console.print("[yellow]No cache directory found.[/]")
