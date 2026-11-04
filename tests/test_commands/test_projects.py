"""Tests for project commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from plane.errors import HttpError

from planecli.commands.projects import _default_identifier, create
from planecli.exceptions import APIError, ValidationError
from planecli.utils.resolve import ISSUE_ID_PATTERN


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Frontend App", "FRONT"),
        ("My Project", "MYPRO"),
        ("My_Backend/API", "MYBAC"),
        ("FE", "FE"),
        ("backend", "BACKE"),
        # Digits would break ABC-123 resolution
        ("Q3 Roadmap", "QROAD"),
        ("2024 Roadmap", "ROADM"),
        # Accents are folded, not dropped
        ("Ação Social", "ACAOS"),
        # Never longer than 5, even when uppercasing expands a character
        ("Straße", "STRAE"),
    ],
)
def test_default_identifier(name: str, expected: str) -> None:
    assert _default_identifier(name) == expected


@pytest.mark.parametrize("name", ["", "___", "🚀🚀", "2024", "日本語プロジェクト"])
def test_default_identifier_empty_when_no_usable_letters(name: str) -> None:
    assert _default_identifier(name) == ""


@pytest.mark.parametrize("name", ["Frontend App", "Q3 Roadmap", "2024 Roadmap", "Ação Social"])
def test_default_identifier_is_resolvable_as_work_item_prefix(name: str) -> None:
    """A derived identifier must form IDs that the resolver can read."""
    assert ISSUE_ID_PATTERN.match(f"{_default_identifier(name)}-12")


@pytest.fixture
def mock_create_deps():
    """Patch everything create() touches; yields the run_sdk mock."""
    with (
        patch("planecli.commands.projects.get_client", return_value=MagicMock()),
        patch("planecli.commands.projects.get_workspace", return_value="ws"),
        patch("planecli.commands.projects.output_single"),
        patch("planecli.cache.invalidate_resource", new_callable=AsyncMock),
        patch("planecli.commands.projects.run_sdk", new_callable=AsyncMock) as mock_run_sdk,
    ):
        mock_run_sdk.return_value = MagicMock()
        yield mock_run_sdk


def _payload(mock_run_sdk: AsyncMock):
    return mock_run_sdk.call_args[0][2]


async def test_create_derives_identifier_when_not_given(mock_create_deps) -> None:
    await create("My Project")
    assert _payload(mock_create_deps).identifier == "MYPRO"


async def test_create_explicit_identifier_wins_and_is_uppercased(mock_create_deps) -> None:
    await create("My Project", identifier="fe")
    assert _payload(mock_create_deps).identifier == "FE"


async def test_create_explicit_identifier_skips_derivation(mock_create_deps) -> None:
    """A name with no usable letters is fine when -i is given."""
    await create("___", identifier="fe")
    assert _payload(mock_create_deps).identifier == "FE"


async def test_create_rejects_underivable_name_without_calling_api(mock_create_deps) -> None:
    with pytest.raises(ValidationError) as exc:
        await create("___")
    assert "-i" in (exc.value.hint or "")
    mock_create_deps.assert_not_called()


async def test_create_conflict_on_derived_identifier_names_the_value(mock_create_deps) -> None:
    mock_create_deps.side_effect = HttpError("Conflict", status_code=409)
    with pytest.raises(ValidationError) as exc:
        await create("Frontend App")
    assert "FRONT" in exc.value.message
    assert "-i" in (exc.value.hint or "")


async def test_create_conflict_on_explicit_identifier_stays_api_error(mock_create_deps) -> None:
    mock_create_deps.side_effect = HttpError("Conflict", status_code=409)
    with pytest.raises(APIError):
        await create("Frontend App", identifier="FE")


async def test_create_other_http_errors_stay_api_error(mock_create_deps) -> None:
    mock_create_deps.side_effect = HttpError("Bad request", status_code=400)
    with pytest.raises(APIError):
        await create("Frontend App")
