"""Shared test fixtures."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_plane_client():
    """Create a mock PlaneClient."""
    client = MagicMock()
    client.users.get_me.return_value = MagicMock(
        id="user-uuid-1",
        display_name="Patrick",
        first_name="Patrick",
        last_name="Alves",
        email="patrick@example.com",
        model_dump=lambda: {
            "id": "user-uuid-1",
            "display_name": "Patrick",
            "first_name": "Patrick",
            "last_name": "Alves",
            "email": "patrick@example.com",
        },
    )
    return client
