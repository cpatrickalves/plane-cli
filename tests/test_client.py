"""Tests for the SSL verification helpers in api/client.py."""

from __future__ import annotations

import warnings

import pytest
from urllib3.exceptions import InsecureRequestWarning

import planecli.api.client as client_mod
from planecli.api.client import _disable_ssl, set_verify_ssl, verify_param


def _collect_sessions(obj, seen, out):
    """Recursively collect every requests.Session under obj."""
    import requests as _requests

    if obj is None:
        return
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, _requests.Session):
        out.append(obj)
        return
    if isinstance(obj, type | str | bytes | int | float | bool):
        return
    try:
        values = list(vars(obj).values())
    except TypeError:
        return
    for v in values:
        _collect_sessions(v, seen, out)


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
    def test_sets_top_level_session_verify_false(self):
        import requests

        class FakeResource:
            def __init__(self):
                self.session = requests.Session()

        class FakeClient:
            def __init__(self):
                self.work_items = FakeResource()
                self.projects = FakeResource()

        fc = FakeClient()
        _disable_ssl(fc)
        assert fc.work_items.session.verify is False
        assert fc.projects.session.verify is False

    def test_sets_nested_subresource_session_verify_false(self):
        """Regression: work_items.comments and other nested resources own
        their own Session and were skipped by the old flat name list."""
        import requests

        class Nested:
            def __init__(self):
                self.session = requests.Session()

        class FakeWorkItems:
            def __init__(self):
                self.session = requests.Session()
                self.comments = Nested()
                self.links = Nested()

        class FakeV2Transport:
            def __init__(self):
                self.session = requests.Session()

        class FakeV2Namespace:
            def __init__(self):
                self.transport = FakeV2Transport()

        class FakeClient:
            def __init__(self):
                self.work_items = FakeWorkItems()
                self.v2 = FakeV2Namespace()

        fc = FakeClient()
        _disable_ssl(fc)
        assert fc.work_items.session.verify is False
        assert fc.work_items.comments.session.verify is False
        assert fc.work_items.links.session.verify is False
        assert fc.v2.transport.session.verify is False

    def test_handles_reference_cycles(self):
        import requests

        class Node:
            def __init__(self):
                self.session = requests.Session()
                self.child = None
                self.back = None

        a, b = Node(), Node()
        a.child = b
        b.back = a  # cycle

        _disable_ssl(a)
        assert a.session.verify is False
        assert b.session.verify is False

    def test_suppresses_warning(self):
        _disable_ssl(object())
        assert client_mod._warnings_suppressed is True

    def test_real_plane_client_disables_every_session(self):
        """Against the real SDK: every Session, nested or not, gets verify=False."""
        from plane.client import PlaneClient

        client = PlaneClient(base_url="https://plane.example.com", api_key="k")
        _disable_ssl(client)

        found = []
        _collect_sessions(client, set(), found)
        assert found, "expected to find at least one Session on a real client"
        assert all(s.verify is False for s in found), (
            "some Session still verifies: "
            + str([s for s in found if s.verify is not False])
        )
        # The specific one that broke `work-item show`:
        assert client.work_items.comments.session.verify is False
