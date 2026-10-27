"""PlaneClient wrapper with error handling and config integration."""

from __future__ import annotations

import types
import warnings

import requests
from plane.client import PlaneClient
from plane.errors import HttpError, PlaneError

from planecli.config import Config, load_config
from planecli.exceptions import APIError, AuthenticationError, PlaneCLIError

_client: PlaneClient | None = None
_config: Config | None = None
_verify_ssl: bool = True
_warnings_suppressed: bool = False


def _suppress_insecure_warning() -> None:
    """Silence urllib3's InsecureRequestWarning once verification is opted out.

    When the user explicitly disables SSL verification (via --no-verify-ssl or
    PLANE_VERIFY_SSL=false), urllib3 still warns on every unverified request.
    That's expected noise for an intentional opt-out, so we filter it process-wide.
    """
    global _warnings_suppressed
    if _warnings_suppressed:
        return
    from urllib3.exceptions import InsecureRequestWarning

    warnings.filterwarnings("ignore", category=InsecureRequestWarning)
    _warnings_suppressed = True


def set_verify_ssl(value: bool) -> None:
    """Set whether SSL certificate verification is enabled."""
    global _verify_ssl, _client
    _verify_ssl = value
    if not value:
        _suppress_insecure_warning()
    _client = None  # invalidate cached client so new one picks up the setting


def verify_param() -> bool | str:
    """Return the `verify=` value to pass to direct requests calls.

    Ad-hoc requests calls (e.g. documents.py) honor the same global setting,
    so they verify by default and skip verification when the user opted out.
    """
    return _verify_ssl


def _disable_ssl(client: PlaneClient) -> None:
    """Disable certificate verification on every requests.Session reachable
    from ``client``.

    The plane SDK gives each resource its own Session, *including* nested
    sub-resources (``work_items.comments``, ``work_items.links``,
    ``customers.properties``, the ``v2`` transport, ...). A flat walk over a
    fixed list of top-level names silently misses those, so instead we recurse
    through the client's attributes and flip ``verify`` on every Session found.
    """
    _suppress_insecure_warning()
    _walk_sessions(client, set())


def _walk_sessions(obj: object, seen: set[int]) -> None:
    """Recursively set verify=False on every Session under ``obj``.

    ``seen`` guards against reference cycles in the SDK object graph.
    """
    if obj is None:
        return

    obj_id = id(obj)
    if obj_id in seen:
        return
    seen.add(obj_id)

    # A requests.Session (or subclass): this is the leaf we care about.
    if isinstance(obj, requests.Session):
        obj.verify = False
        return

    # Only descend into plain objects we can introspect. Skip types, modules,
    # functions, and primitives -- they can't own a Session.
    if isinstance(obj, type | types.ModuleType | str | bytes | int | float | bool):
        return

    try:
        attrs = vars(obj)
    except TypeError:  # objects without a __dict__ (e.g. some builtins)
        return

    for value in attrs.values():
        if isinstance(value, (str, bytes, int, float, bool, type)):
            continue
        _walk_sessions(value, seen)


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
        if not _verify_ssl:
            _disable_ssl(_client)
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
