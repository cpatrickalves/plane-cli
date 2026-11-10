"""Tests for lighten_hex with server-supplied colors."""

from __future__ import annotations

from planecli.utils.colors import lighten_hex


class TestLightenHex:
    def test_valid_hex_still_lightens(self):
        assert lighten_hex("#000000") == "#595959"
        assert lighten_hex("#fff") == "#ffffff"

    def test_malformed_api_color_passes_through(self):
        # A state color from the API that is not hex (e.g. "red") must not
        # crash work-item display with ValueError; it passes through for Rich.
        assert lighten_hex("red") == "red"
        assert lighten_hex("#zzzzzz") == "#zzzzzz"
