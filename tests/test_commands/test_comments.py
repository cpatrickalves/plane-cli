"""Tests for work item comment commands."""

from __future__ import annotations

from planecli.commands.comments import _enrich_comment


def test_enrich_comment_resolves_actor_name_from_members_map():
    members_map = {"user-1": "Alice"}
    result = _enrich_comment(
        {"actor": "user-1", "comment_html": "<p>hello</p>"}, members_map
    )
    assert result["actor_name"] == "Alice"
    assert result["body_text"] == "hello"


def test_enrich_comment_falls_back_to_uuid_without_map():
    result = _enrich_comment({"actor": "user-1", "comment_html": "<p>hi</p>"})
    assert result["actor_name"] == "user-1"


def test_enrich_comment_falls_back_to_uuid_when_member_missing():
    result = _enrich_comment(
        {"actor": "user-x", "comment_html": ""}, {"user-1": "Alice"}
    )
    assert result["actor_name"] == "user-x"
    assert result["body_text"] == ""
