"""PlaneCLI - CLI for Plane.so project management."""

from importlib.metadata import version

__version__ = version("planecli")


def full_version() -> str:
    """Return the version, plus the commit when installed from git or an editable checkout."""
    import json
    import subprocess
    from importlib.metadata import distribution
    from urllib.parse import urlparse
    from urllib.request import url2pathname

    direct_url = distribution("planecli").read_text("direct_url.json")
    if not direct_url:
        return __version__

    info = json.loads(direct_url)
    commit = info.get("vcs_info", {}).get("commit_id")
    if not commit and info.get("dir_info", {}).get("editable"):
        checkout = url2pathname(urlparse(info["url"]).path)
        try:
            result = subprocess.run(
                ["git", "-C", checkout, "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return __version__
        commit = result.stdout.strip()

    return f"{__version__}+{commit[:7]}" if commit else __version__
