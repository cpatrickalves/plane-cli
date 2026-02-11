"""Root cyclopts App, sub-app registration, and entry point."""

from __future__ import annotations

import os
import sys

import cyclopts

from planecli import __version__
from planecli.exceptions import PlaneCLIError
from planecli.formatters import error_console

app = cyclopts.App(
    name="planecli",
    help="CLI for Plane.so project management.",
    version=__version__,
)

# Import and register sub-apps
from planecli.commands.cache_cmd import cache_app  # noqa: E402
from planecli.commands.comments import comment_app  # noqa: E402
from planecli.commands.cycles import cycle_app  # noqa: E402
from planecli.commands.documents import doc_app  # noqa: E402
from planecli.commands.labels import label_app  # noqa: E402
from planecli.commands.modules import module_app  # noqa: E402
from planecli.commands.projects import project_app  # noqa: E402
from planecli.commands.states import state_app  # noqa: E402
from planecli.commands.users import user_app  # noqa: E402
from planecli.commands.work_items import wi_app  # noqa: E402

app.command(project_app)
app.command(wi_app)
app.command(comment_app)
app.command(doc_app)
app.command(user_app)
app.command(module_app)
app.command(label_app)
app.command(state_app)
app.command(cycle_app)
app.command(cache_app)


# Top-level commands
@app.command
async def whoami(*, json: bool = False) -> None:
    """Show current authenticated user."""
    from plane.errors import PlaneError

    from planecli.api.async_sdk import run_sdk
    from planecli.api.client import get_client, handle_api_error
    from planecli.formatters import output_single

    try:
        client = get_client()
        me = await run_sdk(client.users.get_me)
        data = me.model_dump()
    except PlaneError as e:
        raise handle_api_error(e)

    fields = [
        ("id", "ID"),
        ("display_name", "Display Name"),
        ("first_name", "First Name"),
        ("last_name", "Last Name"),
        ("email", "Email"),
    ]
    output_single(data, fields, title="Current User", as_json=json)


@app.command
def configure() -> None:
    """Configure PlaneCLI credentials interactively."""
    import shutil

    from planecli.cache import get_cache_dir
    from planecli.config import CONFIG_FILE, save_config
    from planecli.formatters import console

    console.print("[bold]PlaneCLI Configuration[/]")
    console.print()

    base_url = input("Plane base URL (e.g. https://api.plane.so): ").strip()
    api_key = input("API key: ").strip()
    workspace = input("Workspace slug: ").strip()

    if not base_url or not api_key or not workspace:
        error_console.print("[bold red]Error:[/] All fields are required.")
        sys.exit(1)

    save_config(base_url, api_key, workspace)

    # Clear cache when credentials change (data may be from different instance)
    cache_dir = get_cache_dir()
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)
        console.print("[dim]Cache cleared.[/]")

    console.print(f"\n[green]Configuration saved to {CONFIG_FILE}[/]")


def main() -> None:
    """Entry point for the CLI."""
    from planecli.cache import cache, set_no_cache, setup_cache

    # Handle --no-cache flag via sys.argv (before cyclopts parses)
    no_cache = os.environ.get("PLANECLI_NO_CACHE", "").strip() in ("1", "true", "yes")
    if "--no-cache" in sys.argv:
        sys.argv.remove("--no-cache")
        no_cache = True

    setup_cache()
    set_no_cache(no_cache)

    try:
        app()
    except PlaneCLIError as exc:
        error_console.print(f"[bold red]Error:[/] {exc.message}")
        if exc.hint:
            error_console.print(f"[cyan]Hint:[/] {exc.hint}")
        sys.exit(exc.exit_code)
    except KeyboardInterrupt:
        sys.exit(130)
    finally:
        # Close the cache backend cleanly
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(cache.close())
            else:
                loop.run_until_complete(cache.close())
        except Exception:
            pass
