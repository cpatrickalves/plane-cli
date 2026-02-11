"""User commands."""

from __future__ import annotations

import cyclopts
from plane.errors import PlaneError

from planecli.api.async_sdk import run_sdk
from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.formatters import output

user_app = cyclopts.App(
    name=["user", "users"],
    help="Manage users.",
)

USER_COLUMNS = [
    ("id", "ID"),
    ("display_name", "Display Name"),
    ("first_name", "First Name"),
    ("last_name", "Last Name"),
    ("email", "Email"),
]


@user_app.command(name="list", alias="ls")
async def list_(*, json: bool = False) -> None:
    """List workspace members."""
    try:
        client = get_client()
        workspace = get_workspace()
        members = await run_sdk(client.workspaces.get_members, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    data = [m.model_dump() for m in members]
    output(data, USER_COLUMNS, title="Workspace Members", as_json=json)
