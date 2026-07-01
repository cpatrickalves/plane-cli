"""Tests for module commands."""

from __future__ import annotations

import pytest

from planecli.commands.modules import MODULE_STATUSES, _normalize_status
from planecli.exceptions import ValidationError


@pytest.mark.parametrize("status", MODULE_STATUSES)
def test_normalize_status_canonical_values(status: str) -> None:
    """Canonical status values pass through unchanged."""
    assert _normalize_status(status) == status


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("In-Progress", "in-progress"),
        ("  in-progress  ", "in-progress"),
        ("in progress", "in-progress"),
        ("in_progress", "in-progress"),
        ("inprogress", "in-progress"),
        ("canceled", "cancelled"),
        # Portuguese aliases
        ("em andamento", "in-progress"),
        ("Em Andamento", "in-progress"),
        ("planejado", "planned"),
        ("pausado", "paused"),
        ("concluido", "completed"),
        ("concluído", "completed"),
        ("cancelado", "cancelled"),
    ],
)
def test_normalize_status_aliases_and_casing(value: str, expected: str) -> None:
    """Aliases (English + Portuguese) and mixed casing normalize correctly."""
    assert _normalize_status(value) == expected


@pytest.mark.parametrize("value", ["foobar", "done", "started", ""])
def test_normalize_status_invalid_raises(value: str) -> None:
    """Invalid statuses raise ValidationError listing the valid values."""
    with pytest.raises(ValidationError) as exc:
        _normalize_status(value)
    assert "in-progress" in (exc.value.hint or "")
