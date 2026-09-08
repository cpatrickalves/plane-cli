"""Convert plain user-authored text to the HTML Plane's editor stores.

The Plane API stores HTML verbatim and does not parse markdown or auto-link
URLs — only the web editor does — so text written via the CLI must arrive
already converted. Shared by comment and document write commands.
"""

from __future__ import annotations

import html
import re

_URL_RE = re.compile(r"(?<![\"'>=])(https?://[A-Za-z0-9\-._~:/?#\[\]@!$&()*+,;=%]+)")
# Trailing punctuation that belongs to the sentence, not the URL.
_URL_TRAIL = ".,;:!?)]}。，；：！？）】、"


def _linkify(text: str) -> str:
    """Turn bare http(s) URLs into anchors.

    URLs already inside an href attribute are left alone (the regex excludes
    matches preceded by a quote or angle bracket from an attribute context).
    """

    def _sub(m: re.Match[str]) -> str:
        url = m.group(1).rstrip(_URL_TRAIL)
        trail = m.group(1)[len(url) :]
        return f'<a href="{url}">{url}</a>{trail}'

    return _URL_RE.sub(_sub, text)


def _inline_code(text: str) -> str:
    """Convert `inline code` to a code tag with HTML-escaped content."""
    return re.sub(
        r"`([^`\n]+)`",
        lambda m: f"<code>{html.escape(m.group(1))}</code>",
        text,
    )


def _extract_code_blocks(text: str) -> tuple[str, list[str]]:
    """Pull fenced code blocks out of the text, replacing each with a token.

    Returns the text with \x00N\x00 placeholders and the list of HTML
    fragments (pre-wrapped escaped code) to restore at the end. Extracting
    first keeps their content out of linkify and the newline-to-br pass.
    """
    blocks: list[str] = []

    def _hold(match: re.Match[str]) -> str:
        code = html.escape(match.group(1).strip("\n"))
        blocks.append(f"<pre><code>{code}</code></pre>")
        return f"\x00{len(blocks) - 1}\x00"

    text = re.sub(
        r"```[ \t]*\w*[ \t]*\n(.*?)```",
        _hold,
        text,
        flags=re.DOTALL,
    )
    return text, blocks


def body_to_html(body: str) -> str:
    """Convert plain text to HTML paragraphs.

    Blank lines separate paragraphs; a single newline becomes a br tag —
    the editor collapses whitespace inside a paragraph, so unconverted
    newlines would render as one long line. Backticks become code tags and
    fenced blocks become pre-wrapped code (the editor stores HTML, it does
    not parse markdown).
    """
    text, blocks = _extract_code_blocks(body.strip())
    parts: list[str] = []
    for p in re.split(r"\n\s*\n", text):
        p = p.strip()
        if not p:
            continue
        converted = _linkify(_inline_code(p)).replace(chr(10), "<br/>")
        if re.fullmatch(r"(?:\x00\d+\x00[ \t]*)+", p):
            # A paragraph that is only a code block keeps its pre wrapper.
            parts.append(converted)
        else:
            parts.append(f"<p>{converted}</p>")
    result = "".join(parts)
    for i, fragment in enumerate(blocks):
        result = result.replace(f"\x00{i}\x00", fragment)
    return result
