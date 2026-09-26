"""Tests for Phase 4 — the rendering engine."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reviewer import rendering

MD = """## BUG_REPORT
- **Critical** Undefined name 'db' at line 5.

## REFACTORED_CODE
```python
def f():
    return 1
```
"""


def test_plain_render_returns_text(capsys):
    out = rendering.render_terminal(MD, plain=True)
    assert out == MD
    captured = capsys.readouterr()
    assert "## BUG_REPORT" in captured.out


def test_rich_render_does_not_crash(capsys):
    out = rendering.render_terminal(MD, plain=False)
    assert out == MD  # returns the markdown regardless


def test_markdown_to_html_structure():
    html = rendering.markdown_to_html(MD)
    assert "<h2>BUG_REPORT</h2>" in html
    assert "<ul>" in html and "<li>" in html
    assert "<strong>Critical</strong>" in html
    assert '<pre><code class="language-python">' in html
    assert "def f():" in html


def test_markdown_to_html_escapes():
    html = rendering.markdown_to_html("## BUG_REPORT\n- x <script> & y\n")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
