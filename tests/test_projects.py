"""Tests for the project commands module."""

from __future__ import annotations

from planecli.commands.projects import _default_identifier


class TestDefaultIdentifier:
    def test_derives_from_name(self):
        assert _default_identifier("Frontend App") == "FRONT"

    def test_strips_punctuation(self):
        assert _default_identifier("My Backend API!") == "MYBAC"

    def test_keeps_short_name(self):
        assert _default_identifier("FE") == "FE"

    def test_uppercases(self):
        assert _default_identifier("backend") == "BACKE"
