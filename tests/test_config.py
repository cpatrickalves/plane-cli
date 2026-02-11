"""Tests for config module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from planecli.config import load_config, save_config, _read_config_file
from planecli.exceptions import AuthenticationError


class TestReadConfigFile:
    def test_returns_empty_when_no_file(self, tmp_path):
        with patch("planecli.config.CONFIG_FILE", tmp_path / "nonexistent"):
            result = _read_config_file()
        assert result == {}

    def test_parses_key_value_pairs(self, tmp_path):
        config_file = tmp_path / ".plane_api"
        config_file.write_text("base_url=https://api.plane.so\napi_key=secret\nworkspace=my-ws\n")
        with patch("planecli.config.CONFIG_FILE", config_file):
            result = _read_config_file()
        assert result == {
            "base_url": "https://api.plane.so",
            "api_key": "secret",
            "workspace": "my-ws",
        }

    def test_ignores_comments_and_empty_lines(self, tmp_path):
        config_file = tmp_path / ".plane_api"
        config_file.write_text("# comment\n\nbase_url=https://example.com\n")
        with patch("planecli.config.CONFIG_FILE", config_file):
            result = _read_config_file()
        assert result == {"base_url": "https://example.com"}

    def test_strips_quotes(self, tmp_path):
        config_file = tmp_path / ".plane_api"
        config_file.write_text('api_key="my-secret"\n')
        with patch("planecli.config.CONFIG_FILE", config_file):
            result = _read_config_file()
        assert result == {"api_key": "my-secret"}


class TestSaveConfig:
    def test_saves_and_sets_permissions(self, tmp_path):
        config_file = tmp_path / ".plane_api"
        with patch("planecli.config.CONFIG_FILE", config_file):
            save_config("https://api.plane.so", "secret", "my-ws")

        assert config_file.exists()
        content = config_file.read_text()
        assert "base_url=https://api.plane.so" in content
        assert "api_key=secret" in content
        assert "workspace=my-ws" in content

        # Check permissions (0o600)
        mode = config_file.stat().st_mode & 0o777
        assert mode == 0o600


class TestLoadConfig:
    def test_explicit_args_take_precedence(self, tmp_path):
        config_file = tmp_path / ".plane_api"
        config_file.write_text("base_url=file\napi_key=file\nworkspace=file\n")
        with (
            patch("planecli.config.CONFIG_FILE", config_file),
            patch.dict("os.environ", {}, clear=True),
        ):
            config = load_config(
                base_url="explicit",
                api_key="explicit",
                workspace="explicit",
            )
        assert config.base_url == "explicit"
        assert config.api_key == "explicit"
        assert config.workspace == "explicit"

    def test_env_vars_override_file(self, tmp_path):
        config_file = tmp_path / ".plane_api"
        config_file.write_text("base_url=file\napi_key=file\nworkspace=file\n")
        env = {
            "PLANE_BASE_URL": "env-url",
            "PLANE_API_KEY": "env-key",
            "PLANE_WORKSPACE": "env-ws",
        }
        with (
            patch("planecli.config.CONFIG_FILE", config_file),
            patch.dict("os.environ", env, clear=True),
        ):
            config = load_config()
        assert config.base_url == "env-url"
        assert config.api_key == "env-key"
        assert config.workspace == "env-ws"

    def test_raises_when_missing_base_url(self, tmp_path):
        with (
            patch("planecli.config.CONFIG_FILE", tmp_path / "nonexistent"),
            patch.dict("os.environ", {}, clear=True),
        ):
            with pytest.raises(AuthenticationError, match="Missing base URL"):
                load_config()

    def test_raises_when_missing_api_key(self, tmp_path):
        with (
            patch("planecli.config.CONFIG_FILE", tmp_path / "nonexistent"),
            patch.dict("os.environ", {"PLANE_BASE_URL": "url"}, clear=True),
        ):
            with pytest.raises(AuthenticationError, match="Missing API key"):
                load_config()

    def test_strips_trailing_slash(self, tmp_path):
        with (
            patch("planecli.config.CONFIG_FILE", tmp_path / "nonexistent"),
            patch.dict(
                "os.environ",
                {
                    "PLANE_BASE_URL": "https://api.plane.so/",
                    "PLANE_API_KEY": "key",
                    "PLANE_WORKSPACE": "ws",
                },
                clear=True,
            ),
        ):
            config = load_config()
        assert config.base_url == "https://api.plane.so"
