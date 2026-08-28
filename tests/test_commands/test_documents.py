"""Tests for document / page commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from plane.models.pages import CreatePage

from planecli.commands.documents import DOC_FIELDS, create


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
