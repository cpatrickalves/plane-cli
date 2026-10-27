"""Tests for the SSL verification helpers in api/client.py."""

from __future__ import annotations

import warnings

import pytest
from urllib3.exceptions import InsecureRequestWarning

import planecli.api.client as client_mod
from planecli.api.client import _disable_ssl, set_verify_ssl, verify_param


@pytest.fixture(autouse=True)
def _reset_ssl_state():
    """Restore the module globals after each test."""
    yield
    set_verify_ssl(True)
    client_mod._warnings_suppressed = False


class TestSetVerifySsl:
    def test_enabling_does_not_suppress_warnings(self):
        set_verify_ssl(True)
        assert client_mod._warnings_suppressed is False

    def test_disabling_suppresses_insecure_warning(self):
        set_verify_ssl(False)
        assert client_mod._warnings_suppressed is True

    def test_registers_ignore_filter_for_insecure_warning(self):
        set_verify_ssl(False)
        # An "ignore" filter for InsecureRequestWarning must be registered.
        matched = [
            f
            for f in warnings.filters
            if f[0] == "ignore" and f[2] is InsecureRequestWarning
        ]
        assert matched, "expected an ignore filter for InsecureRequestWarning"

    def test_disable_invalidates_cached_client(self):
        client_mod._client = object()  # simulate a cached singleton
        set_verify_ssl(False)
        assert client_mod._client is None


class TestVerifyParam:
    def test_defaults_to_true(self):
        assert verify_param() is True

    def test_returns_false_when_disabled(self):
        set_verify_ssl(False)
        assert verify_param() is False


class TestDisableSsl:
    def test_sets_session_verify_false(self, monkeypatch):
        class FakeApi:
            def __init__(self):
                class S:
                    verify = True
                self.session = S()

        class FakeClient:
            def __init__(self):
                self.work_items = FakeApi()
                self.projects = FakeApi()

        fc = FakeClient()
        _disable_ssl(fc)
        assert fc.work_items.session.verify is False
        assert fc.projects.session.verify is False

    def test_suppresses_warning(self):
        _disable_ssl(object())
        assert client_mod._warnings_suppressed is True
