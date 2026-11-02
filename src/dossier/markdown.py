"""Tiny, safe Markdown → HTML renderer for the dossier subset (no dependencies).

Supports headings, paragraphs, lists incl. task boxes, blockquotes, pipe tables, fenced code,
**bold**, *italic*, _italic_, `code`, [links](https://…) and bare https:// URLs. All text is
HTML-escaped first; only http(s) links are emitted.
"""

from __future__ import annotations

import re
from html import escape

_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BARE = re.compile(r"(?<![\"=>])(https?://[^\s<)]+)")


def _inline(text: str) -> str:
    s = escape(text, quote=False)
    links: list[str] = []

    def keep(html: str) -> str:
        links.append(html)
        return f"\x00{len(links) - 1}\x00"

    # text is already HTML-escaped (& → &amp;); only quotes still need escaping inside href
    attr = lambda u: u.replace('"', "&quot;")  # noqa: E731
    s = _LINK.sub(lambda m: keep(f'<a href="{attr(m.group(2))}" target="_blank" '
                                 f'rel="noopener">{m.group(1)}</a>'), s)
    s = _BARE.sub(lambda m: keep(f'<a href="{attr(m.group(1))}" target="_blank" '
                                 f'rel="noopener">{m.group(1)}</a>'), s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<![\w])_([^_\n]+)_(?![\w])", r"<em>\1</em>", s)
    return re.sub(r"\x00(\d+)\x00", lambda m: links[int(m.group(1))], s)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def render_markdown(md: str) -> str:
    out: list[str] = []
    lines = md.splitlines()
    i = 0
    para: list[str] = []

    def flush_para():
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            flush_para()
            i += 1
            continue
        if stripped.startswith("```"):
            flush_para()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            out.append("<pre><code>" + escape("\n".join(code)) + "</code></pre>")
            i += 1
            continue
        m = re.match(r"(#{1,4})\s+(.*)", stripped)
        if m:
            flush_para()
            n = len(m.group(1))
            out.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\|?[\s:-]+\|", lines[i + 1].strip()):
            flush_para()
            head = _cells(stripped)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            html = "<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
            for r in rows:
                html += "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
            out.append(html + "</tbody></table>")
            continue
        if stripped.startswith(">"):
            flush_para()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote>" + _inline(" ".join(quote)) + "</blockquote>")
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", line):
            flush_para()
            ordered = bool(re.match(r"^\s*\d+\.", line))
            items = []
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                text = re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i])
                nested = lines[i].startswith("  ")
                box = re.match(r"\[( |x)\]\s+(.*)", text)
                if box:
                    checked = " checked" if box.group(1) == "x" else ""
                    item = f'<input type="checkbox" disabled{checked}> {_inline(box.group(2))}'
                else:
                    item = _inline(text)
                items.append(f'<li class="nested">{item}</li>' if nested else f"<li>{item}</li>")
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        para.append(stripped)
        i += 1
    flush_para()
    return "\n".join(out)
