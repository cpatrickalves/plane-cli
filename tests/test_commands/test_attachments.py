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


# ---------------------------------------------------------------------------
# attachment get (download)
# ---------------------------------------------------------------------------


def _att(att_id: str, name: str) -> dict:
    return {"id": att_id, "name": name, "type": "image/png"}


SHOTS = [_att("a1", "image.png"), _att("a2", "image.png"), _att("a3", "notes.md")]


def test_select_by_id_wins_over_name():
    from planecli.commands.attachments import _select_attachments

    assert _select_attachments(SHOTS, "a2", False) == [SHOTS[1]]


def test_select_by_unique_name():
    from planecli.commands.attachments import _select_attachments

    assert _select_attachments(SHOTS, "notes.md", False) == [SHOTS[2]]


def test_select_shared_name_requires_id_or_all():
    from planecli.commands.attachments import _select_attachments
    from planecli.exceptions import ValidationError

    with pytest.raises(ValidationError, match="2 attachments are named") as exc:
        _select_attachments(SHOTS, "image.png", False)
    # the hint lists the ids to choose from
    assert "a1" in exc.value.hint and "a2" in exc.value.hint
    assert _select_attachments(SHOTS, "image.png", True) == SHOTS[:2]


def test_select_unknown_selector_lists_attachments():
    from planecli.commands.attachments import _select_attachments
    from planecli.exceptions import ValidationError

    with pytest.raises(ValidationError, match="No attachment matches") as exc:
        _select_attachments(SHOTS, "missing.png", False)
    assert "notes.md" in exc.value.hint


def test_select_without_selector():
    from planecli.commands.attachments import _select_attachments
    from planecli.exceptions import ValidationError

    assert _select_attachments(SHOTS[:1], None, False) == SHOTS[:1]
    assert _select_attachments(SHOTS, None, True) == SHOTS
    with pytest.raises(ValidationError, match="choose one"):
        _select_attachments(SHOTS, None, False)
    with pytest.raises(ValidationError, match="no attachments"):
        _select_attachments([], None, True)


def test_plan_paths_suffixes_duplicates_and_existing_files(tmp_path):
    from planecli.commands.attachments import _plan_paths

    (tmp_path / "notes.md").write_text("already here")
    paths = _plan_paths(SHOTS, tmp_path, overwrite=False)
    assert [p.name for p in paths] == ["image.png", "image-2.png", "notes-2.md"]


def test_plan_paths_overwrite_keeps_existing_name(tmp_path):
    from planecli.commands.attachments import _plan_paths

    (tmp_path / "notes.md").write_text("already here")
    paths = _plan_paths(SHOTS, tmp_path, overwrite=True)
    assert [p.name for p in paths] == ["image.png", "image-2.png", "notes.md"]


def test_plan_paths_strips_directories_from_names(tmp_path):
    from planecli.commands.attachments import _plan_paths

    paths = _plan_paths([_att("a1", "../../etc/passwd"), _att("a2", "")], tmp_path, False)
    assert paths == [tmp_path / "passwd", tmp_path / "a2"]


def _http(status: int, headers: dict | None = None, chunks: list[bytes] | None = None):
    m = MagicMock(status_code=status, headers=headers or {})
    m.is_redirect = 300 <= status < 400
    m.iter_content.return_value = chunks or []
    m.__enter__.return_value = m
    return m


def test_download_follows_redirect_without_api_key(tmp_path):
    from planecli.commands.attachments import _download_attachment

    redirect = _http(302, {"Location": "/uploads/obj?sig=1"})
    body = _http(200, chunks=[b"abc", b"de"])
    with patch("requests.get", side_effect=[redirect, body]) as mock_get:
        written = _download_attachment(
            "http://plane.local/api/v1/workspaces/ws/x/a1/", "secret", tmp_path / "f.png"
        )

    assert written == 5
    assert (tmp_path / "f.png").read_bytes() == b"abcde"
    first, second = mock_get.call_args_list
    assert first.kwargs["headers"] == {"X-Api-Key": "secret"}
    assert first.kwargs["allow_redirects"] is False
    # relative Location resolved against the API host; no key sent to storage
    assert second.args[0] == "http://plane.local/uploads/obj?sig=1"
    assert "headers" not in second.kwargs


def test_download_error_leaves_no_partial_file(tmp_path):
    from planecli.commands.attachments import _download_attachment
    from planecli.exceptions import APIError

    with patch("requests.get", return_value=_http(400)), pytest.raises(APIError):
        _download_attachment("http://plane.local/a/", "k", tmp_path / "f.png")

    body = _http(200)
    body.iter_content.side_effect = OSError("connection reset")
    with patch("requests.get", return_value=body), pytest.raises(OSError):
        _download_attachment("http://plane.local/a/", "k", tmp_path / "f.png")
    assert list(tmp_path.iterdir()) == []


@patch("planecli.commands.attachments.get_workspace", return_value="ws")
@patch("planecli.commands.attachments.get_client")
@patch("planecli.commands.attachments._resolve_item", new_callable=AsyncMock)
@patch("planecli.commands.attachments.run_sdk", new_callable=AsyncMock)
async def test_get_all_downloads_each_selected_attachment(
    mock_run, mock_resolve, _client, _ws, tmp_path, capsys
):
    import json as jsonlib

    from planecli.commands.attachments import get

    mock_resolve.return_value = ({"id": "item-1"}, "proj-1")
    listed = [
        {"id": "a1", "attributes": {"name": "image.png", "type": "image/png"}},
        {"id": "a2", "attributes": {"name": "image.png", "type": "image/png"}},
        {"id": "a3", "attributes": {"name": "old.png"}, "is_deleted": True},
    ]
    mock_run.side_effect = [listed, 10, 20]

    with patch(
        "planecli.api.client.get_config",
        return_value=MagicMock(base_url="http://plane.local", api_key="k"),
    ):
        await get("ABC-1", "image.png", all_=True, dir=str(tmp_path), json=True)

    out = jsonlib.loads(capsys.readouterr().out)
    assert [(o["id"], o["size"]) for o in out] == [("a1", 10), ("a2", 20)]
    assert [o["path"].rsplit("/", 1)[1] for o in out] == ["image.png", "image-2.png"]
    url = mock_run.call_args_list[1].args[1]
    assert url == (
        "http://plane.local/api/v1/workspaces/ws/projects/proj-1/"
        "work-items/item-1/attachments/a1/"
    )


@patch("planecli.commands.attachments.get_workspace", return_value="ws")
@patch("planecli.commands.attachments.get_client")
@patch("planecli.commands.attachments._resolve_item", new_callable=AsyncMock)
@patch("planecli.commands.attachments.run_sdk", new_callable=AsyncMock)
async def test_get_output_rejects_several_attachments(mock_run, mock_resolve, _client, _ws):
    from planecli.commands.attachments import get
    from planecli.exceptions import ValidationError

    mock_resolve.return_value = ({"id": "item-1"}, "proj-1")
    mock_run.side_effect = [
        [{"id": "a1", "attributes": {"name": "x"}}, {"id": "a2", "attributes": {"name": "y"}}]
    ]
    with pytest.raises(ValidationError, match="--output takes a single"):
        await get("ABC-1", all_=True, output_file="out.bin")


async def test_get_rejects_output_with_dir():
    from planecli.commands.attachments import get
    from planecli.exceptions import ValidationError

    with pytest.raises(ValidationError, match="not both"):
        await get("ABC-1", output_file="a", dir=".")
