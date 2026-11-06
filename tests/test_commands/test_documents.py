"""Tests for document (page) commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from plane.models.pages import CreatePage

from planecli.commands.documents import DOC_FIELDS, _enrich_doc, create
from planecli.utils.body_html import body_to_html


def _page_model(**overrides) -> MagicMock:
    """A fake Page: only `.model_dump()` is used by the create command."""
    payload = {
        "id": "page-1",
        "name": "Test doc",
        "description_html": "<p></p>",
        "created_at": "2026-08-28T10:00:00Z",
        "updated_at": "2026-08-28T10:00:00Z",
    }
    payload.update(overrides)
    m = MagicMock()
    m.model_dump.return_value = payload
    return m


def test_enrich_doc_strips_html_to_text():
    data = _enrich_doc({"id": "p1", "name": "Doc", "description_html": "<p>hi<br/>there</p>"})
    assert data["content_text"] == "hi\nthere"


def test_enrich_doc_round_trips_converted_body():
    body = "line one\nline two\n\nuse `Vec<u8>` here"
    data = _enrich_doc({"id": "p1", "description_html": body_to_html(body)})
    assert data["content_text"] == body.replace("`", "")


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


def test_body_to_html_url_mid_code_span_is_not_linkified():
    assert body_to_html("`see https://x.io now`") == "<p><code>see https://x.io now</code></p>"
    assert body_to_html('`curl "https://x.io/a"`') == (
        "<p><code>curl &quot;https://x.io/a&quot;</code></p>"
    )


def test_body_to_html_fence_glued_to_text_stays_out_of_paragraph():
    assert body_to_html("Run:\n```\nls\n```\ndone") == (
        "<p>Run:</p><pre><code>ls</code></pre><p>done</p>"
    )


def test_body_to_html_adjacent_fences():
    assert body_to_html("```\na\n```\n```\nb\n```") == (
        "<pre><code>a</code></pre><pre><code>b</code></pre>"
    )


def test_body_to_html_fence_info_string_and_crlf():
    assert body_to_html("```c++\r\n#include <vector>\r\n```") == (
        "<pre><code>#include &lt;vector&gt;</code></pre>"
    )


def test_body_to_html_url_keeps_balanced_closing_paren():
    url = "https://en.wikipedia.org/wiki/Foo_(bar)"
    assert body_to_html(url) == f'<p><a href="{url}">{url}</a></p>'
    assert body_to_html("(see https://x.io/a)") == (
        '<p>(see <a href="https://x.io/a">https://x.io/a</a>)</p>'
    )


@pytest.mark.parametrize("body", ["", "  \n "])
def test_body_to_html_empty_input_gives_empty_paragraph(body):
    assert body_to_html(body) == "<p></p>"


@patch("planecli.commands.documents.output_single")
@patch("planecli.commands.documents.run_sdk", new_callable=AsyncMock)
@patch("planecli.commands.documents.resolve_project_async", new_callable=AsyncMock)
@patch("planecli.commands.documents.get_workspace", return_value="ws")
@patch("planecli.commands.documents.get_client")
async def test_create_passes_description_html_when_content_provided(
    mock_client, mock_ws, mock_resolve, mock_run_sdk, mock_output_single
):
    """CreatePage is constructed with wrapped --content, not assigned after the fact."""
    mock_resolve.return_value = {"id": "p1", "identifier": "ABC"}
    mock_run_sdk.return_value = _page_model(name="Test doc", description_html="<p>hello</p>")

    await create(title="Test doc", content="hello", project="ABC")

    args = mock_run_sdk.call_args[0]
    assert args[0] is mock_client.return_value.pages.create_project_page
    assert args[1:3] == ("ws", "p1")
    payload = args[3]
    assert isinstance(payload, CreatePage)
    assert payload.name == "Test doc"
    assert payload.description_html == "<p>hello</p>"
    data, fields = mock_output_single.call_args[0]
    assert fields is DOC_FIELDS
    assert data["name"] == "Test doc"


@patch("planecli.commands.documents.output_single")
@patch("planecli.commands.documents.run_sdk", new_callable=AsyncMock)
@patch("planecli.commands.documents.resolve_project_async", new_callable=AsyncMock)
@patch("planecli.commands.documents.get_workspace", return_value="ws")
@patch("planecli.commands.documents.get_client")
async def test_create_passes_empty_html_body_when_content_omitted(
    mock_client, mock_ws, mock_resolve, mock_run_sdk, mock_output_single
):
    """Omitting --content still supplies a valid empty HTML body at construction."""
    mock_resolve.return_value = {"id": "p1"}
    mock_run_sdk.return_value = _page_model()

    await create(title="Test doc", project="ABC")

    payload = mock_run_sdk.call_args[0][3]
    assert isinstance(payload, CreatePage)
    assert payload.name == "Test doc"
    assert payload.description_html == "<p></p>"


@patch("planecli.commands.documents.output_single")
@patch("planecli.commands.documents.run_sdk", new_callable=AsyncMock)
@patch("planecli.commands.documents.get_workspace", return_value="ws")
@patch("planecli.commands.documents.get_client")
async def test_create_without_project_creates_workspace_page(
    mock_client, mock_ws, mock_run_sdk, mock_output_single
):
    """Without --project the page is created at workspace level."""
    mock_run_sdk.return_value = _page_model()

    await create(title="Test doc", content="hello")

    args = mock_run_sdk.call_args[0]
    assert args[0] is mock_client.return_value.pages.create_workspace_page
    assert args[1] == "ws"
    assert args[2].description_html == "<p>hello</p>"


@patch("planecli.commands.documents.output_single")
@patch("planecli.commands.documents.run_sdk", new_callable=AsyncMock)
@patch("planecli.commands.documents.resolve_project_async", new_callable=AsyncMock)
@patch("planecli.commands.documents.get_workspace", return_value="ws")
@patch("planecli.commands.documents.get_client")
async def test_doc_create_converts_content_to_html(
    mock_client, mock_ws, mock_resolve, mock_run_sdk, mock_output
):
    mock_resolve.return_value = {"id": "proj-1"}
    mock_run_sdk.return_value = _page_model(description_html="")

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


def _http_error_response(status: int) -> MagicMock:
    import requests

    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status.side_effect = requests.HTTPError(f"{status} Error", response=resp)
    return resp


@patch("requests.delete")
@patch("planecli.api.client.get_config", return_value=_mock_config())
@patch("planecli.commands.documents.get_workspace", return_value="ws")
@patch("planecli.commands.documents.get_client")
async def test_doc_delete_workspace_page_url(mock_client, mock_ws, mock_config, mock_delete):
    from planecli.commands.documents import delete

    await delete("doc-uuid")

    url = mock_delete.call_args[0][0]
    assert url == "https://plane.example.com/api/v1/workspaces/ws/pages/doc-uuid/"


@patch("requests.delete")
@patch("planecli.api.client.get_config", return_value=_mock_config())
@patch("planecli.commands.documents.resolve_project_async", new_callable=AsyncMock)
@patch("planecli.commands.documents.get_workspace", return_value="ws")
@patch("planecli.commands.documents.get_client")
async def test_doc_delete_project_page_url(
    mock_client, mock_ws, mock_resolve, mock_config, mock_delete
):
    from planecli.commands.documents import delete

    mock_resolve.return_value = {"id": "proj-1"}

    await delete("doc-uuid", project="Frontend")

    url = mock_delete.call_args[0][0]
    assert url == "https://plane.example.com/api/v1/workspaces/ws/projects/proj-1/pages/doc-uuid/"


@pytest.mark.parametrize(("status", "exit_code"), [(400, 4), (401, 2), (404, 4), (405, 4)])
@patch("requests.delete")
@patch("planecli.api.client.get_config", return_value=_mock_config())
@patch("planecli.commands.documents.get_workspace", return_value="ws")
@patch("planecli.commands.documents.get_client")
async def test_doc_delete_http_error_maps_to_exit_code(
    mock_client, mock_ws, mock_config, mock_delete, status, exit_code
):
    """Some self-hosted servers answer 405 to page deletes: report it, no traceback."""
    from planecli.commands.documents import delete
    from planecli.exceptions import PlaneCLIError

    mock_delete.return_value = _http_error_response(status)

    with pytest.raises(PlaneCLIError, match="not deleted|Authentication") as exc_info:
        await delete("doc-uuid")

    assert exc_info.value.exit_code == exit_code
