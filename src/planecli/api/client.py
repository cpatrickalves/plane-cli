"""PlaneClient wrapper with error handling and config integration."""

from __future__ import annotations

from plane.client import PlaneClient
from plane.errors import HttpError, PlaneError

from planecli.config import Config, load_config
from planecli.exceptions import APIError, AuthenticationError, PlaneCLIError

_client: PlaneClient | None = None
_config: Config | None = None


def get_config(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    workspace: str | None = None,
) -> Config:
    """Get or create the global config."""
    global _config
    if _config is None:
        _config = load_config(base_url=base_url, api_key=api_key, workspace=workspace)
    return _config


def get_client(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    workspace: str | None = None,
) -> PlaneClient:
    """Get or create the global PlaneClient singleton."""
    global _client
    if _client is None:
        config = get_config(base_url=base_url, api_key=api_key, workspace=workspace)
        _client = PlaneClient(base_url=config.base_url, api_key=config.api_key)
    return _client


def get_workspace() -> str:
    """Get the workspace slug from config."""
    config = get_config()
    return config.workspace


def handle_api_error(err: PlaneError) -> PlaneCLIError:
    """Convert a Plane SDK error to a PlaneCLI error."""
    if isinstance(err, HttpError):
        if err.status_code == 401:
            return AuthenticationError()
        if err.status_code == 429:
            return APIError(
                "Rate limited by Plane API after multiple retries. Try again later.",
                status_code=429,
            )
        return APIError(str(err), status_code=err.status_code)
    return APIError(str(err))
