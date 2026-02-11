"""Output formatting: Rich tables to stderr, JSON to stdout."""

from __future__ import annotations

import json
import sys
from typing import Any, Sequence

from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console(stderr=True)
error_console = Console(stderr=True)


def _format_value(value: Any) -> str | Text:
    """Format a value for table display, prettifying timestamps.

    Rich Text objects are passed through unchanged to preserve color styling.
    """
    if isinstance(value, Text):
        return value
    if not value:
        return ""
    s = str(value)
    # ISO timestamp like "2026-02-08T12:26:34.340901Z" -> "2026-02-08 12:26:34"
    if len(s) >= 20 and s[10:11] == "T" and s.endswith("Z"):
        return s[:19].replace("T", " ")
    return s


def output(
    data: Sequence[dict[str, Any]],
    columns: list[tuple[str, str]],
    *,
    title: str | None = None,
    as_json: bool = False,
) -> None:
    """Output a list of records as a table or JSON.

    Args:
        data: List of dicts to display.
        columns: List of (key, header_label) tuples defining columns.
        title: Optional table title.
        as_json: If True, output JSON to stdout instead of a table.
    """
    if as_json:
        json.dump(list(data), sys.stdout, indent=2, default=str, ensure_ascii=False)
        sys.stdout.write("\n")
        return

    table = Table(title=title, show_lines=True, padding=(0, 1))
    for _, header in columns:
        table.add_column(header)

    for item in data:
        row = [_format_value(item.get(key, "")) for key, _ in columns]
        table.add_row(*row)

    console.print(table)


def output_single(
    data: dict[str, Any],
    fields: list[tuple[str, str]],
    *,
    title: str | None = None,
    as_json: bool = False,
) -> None:
    """Output a single record as key-value pairs or JSON.

    Args:
        data: Dict to display.
        fields: List of (key, label) tuples defining which fields to show.
        title: Optional title.
        as_json: If True, output JSON to stdout instead of a table.
    """
    if as_json:
        json.dump(data, sys.stdout, indent=2, default=str, ensure_ascii=False)
        sys.stdout.write("\n")
        return

    table = Table(title=title, show_header=False, show_lines=True, padding=(0, 1))
    table.add_column("Field", style="bold cyan", width=20)
    table.add_column("Value")

    for key, label in fields:
        value = data.get(key, "")
        table.add_row(label, _format_value(value))

    console.print(table)
