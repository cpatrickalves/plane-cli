"""Convert the HTML Plane's editor stores into Markdown for display.

Work item descriptions and comments come back as editor HTML: paragraphs
carrying class and data-id noise, Tiptap task lists, and custom nodes such
as image-component. Stripping the tags flattens all of that into one line;
converting to Markdown keeps paragraphs, line breaks, lists, links, code,
tables and images readable in a terminal and for agents.
"""

from __future__ import annotations

import re

from markdownify import ATX, MarkdownConverter

_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")
# Containers whose direct img children are blocks of their own: the editor
# emits consecutive top-level images that would otherwise run together.
_BLOCK_PARENTS = {"[document]", "body", "div", "figure", "section", "article"}


def _is_task_item(el) -> bool:
    """True for a Tiptap task-list item (li inside ul data-type=taskList)."""
    if el.get("data-type") == "taskItem" or el.has_attr("data-checked"):
        return True
    parent = el.parent
    return parent is not None and parent.get("data-type") == "taskList"


def _code_language(el) -> str:
    """Read the fence language from a code class like language-python."""
    code = el.find("code")
    for cls in (code.get("class") if code is not None else None) or []:
        if cls.startswith("language-"):
            return cls[len("language-") :]
    return ""


class _PlaneConverter(MarkdownConverter):
    """markdownify with Plane's editor nodes on top."""

    def convert_li(self, el, text, parent_tags):
        if _is_task_item(el):
            box = "[x]" if str(el.get("data-checked", "")).lower() == "true" else "[ ]"
            text = f"{box} {(text or '').strip()}"
        return super().convert_li(el, text, parent_tags)

    def convert_input(self, el, text, parent_tags):
        # The checkbox of a task item; its state is read from the li above.
        return ""

    def convert_img(self, el, text, parent_tags):
        # Keep images visible even inside table cells and headings, where
        # markdownify would reduce them to their alt text.
        alt = el.get("alt") or ""
        src = el.get("src") or ""
        if not src:
            return alt
        image = f"![{alt}]({src})"
        parent = el.parent.name if el.parent is not None else "[document]"
        return f"\n\n{image}\n\n" if parent in _BLOCK_PARENTS else image

    def convert_image_component(self, el, text, parent_tags):
        # Plane's image node stores the asset UUID (not a URL) in src.
        src = el.get("src") or ""
        if not src:
            return ""
        image = f"![{el.get('alt') or 'image'}]({src})"
        return image if "_inline" in parent_tags else f"\n\n{image}\n\n"

    def convert_mention_component(self, el, text, parent_tags):
        label = el.get("label") or el.get("entity_identifier") or ""
        return f"@{label}" if label else ""


_converter = _PlaneConverter(
    heading_style=ATX,
    bullets="-",
    # Display output: escaping every underscore (prob_mean) and asterisk
    # makes plain prose harder to read than the rare ambiguity it avoids.
    escape_underscores=False,
    escape_asterisks=False,
    # Editor tables have no header row; promote the first row so the
    # result is a valid Markdown table.
    table_infer_header=True,
    code_language_callback=_code_language,
)


def html_to_markdown(html: str | None) -> str:
    """Convert editor HTML to Markdown; empty input gives an empty string."""
    if not html or not html.strip():
        return ""
    text = _converter.convert(html)
    # Empty paragraphs (Plane prepends one) leave runs of blank lines.
    return _EXTRA_BLANK_LINES.sub("\n\n", text).strip()
