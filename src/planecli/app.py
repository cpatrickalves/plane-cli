"""Root cyclopts App, sub-app registration, and entry point."""

from __future__ import annotations

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


# Top-level commands
@app.command
def whoami(*, json: bool = False) -> None:
    """Show current authenticated user."""
    from plane.errors import PlaneError

    from planecli.api.client import get_client, handle_api_error
    from planecli.formatters import output_single

    try:
        client = get_client()
        me = client.users.get_me()
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
    console.print(f"\n[green]Configuration saved to {CONFIG_FILE}[/]")


def main() -> None:
    """Entry point for the CLI."""
    try:
        app()
    except PlaneCLIError as exc:
        error_console.print(f"[bold red]Error:[/] {exc.message}")
        if exc.hint:
            error_console.print(f"[cyan]Hint:[/] {exc.hint}")
        sys.exit(exc.exit_code)
    except KeyboardInterrupt:
        sys.exit(130)
