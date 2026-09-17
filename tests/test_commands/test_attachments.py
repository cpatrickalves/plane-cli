"""Tests for work item attachment commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from planecli.commands.attachments import _enrich_attachment, _guess_mime, embed_html


def test_embed_html_uses_asset_id_as_src():
    # The web editor stores the asset UUID in src and resolves it at render
    # time — a full URL here breaks image loading.
    assert embed_html("a1") == '<p><img src="a1" /></p>'


def test_guess_mime_known_extension():
    assert _guess_mime("shot.png") == "image/png"
    assert _guess_mime("notes.MD") == "text/markdown"


def test_guess_mime_unknown_extension_defaults_to_octet_stream():
    assert _guess_mime("data.unknownext") == "application/octet-stream"
    assert _guess_mime("noext") == "application/octet-stream"


def test_enrich_attachment_flattens_attributes():
    data = {
        "id": "a1",
        "attributes": {"name": "shot.png", "type": "image/png"},
        "size": 191318.0,
        "is_uploaded": True,
    }
    result = _enrich_attachment(data)
    assert result["name"] == "shot.png"
    assert result["type"] == "image/png"
    assert result["size"] == 191318.0


def test_enrich_attachment_tolerates_missing_attributes():
    result = _enrich_attachment({"id": "a1"})
    assert result["name"] == ""
    assert result["type"] == ""
    assert result["size"] is None


@patch(
    "planecli.commands.attachments._resolve_item",
    new_callable=AsyncMock,
)
async def test_attach_rejects_missing_file(mock_resolve):
    from planecli.exceptions import ValidationError

    mock_resolve.return_value = ({"id": "item-1"}, "proj-1")
    with pytest.raises(ValidationError):
        await _run_attach("/definitely/not/here.png")


def _upload_side_effects(verify_list):
    return [
        [],  # 0. dup-check: no existing attachments
        {  # 1. register -> presigned target
            "asset_id": "asset-1",
            "upload_data": {"url": "http://uploads.local", "fields": {"key": "k"}},
        },
        MagicMock(status_code=204),  # 2. binary upload
        None,  # 3. PATCH is_uploaded
        verify_list,  # 4. verify
    ]


@patch("planecli.commands.attachments.run_sdk", new_callable=AsyncMock)
@patch("planecli.commands.attachments.get_workspace", return_value="ws")
@patch("planecli.commands.attachments.get_client")
@patch(
    "planecli.commands.attachments.resolve_work_item_across_projects_async",
    new_callable=AsyncMock,
)
async def test_attach_uploads_then_marks_uploaded(mock_resolve, mock_client, _ws, mock_run):
    from planecli.commands.attachments import attach

    mock_resolve.return_value = ({"id": "item-1"}, "proj-1")
    mock_run.side_effect = _upload_side_effects(
        [{"id": "asset-1", "attributes": {"name": "x.png"}, "is_uploaded": True}]
    )

    with (
        patch("os.path.isfile", return_value=True),
        patch("os.path.getsize", return_value=10),
        patch("builtins.open", MagicMock()),
    ):
        await attach("ABC-1", "x.png", json=True)

    # binary push went to the presigned URL with form fields, not the API
    post_call = mock_run.call_args_list[2]
    assert post_call.args[1] == "http://uploads.local"
    assert post_call.kwargs["data"] == {"key": "k"}


@patch("planecli.commands.attachments.run_sdk", new_callable=AsyncMock)
@patch("planecli.commands.attachments.get_workspace", return_value="ws")
@patch("planecli.commands.attachments.get_client")
@patch(
    "planecli.commands.attachments.resolve_work_item_across_projects_async",
    new_callable=AsyncMock,
)
async def test_attach_raises_when_server_does_not_confirm(mock_resolve, _client, _ws, mock_run):
    from planecli.exceptions import APIError

    mock_resolve.return_value = ({"id": "item-1"}, "proj-1")
    mock_run.side_effect = _upload_side_effects(
        [{"id": "asset-1", "is_uploaded": False}]  # PATCH accepted but not applied
    )

    with (
        patch("os.path.isfile", return_value=True),
        patch("os.path.getsize", return_value=10),
        patch("builtins.open", MagicMock()),
        pytest.raises(APIError),
    ):
        from planecli.commands.attachments import attach

        await attach("ABC-1", "x.png")


@patch("planecli.commands.attachments._guess_mime", return_value="image/png")
@patch("planecli.commands.attachments.run_sdk", new_callable=AsyncMock)
async def test_upload_attachment_cancels_on_duplicate_name(mock_run, _mime):
    from planecli.commands.attachments import upload_attachment
    from planecli.exceptions import ValidationError

    mock_run.side_effect = [
        [{"id": "old-1", "attributes": {"name": "x.png"}, "is_uploaded": True}],
    ]

    with (
        patch("os.path.isfile", return_value=True),
        patch("os.path.getsize", return_value=10),
        pytest.raises(ValidationError, match="already attached"),
    ):
        # not a TTY in tests -> prompt refuses -> ValidationError
        await upload_attachment(MagicMock(), "ws", "p1", "i1", "x.png")


@patch("planecli.commands.attachments._guess_mime", return_value="image/png")
@patch("planecli.commands.attachments.run_sdk", new_callable=AsyncMock)
async def test_upload_attachment_force_skips_duplicate_check(mock_run, _mime):
    from planecli.commands.attachments import upload_attachment

    mock_run.side_effect = [
        [{"id": "old-1", "attributes": {"name": "x.png"}, "is_uploaded": True}],
        {"asset_id": "asset-1", "upload_data": {"url": "u", "fields": {}}},
        MagicMock(status_code=204),
        None,
        [{"id": "asset-1", "attributes": {"name": "x.png"}, "is_uploaded": True}],
    ]

    with (
        patch("os.path.isfile", return_value=True),
        patch("os.path.getsize", return_value=10),
        patch("builtins.open", MagicMock()),
    ):
        result = await upload_attachment(MagicMock(), "ws", "p1", "i1", "x.png", force=True)

    assert result["id"] == "asset-1"


async def _run_attach(path: str) -> None:
    from planecli.commands.attachments import attach

    await attach("ABC-1", path)


def _resp(status, json_data=None):
    m = MagicMock(status_code=status)
    m.json.return_value = json_data or {}
    return m


@patch("planecli.api.client.get_config")
@patch("planecli.commands.attachments.run_sdk", new_callable=AsyncMock)
async def test_upload_embed_image_prefers_v2_endpoint(mock_run, mock_cfg):
    from planecli.commands.attachments import upload_embed_image

    mock_cfg.return_value = MagicMock(base_url="http://plane.local", api_key="k")
    mock_run.side_effect = [
        _resp(200, {"asset_id": "a1", "asset_url": "/api/assets/v2/x/a1/",
                    "upload_data": {"url": "u", "fields": {}}}),
        _resp(204),  # binary upload
        _resp(204),  # mark uploaded
        _resp(200),  # v1 readback confirms
    ]

    with (
        patch("os.path.isfile", return_value=True),
        patch("os.path.getsize", return_value=10),
        patch("builtins.open", MagicMock()),
    ):
        asset_id = await upload_embed_image(None, "ws", "p1", "i1", "x.png")

    assert asset_id == "a1"
    # first call hits the app (v2) endpoint with the api key, not /api/v1/
    first = mock_run.call_args_list[0]
    assert "/api/assets/v2/workspaces/ws/projects/p1/" in first.args[1]
    assert first.args[2] == "k"


@patch("planecli.commands.attachments.upload_attachment", new_callable=AsyncMock)
@patch("planecli.api.client.get_config")
@patch("planecli.commands.attachments.run_sdk", new_callable=AsyncMock)
async def test_upload_embed_image_falls_back_to_v1_on_401(
    mock_run, mock_cfg, mock_upload
):
    from planecli.commands.attachments import upload_embed_image

    mock_cfg.return_value = MagicMock(base_url="http://plane.local", api_key="k")
    mock_run.side_effect = [_resp(401)]
    mock_upload.return_value = {"id": "a9"}

    with (
        patch("os.path.isfile", return_value=True),
        patch("os.path.getsize", return_value=10),
    ):
        asset_id = await upload_embed_image(None, "ws", "p1", "i1", "x.png")

    assert asset_id == "a9"
    mock_upload.assert_awaited_once()


@patch("planecli.api.client.get_config")
@patch("planecli.commands.attachments.run_sdk", new_callable=AsyncMock)
async def test_upload_embed_image_raises_on_v2_server_error(mock_run, mock_cfg):
    from planecli.commands.attachments import upload_embed_image
    from planecli.exceptions import APIError

    mock_cfg.return_value = MagicMock(base_url="http://plane.local", api_key="k")
    mock_run.side_effect = [_resp(500)]

    with (
        patch("os.path.isfile", return_value=True),
        patch("os.path.getsize", return_value=10),
        pytest.raises(APIError),
    ):
        await upload_embed_image(None, "ws", "p1", "i1", "x.png")


@patch("planecli.api.client.get_config")
@patch("planecli.commands.attachments.run_sdk", new_callable=AsyncMock)
async def test_upload_embed_image_raises_when_not_confirmed(mock_run, mock_cfg):
    from planecli.commands.attachments import upload_embed_image
    from planecli.exceptions import APIError

    mock_cfg.return_value = MagicMock(base_url="http://plane.local", api_key="k")
    mock_run.side_effect = [
        _resp(200, {"asset_id": "a1", "asset_url": "/u",
                    "upload_data": {"url": "u", "fields": {}}}),
        _resp(204),
        _resp(204),
        _resp(404),  # readback: asset not visible -> write did not land
    ]

    with (
        patch("os.path.isfile", return_value=True),
        patch("os.path.getsize", return_value=10),
        patch("builtins.open", MagicMock()),
        pytest.raises(APIError),
    ):
        await upload_embed_image(None, "ws", "p1", "i1", "x.png")
