"""Authentication config loading with precedence: CLI flags > env vars > ~/.plane_api file.

~/.plane_api holds key=value lines for the default workspace. Optional
``[name]`` sections add more workspaces; each may set ``workspace`` (the slug,
default: the section name), ``api_key`` and ``base_url`` (default: the top-level
values). ``--workspace/-w NAME`` or ``PLANE_WORKSPACE=NAME`` selects a section by
name, or any workspace by slug.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from planecli.exceptions import AuthenticationError

CONFIG_FILE = Path.home() / ".plane_api"

_FIELD_MAP = {
    "base_url": "PLANE_BASE_URL",
    "api_key": "PLANE_API_KEY",
    "workspace": "PLANE_WORKSPACE",
}


@dataclass
class Config:
    base_url: str
    api_key: str
    workspace: str


def _parse_config_file() -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """Parse ~/.plane_api into top-level values and ``[name]`` workspace sections."""
    top: dict[str, str] = {}
    sections: dict[str, dict[str, str]] = {}
    if not CONFIG_FILE.exists():
        return top, sections
    current = top
    for line in CONFIG_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            current = sections.setdefault(name, {})
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        current[key.strip().lower()] = value.strip().strip('"').strip("'")
    return top, sections


def _read_config_file() -> dict[str, str]:
    """Read the top-level key=value pairs from ~/.plane_api."""
    return _parse_config_file()[0]


@dataclass
class WorkspaceEntry:
    """A workspace known from ~/.plane_api (no secrets)."""

    name: str
    slug: str
    base_url: str
    default: bool
    own_api_key: bool


def list_workspaces() -> list[WorkspaceEntry]:
    """The default workspace and every ``[name]`` section, in file order."""
    top, sections = _parse_config_file()
    out: list[WorkspaceEntry] = []
    if top.get("workspace"):
        out.append(
            WorkspaceEntry(
                name=top["workspace"],
                slug=top["workspace"],
                base_url=top.get("base_url", ""),
                default=True,
                own_api_key=False,
            )
        )
    for name, values in sections.items():
        out.append(
            WorkspaceEntry(
                name=name,
                slug=values.get("workspace") or name,
                base_url=values.get("base_url") or top.get("base_url", ""),
                default=False,
                own_api_key=bool(values.get("api_key")),
            )
        )
    return out


# Set by the global --workspace/-w flag (see planecli.app.main).
_cli_workspace: str | None = None


def set_cli_workspace(name: str | None) -> None:
    """Record the workspace chosen with --workspace/-w for this process."""
    global _cli_workspace
    _cli_workspace = name


def save_config(base_url: str, api_key: str, workspace: str) -> None:
    """Save config to ~/.plane_api with restricted permissions."""
    content = f"base_url={base_url}\napi_key={api_key}\nworkspace={workspace}\n"
    CONFIG_FILE.write_text(content)
    CONFIG_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600


def load_config(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    workspace: str | None = None,
) -> Config:
    """Load config with precedence: explicit args > env vars > config file.

    The workspace is chosen first (argument, then --workspace/-w, then
    PLANE_WORKSPACE, then the file's default). When it names a ``[section]``,
    that section's values sit between the environment and the top-level file
    values: explicit args > env vars > section > top level.
    """
    file_values, sections = _parse_config_file()

    chosen = workspace or _cli_workspace or os.environ.get("PLANE_WORKSPACE")
    profile: dict[str, str] = {}
    resolved_workspace = chosen or file_values.get("workspace")
    if resolved_workspace in sections:
        profile = sections[resolved_workspace]
        resolved_workspace = profile.get("workspace") or resolved_workspace

    resolved_base_url = (
        base_url
        or os.environ.get("PLANE_BASE_URL")
        or profile.get("base_url")
        or file_values.get("base_url")
    )
    resolved_api_key = (
        api_key
        or os.environ.get("PLANE_API_KEY")
        or profile.get("api_key")
        or file_values.get("api_key")
    )

    if not resolved_base_url:
        raise AuthenticationError(
            "Missing base URL. Set PLANE_BASE_URL or run 'planecli configure'."
        )
    if not resolved_api_key:
        raise AuthenticationError("Missing API key. Set PLANE_API_KEY or run 'planecli configure'.")
    if not resolved_workspace:
        raise AuthenticationError(
            "Missing workspace slug. Set PLANE_WORKSPACE or run 'planecli configure'."
        )

    return Config(
        base_url=resolved_base_url.rstrip("/"),
        api_key=resolved_api_key,
        workspace=resolved_workspace,
    )
