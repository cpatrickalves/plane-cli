"""Authentication config loading with precedence: CLI flags > env vars > ~/.plane_api file."""

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


def _read_config_file() -> dict[str, str]:
    """Read key=value pairs from ~/.plane_api."""
    if not CONFIG_FILE.exists():
        return {}
    values: dict[str, str] = {}
    for line in CONFIG_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip().lower()] = value.strip().strip('"').strip("'")
    return values


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
    """Load config with precedence: explicit args > env vars > config file."""
    file_values = _read_config_file()

    resolved_base_url = base_url or os.environ.get("PLANE_BASE_URL") or file_values.get("base_url")
    resolved_api_key = api_key or os.environ.get("PLANE_API_KEY") or file_values.get("api_key")
    resolved_workspace = (
        workspace or os.environ.get("PLANE_WORKSPACE") or file_values.get("workspace")
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
