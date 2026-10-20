"""Tests for table/JSON output formatting."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from planecli.formatters import _format_value


def _render(value) -> str:
    console = Console(width=200, record=True)
    console.print(value)
    return console.export_text().rstrip("\n")


def test_brackets_in_values_are_not_rich_markup():
    # As a plain str, Rich would treat "[x]" as a style tag and drop it.
    value = _format_value("- [x] done\n- [ ] todo [bold]literal[/bold]")
    assert _render(value) == "- [x] done\n- [ ] todo [bold]literal[/bold]"


def test_timestamps_are_prettified():
    assert _format_value("2026-02-08T12:26:34.340901Z") == "2026-02-08 12:26:34"


def test_long_values_fold_instead_of_truncating():
    long = "x" * 120
    assert _format_value(long).overflow == "fold"
    assert _format_value("short").overflow is None


def test_text_values_pass_through():
    styled = Text("red", style="red")
    assert _format_value(styled) is styled
