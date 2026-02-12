"""Logging configuration using loguru."""

from __future__ import annotations

import sys

from loguru import logger


def setup_logging(*, verbose: bool = False) -> None:
    """Configure loguru for CLI output.

    - Remove default handler (stdout)
    - Add stderr handler to not pollute JSON/table output
    - Default level: WARNING (show rate limit warnings)
    - Verbose mode: DEBUG (show all API calls)
    """
    logger.remove()  # Remove default handler
    level = "DEBUG" if verbose else "WARNING"
    logger.add(
        sys.stderr,
        level=level,
        format="<level>{level}</level> | {message}",
        colorize=True,
    )
