"""Tests for document (page) commands."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from planecli.commands.documents import _enrich_doc
from planecli.utils.body_html import body_to_html


def test_enrich_doc_strips_html_to_text():
    data = _enrich_doc({"id": "p1", "name": "Doc", "description_html": "<p>hi<br/>there</p>"})
    assert data["content_text"] == "hithere"


def test_enrich_doc_empty_description():
    data = _enrich_doc({"id": "p1", "name": "Doc", "description_html": None})
    assert data["content_text"] == ""


def test_body_to_html_blank_lines_split_paragraphs():
    assert body_to_html("one\n\n\ntwo") == "<p>one</p><p>two</p>"


def test_body_to_html_single_newline_becomes_br():
    assert body_to_html("one\ntwo") == "<p>one<br/>two</p>"


def test_body_to_html_linkifies_bare_urls():
    html = body_to_html("see https://example.com/a, ok")
    assert html == '<p>see <a href="https://example.com/a">https://example.com/a</a>, ok</p>'


def test_body_to_html_linkify_keeps_trailing_punctuation_outside_anchor():
    html = body_to_html("visit https://plane.so.")
    assert html == '<p>visit <a href="https://plane.so">https://plane.so</a>.</p>'


def test_body_to_html_backticks_become_code():
    assert body_to_html("run `make test` now") == "<p>run <code>make test</code> now</p>"


def test_body_to_html_inline_code_is_escaped_and_not_linkified():
    html = body_to_html("use `https://x.io <b>` here")
    assert html == "<p>use <code>https://x.io &lt;b&gt;</code> here</p>"


def test_body_to_html_fenced_block_becomes_pre_code():
    html = body_to_html("before\n\n```py\nprint('<x>')\n```\n\nafter")
    assert html == "<p>before</p><pre><code>print(&#x27;&lt;x&gt;&#x27;)</code></pre><p>after</p>"


@patch("planecli.commands.documents.output_single")
@patch("planecli.commands.documents.run_sdk", new_callable=AsyncMock)
@patch("planecli.commands.documents.resolve_project_async", new_callable=AsyncMock)
@patch("planecli.commands.documents.get_workspace", return_value="ws")
@patch("planecli.commands.documents.get_client")
async def test_doc_create_without_content_sends_empty_paragraph(
    mock_client, mock_ws, mock_resolve, mock_run_sdk, mock_output
):
    """description_html is a required CreatePage field; omitting it crashed
    construction even when --content was not given."""
    from planecli.commands.documents import create

    mock_resolve.return_value = {"id": "proj-1"}
    mock_run_sdk.return_value = MagicMock(
        model_dump=lambda: {"id": "p1", "name": "Doc", "description_html": "<p></p>"}
    )

    await create(title="Doc", project="Frontend")

    page_data = mock_run_sdk.call_args[0][3]
    assert page_data.description_html == "<p></p>"
    assert page_data.name == "Doc"


@patch("planecli.commands.documents.output_single")
@patch("planecli.commands.documents.run_sdk", new_callable=AsyncMock)
@patch("planecli.commands.documents.resolve_project_async", new_callable=AsyncMock)
@patch("planecli.commands.documents.get_workspace", return_value="ws")
@patch("planecli.commands.documents.get_client")
async def test_doc_create_converts_content_to_html(
    mock_client, mock_ws, mock_resolve, mock_run_sdk, mock_output
):
    from planecli.commands.documents import create

    mock_resolve.return_value = {"id": "proj-1"}
    mock_run_sdk.return_value = MagicMock(
        model_dump=lambda: {"id": "p1", "name": "Doc", "description_html": ""}
    )

    await create(
        title="Doc",
        content="line one\nline two\n\nsee https://plane.so and `make check`",
        project="Frontend",
    )

    page_data = mock_run_sdk.call_args[0][3]
    assert page_data.description_html == (
        "<p>line one<br/>line two</p>"
        '<p>see <a href="https://plane.so">https://plane.so</a>'
        " and <code>make check</code></p>"
    )


def _mock_config():
    config = MagicMock()
    config.base_url = "https://plane.example.com"
    config.api_key = "key"
    return config


@patch("planecli.commands.documents.output_single")
@patch("requests.patch")
@patch("planecli.api.client.get_config", return_value=_mock_config())
@patch("planecli.commands.documents.resolve_project_async", new_callable=AsyncMock)
@patch("planecli.commands.documents.get_workspace", return_value="ws")
@patch("planecli.commands.documents.get_client")
async def test_doc_update_converts_content(
    mock_client, mock_ws, mock_resolve, mock_config, mock_patch, mock_output
):
    from planecli.commands.documents import update

    mock_resolve.return_value = {"id": "proj-1"}
    resp = MagicMock()
    resp.json.return_value = {"id": "p1", "name": "Doc", "description_html": ""}
    mock_patch.return_value = resp

    await update("doc-uuid", title="Doc", content="a\nb", project="Frontend")

    url = mock_patch.call_args[0][0]
    assert url == ("https://plane.example.com/api/v1/workspaces/ws/projects/proj-1/pages/doc-uuid/")
    payload = mock_patch.call_args.kwargs["json"]
    assert payload == {"name": "Doc", "description_html": "<p>a<br/>b</p>"}


@patch("planecli.commands.documents.output_single")
@patch("requests.patch")
@patch("planecli.api.client.get_config", return_value=_mock_config())
@patch("planecli.commands.documents.get_workspace", return_value="ws")
@patch("planecli.commands.documents.get_client")
async def test_doc_update_workspace_page_url(
    mock_client, mock_ws, mock_config, mock_patch, mock_output
):
    from planecli.commands.documents import update

    resp = MagicMock()
    resp.json.return_value = {"id": "p1", "name": "Doc", "description_html": ""}
    mock_patch.return_value = resp

    await update("doc-uuid", content="x")

    url = mock_patch.call_args[0][0]
    assert url == "https://plane.example.com/api/v1/workspaces/ws/pages/doc-uuid/"


@patch("requests.delete")
@patch("requests.patch")
@patch("planecli.api.client.get_config", return_value=_mock_config())
@patch("planecli.commands.documents.get_workspace", return_value="ws")
@patch("planecli.commands.documents.get_client")
async def test_doc_delete_archives_before_deleting(
    mock_client, mock_ws, mock_config, mock_patch, mock_delete
):
    """The API refuses to delete un-archived pages and silently ignores
    unknown fields on the archive request, so delete must PATCH archived_at,
    verify it came back set, and only then DELETE."""
    from planecli.commands.documents import delete

    today = date.today().isoformat()
    patch_resp = MagicMock()
    patch_resp.json.return_value = {"id": "p1", "archived_at": today}
    mock_patch.return_value = patch_resp
    mock_delete.return_value = MagicMock()

    await delete("doc-uuid")

    url = mock_patch.call_args[0][0]
    assert url == "https://plane.example.com/api/v1/workspaces/ws/pages/doc-uuid/"
    assert mock_patch.call_args.kwargs["json"] == {"archived_at": today}
    # archive happened before delete, on the same URL
    assert mock_delete.called
    assert mock_delete.call_args[0][0] == url


@patch("requests.delete")
@patch("requests.patch")
@patch("planecli.api.client.get_config", return_value=_mock_config())
@patch("planecli.commands.documents.get_workspace", return_value="ws")
@patch("planecli.commands.documents.get_client")
async def test_doc_delete_refuses_when_archive_not_applied(
    mock_client, mock_ws, mock_config, mock_patch, mock_delete
):
    """A 200 on the archive PATCH is not proof of archiving (unknown fields
    are silently ignored) — if archived_at is missing from the response the
    document must NOT be deleted."""
    from planecli.commands.documents import delete
    from planecli.exceptions import APIError

    patch_resp = MagicMock()
    patch_resp.json.return_value = {"id": "p1", "archived_at": None}
    mock_patch.return_value = patch_resp

    with pytest.raises(APIError):
        await delete("doc-uuid")

    mock_delete.assert_not_called()
