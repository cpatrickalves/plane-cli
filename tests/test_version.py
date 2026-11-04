"""Tests for the commit shown by `planecli --version`."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

from planecli import __version__, full_version
from planecli.app import app

SHA = "18c7682b44c71ef183ddbb24d6b9b1c59b989551"


def _installed_with(direct_url: dict | None) -> MagicMock:
    dist = MagicMock()
    dist.read_text.return_value = json.dumps(direct_url) if direct_url else None
    return dist


@patch("importlib.metadata.distribution")
def test_regular_install_shows_only_the_version(mock_distribution):
    mock_distribution.return_value = _installed_with(None)

    assert full_version() == __version__


@patch("importlib.metadata.distribution")
def test_git_install_shows_the_installed_commit(mock_distribution):
    mock_distribution.return_value = _installed_with(
        {"url": "https://github.com/o/plane-cli", "vcs_info": {"vcs": "git", "commit_id": SHA}}
    )

    assert full_version() == f"{__version__}+18c7682"


@patch("subprocess.run")
@patch("importlib.metadata.distribution")
def test_editable_install_shows_the_checkout_commit(mock_distribution, mock_run):
    mock_distribution.return_value = _installed_with(
        {"url": "file:///home/me/plane-cli", "dir_info": {"editable": True}}
    )
    mock_run.return_value = MagicMock(stdout=f"{SHA}\n")

    assert full_version() == f"{__version__}+18c7682"
    assert mock_run.call_args[0][0][:3] == ["git", "-C", "/home/me/plane-cli"]


@patch("subprocess.run", side_effect=subprocess.CalledProcessError(128, "git"))
@patch("importlib.metadata.distribution")
def test_editable_install_outside_git_shows_only_the_version(mock_distribution, mock_run):
    mock_distribution.return_value = _installed_with(
        {"url": "file:///home/me/plane-cli", "dir_info": {"editable": True}}
    )

    assert full_version() == __version__


@patch("subprocess.run", side_effect=FileNotFoundError("git"))
@patch("importlib.metadata.distribution")
def test_editable_install_without_git_shows_only_the_version(mock_distribution, mock_run):
    mock_distribution.return_value = _installed_with(
        {"url": "file:///home/me/plane-cli", "dir_info": {"editable": True}}
    )

    assert full_version() == __version__


def test_app_resolves_the_version_lazily():
    assert app.version is full_version
