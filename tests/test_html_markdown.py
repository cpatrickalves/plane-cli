"""Tests for the editor-HTML to Markdown converter."""

from __future__ import annotations

from planecli.utils.html_markdown import html_to_markdown


def test_empty_input_gives_empty_string():
    assert html_to_markdown(None) == ""
    assert html_to_markdown("") == ""
    assert html_to_markdown("<p></p>") == ""


def test_paragraphs_and_line_breaks_survive():
    html = '<p class="editor-paragraph-block" data-id="x">one<br>two</p><p></p><p>three</p>'
    assert html_to_markdown(html) == "one  \ntwo\n\nthree"


def test_lists_links_and_inline_code():
    html = (
        "<ul><li><p>see <a href='https://x.io/a_b'>docs</a></p></li>"
        "<li><p><code>prob_mean</code> is <strong>key</strong></p></li></ul>"
        "<ol><li><p>first</p></li><li><p>second</p></li></ol>"
    )
    assert html_to_markdown(html) == (
        "- see [docs](https://x.io/a_b)\n- `prob_mean` is **key**\n\n1. first\n2. second"
    )


def test_underscores_in_prose_are_not_escaped():
    assert html_to_markdown("<p>use snake_case here</p>") == "use snake_case here"


def test_plane_task_list_renders_checkboxes():
    html = (
        '<ul data-type="taskList">'
        '<li data-checked="true" data-type="taskItem"><label><input type="checkbox" checked>'
        "<span></span></label><div><p>done</p></div></li>"
        '<li data-checked="false" data-type="taskItem"><label><input type="checkbox">'
        "</label><div><p>todo</p></div></li></ul>"
    )
    assert html_to_markdown(html) == "- [x] done\n- [ ] todo"


def test_fenced_code_keeps_language():
    html = '<pre><code class="language-python">a = 1\nb = 2</code></pre>'
    assert html_to_markdown(html) == "```python\na = 1\nb = 2\n```"


def test_table_gets_a_header_row():
    html = (
        "<table><tbody><tr><td><p><strong>ClickUp</strong></p></td>"
        "<td><p><a href='https://c.u/t/1'>1</a></p></td></tr>"
        "<tr><td><p>Status</p></td><td><p>done</p></td></tr></tbody></table>"
    )
    assert html_to_markdown(html) == (
        "| **ClickUp** | [1](https://c.u/t/1) |\n| --- | --- |\n| Status | done |"
    )


def test_consecutive_top_level_images_are_separate_blocks():
    html = '<h3>Images</h3><img src="https://h/a" alt="a.png"><img src="https://h/b" alt="">'
    assert html_to_markdown(html) == "### Images\n\n![a.png](https://h/a)\n\n![](https://h/b)"


def test_inline_image_stays_inline():
    assert html_to_markdown('<p>see <img src="u" alt="x"></p>') == "see ![x](u)"


def test_image_component_becomes_image_reference():
    html = '<p>before</p><image-component src="0e3a-asset" width="300"></image-component>'
    assert html_to_markdown(html) == "before\n\n![image](0e3a-asset)"


def test_mention_component_becomes_at_reference():
    html = '<p>hi <mention-component entity_identifier="u-1"></mention-component></p>'
    assert html_to_markdown(html) == "hi @u-1"
