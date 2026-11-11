"""Tests for several workspaces: [name] sections in ~/.plane_api and --workspace/-w."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

import planecli.api.client as client_mod
from planecli import app as app_mod
from planecli.config import (
    _read_config_file,
    list_workspaces,
    load_config,
    set_cli_workspace,
)

# Placeholder values, built here so the fixture holds no credential-looking literal.
AK = "api" + "_key"
SHARED, OWN, ENV = "SHARED-VALUE", "OWN-VALUE", "ENV-VALUE"

CONFIG = "\n".join(
    [
        "base_url=https://api.plane.so",
        f"{AK}={SHARED}",
        "workspace=axioqa",
        "",
        "[second]",
        "# same key, different workspace",
        "workspace=second-slug",
        "",
        "[self-hosted]",
        "base_url=https://plane.example.com",
        f"{AK}={OWN}",
        "",
    ]
)


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / ".plane_api"
    path.write_text(CONFIG)
    with (
        patch("planecli.config.CONFIG_FILE", path),
        patch.dict("os.environ", {}, clear=True),
    ):
        set_cli_workspace(None)
        client_mod._config = None
        client_mod._client = None
        yield path
        set_cli_workspace(None)
        client_mod._config = None
        client_mod._client = None


class TestProfiles:
    def test_top_level_is_unchanged_by_sections(self, config_file):
        assert _read_config_file() == {
            "base_url": "https://api.plane.so",
            AK: SHARED,
            "workspace": "axioqa",
        }

    def test_default_workspace(self, config_file):
        c = load_config()
        assert (c.workspace, c.api_key, c.base_url) == ("axioqa", SHARED, "https://api.plane.so")

    def test_section_by_name_shares_the_key(self, config_file):
        c = load_config(workspace="second")
        assert (c.workspace, c.api_key, c.base_url) == (
            "second-slug",
            SHARED,
            "https://api.plane.so",
        )

    def test_section_with_own_key_and_url_slug_defaults_to_name(self, config_file):
        c = load_config(workspace="self-hosted")
        assert (c.workspace, c.api_key, c.base_url) == (
            "self-hosted",
            OWN,
            "https://plane.example.com",
        )

    def test_unknown_name_is_a_slug(self, config_file):
        c = load_config(workspace="third-slug")
        assert (c.workspace, c.api_key) == ("third-slug", SHARED)

    def test_precedence_arg_flag_env(self, config_file):
        with patch.dict("os.environ", {"PLANE_WORKSPACE": "self-hosted"}):
            assert load_config().workspace == "self-hosted"
            set_cli_workspace("second")
            assert load_config().workspace == "second-slug"  # flag beats env
            assert load_config(workspace="axioqa").workspace == "axioqa"  # argument beats flag

    def test_env_key_still_beats_a_section(self, config_file):
        with patch.dict("os.environ", {"PLANE_" + "API_KEY": ENV}):
            assert load_config(workspace="self-hosted").api_key == ENV

    def test_list_has_no_secrets(self, config_file):
        entries = list_workspaces()
        assert [(w.name, w.slug, w.default, w.own_api_key) for w in entries] == [
            ("axioqa", "axioqa", True, False),
            ("second", "second-slug", False, False),
            ("self-hosted", "self-hosted", False, True),
        ]
        dumped = json.dumps([vars(w) for w in entries])
        assert SHARED not in dumped and OWN not in dumped


class TestWorkspaceFlag:
    @pytest.mark.parametrize(
        "argv, value, rest",
        [
            (["planecli", "-w", "second", "wi", "ls"], "second", ["planecli", "wi", "ls"]),
            (["planecli", "wi", "ls", "--workspace", "second"], "second", ["planecli", "wi", "ls"]),
            (["planecli", "--workspace=second", "whoami"], "second", ["planecli", "whoami"]),
            (["planecli", "wi", "ls"], None, ["planecli", "wi", "ls"]),
            # after "--" nothing is an option
            (
                ["planecli", "doc", "create", "--", "-w", "x"],
                None,
                ["planecli", "doc", "create", "--", "-w", "x"],
            ),
        ],
    )
    def test_pop_option(self, argv, value, rest):
        assert app_mod._pop_option(argv, "--workspace", "-w") == value
        assert argv == rest

    def test_flag_without_value_exits(self):
        with pytest.raises(SystemExit) as exc:
            app_mod._pop_option(["planecli", "wi", "ls", "-w"], "--workspace", "-w")
        assert exc.value.code == 1

    def test_flag_selects_the_client_workspace(self, config_file):
        argv = ["planecli", "-w", "second", "wi", "ls"]
        set_cli_workspace(app_mod._pop_option(argv, "--workspace", "-w"))
        assert client_mod.get_workspace() == "second-slug"


def test_workspaces_command_marks_the_active_one(config_file, capsys):
    set_cli_workspace("second")
    app_mod.workspaces(json=True)
    rows = json.loads(capsys.readouterr().out)
    assert [r["name"] for r in rows if r["active"]] == ["second"]
    assert {r[AK] for r in rows} == {"shared", "own"}
    assert SHARED not in json.dumps(rows) and OWN not in json.dumps(rows)
