"""Phase 4 — The Rendering Engine.

The engine compiles the verified markdown and prints color-mapped,
syntax-highlighted output directly in the console, driven by the
language tags on the fenced code blocks (``rich.markdown.Markdown``).
"""

from __future__ import annotations


def render_terminal(markdown_text: str, plain: bool = False) -> str:
    """Render markdown to the terminal with syntax highlighting.

    Returns the original markdown text (useful for --save flows).
    Falls back to raw output when ``plain`` is set or Rich is missing.
    """
    if plain:
        print(markdown_text)
        return markdown_text
    try:
        from rich.console import Console
        from rich.markdown import Markdown
    except ImportError:
        print(markdown_text)
        return markdown_text
    console = Console()
    console.print(Markdown(markdown_text))
    return markdown_text


def markdown_to_html(markdown_text: str) -> str:
    """Minimal markdown -> HTML for the web UI (client highlights code)."""
    import html
    import re

    out: list[str] = []
    in_code = False
    code_lang = ""
    code_buf: list[str] = []
    for line in markdown_text.splitlines():
        m = re.match(r"^```(\w*)\s*$", line)
        if m and not in_code:
            in_code, code_lang, code_buf = True, m.group(1), []
            continue
        if line.strip() == "```" and in_code:
            in_code = False
            out.append(
                f'<pre><code class="language-{html.escape(code_lang)}">'
                + html.escape("\n".join(code_buf))
                + "</code></pre>"
            )
            continue
        if in_code:
            code_buf.append(line)
            continue
        hm = re.match(r"^##\s+(.*)$", line)
        if hm:
            out.append(f"<h2>{html.escape(hm.group(1))}</h2>")
            continue
        bm = re.match(r"^[-*]\s+(.*)$", line)
        if bm:
            body = html.escape(bm.group(1))
            body = re.sub(
                r"\*\*(.+?)\*\*", r"<strong>\1</strong>", body
            )
            body = re.sub(r"`(.+?)`", r"<code>\1</code>", body)
            out.append(f"<li>{body}</li>")
            continue
        if line.strip():
            out.append(f"<p>{html.escape(line.strip())}</p>")
    html_out = []
    in_list = False
    for chunk in out:
        if chunk.startswith("<li>") and not in_list:
            html_out.append("<ul>")
            in_list = True
        elif not chunk.startswith("<li>") and in_list:
            html_out.append("</ul>")
            in_list = False
        html_out.append(chunk)
    if in_list:
        html_out.append("</ul>")
    return "\n".join(html_out)
