"""Convert plain user-authored text to the HTML Plane's editor stores.

The Plane API stores HTML verbatim and does not parse markdown or auto-link
URLs — only the web editor does — so text written via the CLI must arrive
already converted. Used by document write commands.
"""

from __future__ import annotations

import html
import re

_URL_RE = re.compile(r"(?<![\"'>=])(https?://[A-Za-z0-9\-._~:/?#\[\]@!$&()*+,;=%]+)")
# Trailing punctuation that belongs to the sentence, not the URL.
_URL_TRAIL = ".,;:!?)]}。，；：！？）】、"
# A fenced block: an opening ``` line with an optional info string (py, c++,
# shell-session...), the body, and a closing ``` line.
_FENCE_RE = re.compile(r"^[ \t]*```[^\n`]*\n(.*?)^[ \t]*```[ \t]*$", re.DOTALL | re.MULTILINE)


def _linkify(text: str) -> str:
    """Turn bare http(s) URLs into anchors.

    URLs already inside an href attribute are left alone (the regex excludes
    matches preceded by a quote or angle bracket from an attribute context).
    """

    def _sub(m: re.Match[str]) -> str:
        raw = m.group(1)
        url = raw.rstrip(_URL_TRAIL)
        # Keep a closing paren that balances one inside the URL: .../Foo_(bar)
        while raw[len(url) :].startswith(")") and url.count("(") > url.count(")"):
            url += ")"
        return f'<a href="{url}">{url}</a>{raw[len(url) :]}'

    return _URL_RE.sub(_sub, text)


def _inline(text: str) -> str:
    """Convert one paragraph: code spans, bare URLs, and line breaks."""
    # Odd slots of the split are code-span contents, so URLs inside them are
    # never linkified.
    parts = re.split(r"`([^`\n]+)`", text)
    converted = "".join(
        f"<code>{html.escape(part)}</code>" if i % 2 else _linkify(part)
        for i, part in enumerate(parts)
    )
    return converted.replace("\n", "<br/>")


def body_to_html(body: str) -> str:
    """Convert plain text to HTML paragraphs.

    Blank lines separate paragraphs; a single newline becomes a br tag —
    the editor collapses whitespace inside a paragraph, so unconverted
    newlines would render as one long line. Backticks become code tags and
    fenced blocks become pre-wrapped code (the editor stores HTML, it does
    not parse markdown). Empty input gives an empty paragraph.
    """
    parts: list[str] = []
    # Odd slots of the split are fence bodies, so a block never lands inside
    # a paragraph.
    for i, segment in enumerate(_FENCE_RE.split(body.replace("\r\n", "\n").strip())):
        if i % 2:
            code = html.escape(segment.strip("\n"))
            parts.append(f"<pre><code>{code}</code></pre>")
            continue
        for p in re.split(r"\n\s*\n", segment):
            if p.strip():
                parts.append(f"<p>{_inline(p.strip())}</p>")
    return "".join(parts) or "<p></p>"
