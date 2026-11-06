"""Tests for `wi create -i` / `wi update -i` (description images)."""

from __future__ import annotations

import inspect
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from planecli.commands.work_items import create, update
from planecli.exceptions import ResourceNotFoundError, ValidationError

WI = "planecli.commands.work_items"
UPLOAD = "planecli.commands.attachments.upload_embed_image"


def _img(tmp_path, name="shot.png"):
    f = tmp_path / name
    f.write_bytes(b"png")
    return str(f)


def _item(**fields):
    m = MagicMock()
    m.model_dump.return_value = {
        "id": "wi-1",
        "name": "Bug",
        "sequence_id": 5,
        "priority": "high",
        "project_detail": {"identifier": "ABC"},
        **fields,
    }
    return m


class _Sdk:
    """run_sdk stand-in that records create/update payloads by SDK method."""

    def __init__(self, client, item):
        self.client = client
        self.item = item
        self.created = []
        self.updated = []

    async def call(self, fn, *args, **_kwargs):
        if fn is self.client.work_items.create:
            self.created.append(args[-1])
        elif fn is self.client.work_items.update:
            self.updated.append(args[-1])
        return self.item


@pytest.fixture
def wi_env():
    client = MagicMock()
    with (
        patch(f"{WI}.get_client", return_value=client),
        patch(f"{WI}.get_workspace", return_value="ws"),
        patch(f"{WI}._resolve_project_id_async", new_callable=AsyncMock) as resolve_proj,
        patch(f"{WI}.run_sdk", new_callable=AsyncMock) as run_sdk,
        patch("planecli.cache.invalidate_resource", new_callable=AsyncMock),
        patch(UPLOAD, new_callable=AsyncMock) as upload,
    ):
        resolve_proj.return_value = "proj-1"
        yield {"client": client, "run_sdk": run_sdk, "upload": upload}


# --- wi create -i ---------------------------------------------------------


async def test_wi_create_image_missing_path_creates_nothing(wi_env, tmp_path):
    ok = _img(tmp_path)
    missing = str(tmp_path / "missing.png")

    with pytest.raises(ValidationError, match=f"File not found: {missing}") as exc:
        await create("Bug", project="Frontend", image=[ok, missing])

    assert exc.value.exit_code == 5
    wi_env["run_sdk"].assert_not_called()
    wi_env["upload"].assert_not_called()


async def test_wi_create_image_keeps_description(wi_env, tmp_path):
    sdk = _Sdk(wi_env["client"], _item())
    wi_env["run_sdk"].side_effect = sdk.call
    wi_env["upload"].side_effect = ["asset-a", "asset-b"]

    await create(
        "Bug",
        project="Frontend",
        description="Steps",
        image=[_img(tmp_path, "a.png"), _img(tmp_path, "b.png")],
    )

    assert sdk.created[0].description_html == "<p>Steps</p>"
    assert sdk.updated[0].description_html == (
        '<p>Steps</p><p><img src="asset-a" /></p><p><img src="asset-b" /></p>'
    )


async def test_wi_create_image_enriches_once(wi_env, tmp_path, capsys):
    wi_env["run_sdk"].side_effect = _Sdk(wi_env["client"], _item()).call
    wi_env["upload"].return_value = "asset-a"

    await create("Bug", project="Frontend", priority="high", image=[_img(tmp_path)], json=True)

    data = json.loads(capsys.readouterr().out)
    assert data["priority"] == "high"
    assert data["sequence_id"] == "ABC-5"


def test_wi_create_has_no_force_flag():
    from planecli.app import app

    with pytest.raises(Exception):
        app.parse_args(["wi", "create", "Bug", "-p", "Frontend", "--force"], exit_on_error=False)
    assert "force" not in inspect.signature(create).parameters


# --- wi update -i ---------------------------------------------------------


@pytest.fixture
def wi_update_env(wi_env):
    with patch(
        f"{WI}.resolve_work_item_across_projects_async", new_callable=AsyncMock
    ) as resolve_wi:
        resolve_wi.return_value = (
            {"id": "wi-1", "description_html": "<p>Old</p>"},
            "proj-1",
        )
        wi_env["resolve_wi"] = resolve_wi
        yield wi_env


async def test_wi_update_image_missing_path_resolves_nothing(wi_update_env, tmp_path):
    missing = str(tmp_path / "missing.png")

    with pytest.raises(ValidationError, match="File not found") as exc:
        await update("ABC-5", image=[missing], state="Done")

    assert exc.value.exit_code == 5
    wi_update_env["resolve_wi"].assert_not_called()
    wi_update_env["upload"].assert_not_called()
    wi_update_env["run_sdk"].assert_not_called()


async def test_wi_update_image_not_uploaded_when_state_fails(wi_update_env, tmp_path):
    with patch(f"{WI}.resolve_state_async", new_callable=AsyncMock) as resolve_state:
        resolve_state.side_effect = ResourceNotFoundError("State", "In Progres")
        with pytest.raises(ResourceNotFoundError) as exc:
            await update("ABC-5", image=[_img(tmp_path)], state="In Progres")

    assert exc.value.exit_code == 3
    wi_update_env["upload"].assert_not_called()


async def test_wi_update_image_not_uploaded_when_labels_fail(wi_update_env, tmp_path):
    with patch(f"{WI}.resolve_label_async", new_callable=AsyncMock) as resolve_label:
        resolve_label.side_effect = ResourceNotFoundError("Label", "bgu")
        with pytest.raises(ResourceNotFoundError):
            await update("ABC-5", image=[_img(tmp_path)], labels="bgu")

    wi_update_env["upload"].assert_not_called()


async def test_wi_update_image_appends_to_existing_description(wi_update_env, tmp_path):
    sdk = _Sdk(wi_update_env["client"], _item())
    wi_update_env["run_sdk"].side_effect = sdk.call
    wi_update_env["upload"].return_value = "asset-a"

    await update("ABC-5", image=[_img(tmp_path)])

    assert sdk.updated[0].description_html == '<p>Old</p><p><img src="asset-a" /></p>'


async def test_wi_update_image_with_new_description(wi_update_env, tmp_path):
    sdk = _Sdk(wi_update_env["client"], _item())
    wi_update_env["run_sdk"].side_effect = sdk.call
    wi_update_env["upload"].return_value = "asset-a"

    await update("ABC-5", description="New", image=[_img(tmp_path)])

    assert sdk.updated[0].description_html == '<p>New</p><p><img src="asset-a" /></p>'


def test_wi_update_force_help_mentions_v1_fallback():
    doc = inspect.getdoc(update) or ""
    force_help = doc.split("force\n", 1)[1]
    assert "v1" in force_help
    assert "fall" in force_help.lower()
