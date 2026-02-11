"""Color utilities for Rich terminal output."""

from __future__ import annotations

from rich.text import Text

PRIORITY_COLORS: dict[str, str] = {
    "urgent": "#ef4444",
    "high": "#f97316",
    "medium": "#eab308",
    "low": "#22c55e",
    "none": "#a3a3a3",
}


def _normalize_hex(color: str) -> str:
    """Normalize a hex color string for Rich compatibility.

    Handles missing '#' prefix and 3-char shorthand (#fff -> #ffffff).
    """
    color = color.strip()
    if not color.startswith("#"):
        color = f"#{color}"
    # Expand 3-char shorthand: #abc -> #aabbcc
    if len(color) == 4:
        color = f"#{color[1]*2}{color[2]*2}{color[3]*2}"
    return color


def lighten_hex(color: str, factor: float = 0.35) -> str:
    """Lighten a hex color by blending it towards white.

    Args:
        color: Hex color string (e.g. '#a3a3a3').
        factor: 0.0 = unchanged, 1.0 = white. Default 0.35.
    """
    color = _normalize_hex(color)
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def colorize(text: str, color: str | None) -> str | Text:
    """Create a colored Rich Text object, or return plain string on failure.

    Args:
        text: The text to colorize.
        color: Hex color string (e.g. '#FFA500'). If None/empty, returns plain text.

    Returns:
        A Rich Text object with color styling, or the plain string if color is unavailable.
    """
    if not text:
        return ""
    if not color:
        return text
    try:
        return Text(text, style=_normalize_hex(color))
    except Exception:
        return text


def color_swatch(hex_color: str) -> str | Text:
    """Return a colored unicode block followed by the hex string.

    Used in 'state list' and 'label list' Color columns.

    Args:
        hex_color: Hex color string (e.g. '#FFA500').

    Returns:
        A Rich Text with colored swatch + hex string, or the raw hex on failure.
    """
    if not hex_color:
        return ""
    try:
        normalized = _normalize_hex(hex_color)
        result = Text()
        result.append("\u2588\u2588 ", style=normalized)
        result.append(hex_color)
        return result
    except Exception:
        return hex_color
