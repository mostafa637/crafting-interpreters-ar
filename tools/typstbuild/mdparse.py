"""Parses the book's Markdown into a small AST.

The book's Markdown is not plain CommonMark: it also embeds the ``^code``
directives, ``<aside>`` blocks for margin notes, ``<span name="...">`` anchors,
hand-written HTML tables and one hand-written highlighted snippet.  The Dart
build uses ``package:markdown`` plus custom `BlockSyntax`/`InlineSyntax`
subclasses (``tool/lib/src/markdown/``); this module does the same job with a
hand-written parser tuned to what actually appears in ``book/*.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Union

from .highlight import highlight
from .model import Book, Header, Page
from .text import unescape_entities

# ---------------------------------------------------------------------------
# Inline AST
# ---------------------------------------------------------------------------


@dataclass
class Text:
    value: str


@dataclass
class Emph:
    children: list["Inline"]


@dataclass
class Strong:
    children: list["Inline"]


@dataclass
class CodeSpan:
    value: str


@dataclass
class Link:
    children: list["Inline"]
    href: str


@dataclass
class Anchor:
    """``<span name="x">``: where a margin note is attached."""

    name: str


@dataclass
class ImageInline:
    """An ``<img>`` that appears inside a paragraph, e.g. the GC color dots."""

    src: str
    alt: str
    klass: str


@dataclass
class LineBreak:
    pass


@dataclass
class SmallCaps:
    value: str


@dataclass
class Cite:
    """``<cite>`` inside a chapter-opening block quote."""

    children: list["Inline"]


Inline = Union[
    Text, Emph, Strong, CodeSpan, Link, Anchor, LineBreak, SmallCaps, Cite, ImageInline
]


# ---------------------------------------------------------------------------
# Block AST
# ---------------------------------------------------------------------------


@dataclass
class Paragraph:
    inlines: list[Inline]


@dataclass
class Heading:
    level: int
    raw: str
    header: Optional[Header]
    inlines: list[Inline]


@dataclass
class SnippetBlock:
    name: str
    options: Optional[str]


@dataclass
class CodeFence:
    lang: str
    lines: list[str]
    indent: int = 0


@dataclass
class Aside:
    name: str
    blocks: list["Block"]
    #: The aside's CSS class. ``bottom`` hangs the note *up* from the line it
    #: annotates instead of down from it, which the long notes need.
    klass: str = ""


@dataclass
class Quote:
    blocks: list["Block"]


@dataclass
class ListBlock:
    ordered: bool
    #: One entry per item; each item is a list of blocks.
    items: list[list["Block"]]


@dataclass
class ImageBlock:
    src: str
    alt: str
    klass: str


@dataclass
class Table:
    header: list[list[Inline]]
    rows: list[list[list[Inline]]]


@dataclass
class Div:
    """A raw ``<div>`` marker in the Markdown, e.g. ``class="challenges"``."""

    klass: str
    closing: bool = False


@dataclass
class RawListing:
    """The hand-written highlighted snippet in ``introduction.md``."""

    file: Optional[str]
    change: list[tuple[str, str]]
    context_before: list[list[tuple[str, str]]]
    insert: list[list[tuple[str, str]]]
    context_after: list[list[tuple[str, str]]]


@dataclass
class HorizontalRule:
    pass


Block = Union[
    Paragraph,
    Heading,
    SnippetBlock,
    CodeFence,
    Aside,
    Quote,
    ListBlock,
    ImageBlock,
    Table,
    Div,
    RawListing,
    HorizontalRule,
]


# ---------------------------------------------------------------------------
# Inline parser
# ---------------------------------------------------------------------------

_INLINE_SPECIAL = re.compile(
    r"""(`|\*\*|\*|\[|<span\s+name="|</?em>|</?code>|</?strong>|<br\s*/?>|"""
    r"""<span\s+class="small-caps">|<span\s+class="ellipse">|<span\b[^>]*>|</span>|"""
    r"""<a\s+href="|</a>|<cite>|</cite>|<img\b|"""
    r"""&[a-zA-Z#][a-zA-Z0-9]*;)"""
)

#: Chicago-style ellipsis: the dots get more air than a Unicode ellipsis gives
#: them. This is what the Dart ``EllipseSyntax`` writes for the print format.
THIN_ELLIPSIS = "\u2009.\u2009.\u2009.\u2009"

_TAG_STRIP = re.compile(r"</?[a-zA-Z][^>]*>")


def _is_right_single(before: Optional[str], after: Optional[str]) -> bool:
    """Port of ``ApostropheSyntax._isRight``."""
    if before == " " and after is not None and after.isdigit():
        return True
    if before == "`" and after == "s":
        return True
    if before == " ":
        return False
    if before == "\n":
        return False
    return True


def _is_right_double(before: Optional[str], after: Optional[str]) -> bool:
    """Port of ``SmartQuoteSyntax._isRight``."""
    if after == " ":
        return True
    if before is not None and (before.isalnum()):
        return True
    if before is not None and before in ".?!":
        return True
    if after is not None and after in ":,.":
        return True
    return False


def smarten(text: str) -> str:
    """Applies the book's typographic tweaks to prose.

    Straight quotes become smart quotes, `` -- `` becomes an em dash and
    ``...`` becomes an ellipsis, exactly like the Dart inline syntaxes do.
    """
    # Em dash: the Dart rule consumes the spaces around " -- ".
    text = re.sub(r"\s--\s", "\u2014", text)
    text = text.replace("...", "\u2026")

    out = []
    for index, char in enumerate(text):
        before = text[index - 1] if index > 0 else None
        after = text[index + 1] if index < len(text) - 1 else None
        if char == "'":
            out.append("\u2019" if _is_right_single(before, after) else "\u2018")
        elif char == '"':
            out.append("\u201d" if _is_right_double(before, after) else "\u201c")
        else:
            out.append(char)
    return "".join(out)


def _matching_paren(text: str, start: int) -> int:
    """Returns the index of the ``)`` that closes the ``(`` before *start*.

    Markdown URLs may contain balanced parentheses (the MSDN links in the
    book do, e.g. ``...xe53dz5w(v=vs.100).aspx``), so the closing paren has
    to be found by counting rather than by a plain ``find``.
    """
    depth = 0
    for index in range(start - 1, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def parse_inlines(text: str) -> list[Inline]:
    """Parses a string of inline Markdown into inline nodes."""
    inlines: list[Inline] = []
    buffer = []

    def flush() -> None:
        if buffer:
            inlines.append(Text(smarten(unescape_entities("".join(buffer)))))
            buffer.clear()

    index = 0
    while index < len(text):
        match = _INLINE_SPECIAL.search(text, index)
        if match is None:
            buffer.append(text[index:])
            break

        start = match.start()
        token = match.group(0)
        if start > index:
            buffer.append(text[index:start])

        if token == "`":
            end = text.find("`", match.end())
            if end == -1:
                buffer.append(token)
                index = match.end()
                continue
            flush()
            inlines.append(CodeSpan(unescape_entities(text[match.end() : end])))
            index = end + 1

        elif token == "**":
            end = text.find("**", match.end())
            if end == -1:
                buffer.append(token)
                index = match.end()
                continue
            flush()
            inlines.append(Strong(parse_inlines(text[match.end() : end])))
            index = end + 2

        elif token == "*":
            end = text.find("*", match.end())
            if end == -1:
                buffer.append(token)
                index = match.end()
                continue
            flush()
            inlines.append(Emph(parse_inlines(text[match.end() : end])))
            index = end + 1

        elif token == "[":
            close = text.find("](", match.end())
            paren = _matching_paren(text, close + 2) if close != -1 else -1
            if close == -1 or paren == -1:
                buffer.append(token)
                index = match.end()
                continue
            flush()
            inlines.append(
                Link(
                    parse_inlines(text[match.end() : close]),
                    unescape_entities(text[close + 2 : paren]),
                )
            )
            index = paren + 1

        elif token.startswith("<img"):
            end = text.find(">", match.end())
            if end == -1:
                index = match.end()
                continue
            attributes = _parse_image_attributes(text[start : end + 1])
            if attributes is None:
                index = end + 1
                continue
            flush()
            inlines.append(
                ImageInline(
                    attributes["src"],
                    unescape_entities(attributes.get("alt", "")),
                    attributes.get("class", ""),
                )
            )
            index = end + 1

        elif token.startswith('<span name="'):
            end = text.find('">', match.end())
            name = text[match.end() : end] if end != -1 else ""
            flush()
            inlines.append(Anchor(name))
            index = end + 2 if end != -1 else match.end()

        elif token.startswith('<span class="small-caps"'):
            end = text.find("</span>", match.end())
            value = text[match.end() : end] if end != -1 else ""
            flush()
            inlines.append(SmallCaps(unescape_entities(value)))
            index = end + len("</span>") if end != -1 else match.end()

        elif token.startswith('<span class="ellipse"'):
            # A hand-written Chicago-style ellipsis, inside the HTML tables.
            end = text.find("</span>", match.end())
            flush()
            inlines.append(Text(THIN_ELLIPSIS))
            index = end + len("</span>") if end != -1 else match.end()

        elif token in ("<em>", "<code>", "<strong>") or token.startswith("<span"):
            # Inline HTML emphasis/code: treat the tag as a delimiter.
            closing = {"<em>": "</em>", "<code>": "</code>", "<strong>": "</strong>"}.get(token)
            if closing is not None:
                end = text.find(closing, match.end())
                if end != -1:
                    flush()
                    inner = parse_inlines(text[match.end() : end])
                    if token == "<em>":
                        inlines.append(Emph(inner))
                    elif token == "<strong>":
                        inlines.append(Strong(inner))
                    else:
                        inlines.append(CodeSpan(unescape_entities(text[match.end() : end])))
                    index = end + len(closing)
                    continue
            # A bare <span> or an unknown tag: drop it.
            index = match.end()

        elif token in ("</em>", "</code>", "</strong>", "</span>", "</a>"):
            index = match.end()

        elif token == "<cite>":
            end = text.find("</cite>", match.end())
            if end == -1:
                index = match.end()
                continue
            flush()
            inlines.append(Cite(parse_inlines(text[match.end() : end])))
            index = end + len("</cite>")

        elif token == "</cite>":
            index = match.end()

        elif token.startswith("<br"):
            flush()
            inlines.append(LineBreak())
            index = match.end()

        elif token.startswith("<a href="):
            end_quote = text.find('"', match.end())
            end_tag = text.find(">", end_quote)
            close = text.find("</a>", end_tag)
            if end_quote == -1 or end_tag == -1 or close == -1:
                index = match.end()
                continue
            flush()
            inlines.append(
                Link(
                    parse_inlines(text[end_tag + 1 : close]),
                    text[match.end() : end_quote],
                )
            )
            index = close + len("</a>")

        else:
            # An entity like &mdash; or &#8209;.
            buffer.append(token)
            index = match.end()

    flush()
    return inlines


def strip_html_tags(text: str) -> str:
    return _TAG_STRIP.sub("", text)


# ---------------------------------------------------------------------------
# Block parser
# ---------------------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,3}) (.*)$")
_FENCE = re.compile(r"^(\s*)```(.*)$")
_CODE_DIRECTIVE = re.compile(r"^\^code ([-a-z0-9]+)( \(([^)]+)\))?$")
_LIST_ITEM = re.compile(r"^(\s*)(\*|-|\d+\.)\s+(.*)$")
_ASIDE_OPEN = re.compile(r"^<aside\b([^>]*)>\s*$")
_DIV = re.compile(r'^</?div(?: class="([^"]+)")?>\s*$')
#: The duplicate of a snippet's "file, in method()" line that the web layout
#: shows on narrow screens. The book has one layout, so it is redundant here.
_SOURCE_FILE_NARROW = re.compile(r'^<div class="source-file-narrow">')


def _attributes(text: str) -> dict[str, str]:
    """The attributes of an HTML tag, whichever order they are written in."""
    attributes: dict[str, str] = {}
    for attribute in _ATTRIBUTE.finditer(text):
        value = attribute.group(2) if attribute.group(2) is not None else attribute.group(3)
        attributes[attribute.group(1)] = value
    return attributes
_IMAGE = re.compile(r"^<img\b([^>]*?)/?>\s*$")
_ATTRIBUTE = re.compile(r"""([A-Za-z-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")


def _parse_image_attributes(text: str) -> Optional[dict[str, str]]:
    """Pulls the attributes out of an ``<img ... />`` tag.

    The book's Markdown writes the attributes in whatever order it likes
    (``class`` sometimes comes first) and wraps long tags over several lines,
    which :func:`join_image_tags` has already taken care of.
    """
    match = _IMAGE.match(text.strip())
    if match is None:
        return None

    attributes: dict[str, str] = {}
    for attribute in _ATTRIBUTE.finditer(match.group(1)):
        value = attribute.group(2) if attribute.group(2) is not None else attribute.group(3)
        attributes[attribute.group(1)] = value
    if "src" not in attributes:
        return None
    return attributes


def _image_node(attributes: dict[str, str]) -> ImageBlock:
    return ImageBlock(
        attributes["src"],
        unescape_entities(attributes.get("alt", "")),
        attributes.get("class", ""),
    )
_TABLE_ROW = re.compile(r"^\s*<tr>\s*$")
_TABLE_CELL = re.compile(r"^\s*<td>(.*)</td>\s*$")
_PRE_CELL = re.compile(r"^\s*<pre[^>]*>(.*)</pre>\s*$")

#: Lines that start a new block, so a paragraph has to end before them.
_BLOCK_START = re.compile(
    r"^(#{1,3} |\^code |```|<aside |</aside>|<div|</div>|<table>|</table>|<img |<tr>|<td>|>|"
    r"\* |- |\d+\. |<pre)"
)


def _unclosed_image(line: str) -> bool:
    start = line.find("<img")
    return start != -1 and ">" not in line[start:]


def join_image_tags(lines: list[str]) -> list[str]:
    """Glues ``<img>`` tags that the Markdown wraps over several lines.

    The long ``alt`` texts in the bytecode chapters push those tags over two
    or three lines, which would otherwise leave the tag inside a paragraph and
    the image unrendered.
    """
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if _unclosed_image(line):
            parts = [line]
            while index < len(lines) and _unclosed_image(" ".join(parts)):
                parts.append(lines[index].strip())
                index += 1
            line = re.sub(r"\s+", " ", " ".join(parts)).strip()
        out.append(line)
    return out


class MarkdownParser:
    def __init__(self, book: Book, page: Page):
        self.book = book
        self.page = page

    # -- Entry point -------------------------------------------------------

    def parse(self, lines: list[str]) -> list[Block]:
        blocks, _ = self._parse_blocks(join_image_tags(lines))
        return blocks

    def _parse_blocks(self, lines: list[str]) -> tuple[list[Block], int]:
        blocks: list[Block] = []
        index = 0

        while index < len(lines):
            line = lines[index]

            if not line.strip():
                index += 1
                continue

            # ^code directives.
            match = _CODE_DIRECTIVE.match(line)
            if match is not None:
                blocks.append(SnippetBlock(match.group(1), match.group(3)))
                index += 1
                continue

            # <aside name="x"> ... </aside>, sometimes with a class.
            match = _ASIDE_OPEN.match(line)
            if match is not None:
                attributes = _attributes(match.group(1))
                inner, index = self._collect_until(lines, index + 1, "</aside>")
                blocks.append(
                    Aside(
                        attributes.get("name", ""),
                        self.parse(inner),
                        attributes.get("class", ""),
                    )
                )
                continue

            # Raw <div> markers.
            match = _DIV.match(line)
            if match is not None:
                blocks.append(
                    Div(match.group(1) or "", closing=line.startswith("</"))
                )
                index += 1
                continue

            # The narrow-screen copy of a snippet's source line.
            if _SOURCE_FILE_NARROW.match(line):
                while index < len(lines) and "</div>" not in lines[index]:
                    index += 1
                index += 1
                continue

            # The hand-written highlighted snippet in introduction.md.
            if line.startswith('<div class="codehilite">'):
                raw = [line]
                depth = line.count("<div")
                index += 1
                while index < len(lines):
                    raw.append(lines[index])
                    depth += lines[index].count("<div")
                    depth -= lines[index].count("</div>")
                    done = lines[index].rstrip().endswith("</div>") and depth <= 0
                    index += 1
                    if done:
                        break
                blocks.extend(_parse_raw_listing(raw))
                continue

            # HTML tables.
            if line.strip() == "<table>":
                inner, index = self._collect_until(lines, index + 1, "</table>")
                table = _parse_table(inner)
                if table is not None:
                    blocks.append(table)
                continue

            # Images.
            attributes = _parse_image_attributes(line)
            if attributes is not None:
                blocks.append(_image_node(attributes))
                index += 1
                continue

            # Fenced code.
            match = _FENCE.match(line)
            if match is not None:
                indent = len(match.group(1))
                lang = match.group(2).strip()
                body: list[str] = []
                index += 1
                while index < len(lines):
                    if _FENCE.match(lines[index]) is not None:
                        index += 1
                        break
                    body.append(lines[index])
                    index += 1
                blocks.append(CodeFence(lang, body, indent))
                continue

            # Headings.
            match = _HEADING.match(line)
            if match is not None:
                level = len(match.group(1))
                raw = line
                header = self.page.headers.get(raw)
                blocks.append(Heading(level, raw, header, parse_inlines(match.group(2))))
                index += 1
                continue

            if line.strip() == "---":
                blocks.append(HorizontalRule())
                index += 1
                continue

            # Block quotes.
            if line.startswith(">"):
                quote_lines: list[str] = []
                while index < len(lines) and lines[index].startswith(">"):
                    quote_lines.append(lines[index][1:].lstrip())
                    index += 1
                blocks.append(Quote(self.parse(quote_lines)))
                continue

            # Lists.
            match = _LIST_ITEM.match(line)
            if match is not None:
                block, index = self._parse_list(lines, index)
                blocks.append(block)
                continue

            # Otherwise, a paragraph.
            paragraph_lines = [line]
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if not candidate.strip():
                    break
                if _BLOCK_START.match(candidate):
                    break
                paragraph_lines.append(candidate)
                index += 1
            blocks.append(Paragraph(parse_inlines(" ".join(paragraph_lines))))

        return blocks, index

    # -- Helpers -----------------------------------------------------------

    def _collect_until(
        self, lines: list[str], index: int, terminator: str
    ) -> tuple[list[str], int]:
        collected: list[str] = []
        while index < len(lines):
            if lines[index].strip() == terminator:
                index += 1
                break
            collected.append(lines[index])
            index += 1
        return collected, index

    def _parse_list(self, lines: list[str], index: int) -> tuple[ListBlock, int]:
        first = _LIST_ITEM.match(lines[index])
        assert first is not None
        base_indent = len(first.group(1))
        ordered = first.group(2) not in ("*", "-")

        items: list[list[Block]] = []
        current: list[str] = []

        while index < len(lines):
            line = lines[index]
            match = _LIST_ITEM.match(line)

            if match is not None and len(match.group(1)) <= base_indent:
                if current:
                    items.append(self.parse(current))
                current = [match.group(3)]
                index += 1
                continue

            if not line.strip():
                # A blank line ends the list unless the next line is indented
                # enough to still belong to this item.
                lookahead = index + 1
                while lookahead < len(lines) and not lines[lookahead].strip():
                    lookahead += 1
                if lookahead >= len(lines):
                    index = lookahead
                    break
                next_match = _LIST_ITEM.match(lines[lookahead])
                if next_match is not None and len(next_match.group(1)) <= base_indent:
                    index = lookahead
                    continue
                indent = len(lines[lookahead]) - len(lines[lookahead].lstrip())
                if indent <= base_indent and not lines[lookahead].startswith(" " * (base_indent + 1)):
                    index = lookahead
                    break
                current.append("")
                index += 1
                continue

            # A continuation line: strip the item's indentation.
            stripped = line[base_indent + 4 :] if len(line) > base_indent + 4 else line.strip()
            current.append(stripped)
            index += 1

        if current:
            items.append(self.parse(current))

        return ListBlock(ordered, items), index


# ---------------------------------------------------------------------------
# HTML tables and the hand-written snippet
# ---------------------------------------------------------------------------

_HIGHLIGHT_SPAN = re.compile(r'<span class="([a-z]+)">(.*?)</span>', re.S)


def _runs_from_html(html_text: str) -> list[tuple[str, str]]:
    runs: list[tuple[str, str]] = []
    index = 0
    for match in _HIGHLIGHT_SPAN.finditer(html_text):
        if match.start() > index:
            runs.append(("", unescape_entities(html_text[index : match.start()])))
        runs.append((match.group(1), unescape_entities(match.group(2))))
        index = match.end()
    if index < len(html_text):
        runs.append(("", unescape_entities(html_text[index:])))
    return [run for run in runs if run[1]]


#: Lines that begin a new row or cell in the book's hand-written tables.
_TABLE_TAG = re.compile(r"^</?(?:thead|tbody|tr|td|pre)\b")


def _join_table_lines(lines: list[str]) -> list[str]:
    """Folds the continuation lines of a multi-line ``<td>`` into their cell.

    The precedence table in "Parsing Expressions" wraps one cell over two
    lines, which would otherwise shift every cell after it by one column.
    """
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if (
            out
            and stripped
            and not _TABLE_TAG.match(stripped)
            and not stripped.startswith("</")
        ):
            out[-1] = out[-1] + " " + stripped
            continue
        out.append(stripped)
    return out


def _parse_table(lines: list[str]) -> Optional[Table]:
    header: list[list[Inline]] = []
    rows: list[list[list[Inline]]] = []
    in_header = False
    in_body = False

    for line in _join_table_lines(lines):
        stripped = line.strip()
        if stripped == "<thead>":
            in_header = True
            continue
        if stripped == "</thead>":
            in_header = False
            continue
        if stripped == "<tbody>":
            in_body = True
            continue
        if stripped == "</tbody>":
            in_body = False
            continue
        if stripped in ("<tr>", "</tr>"):
            continue

        match = _TABLE_CELL.match(line)
        if match is None:
            # A <pre> block inside a cell (used by the Optimization table).
            match = _PRE_CELL.match(line)
            if match is None:
                continue
            cell: list[Inline] = [CodeSpan(strip_html_tags(unescape_entities(match.group(1))))]
        else:
            cell = parse_inlines(match.group(1))

        if in_header:
            header.append(cell)
        elif in_body:
            if not rows or len(rows[-1]) >= len(header or [None] * 100):
                rows.append([])
            rows[-1].append(cell)
        else:
            rows.append([cell])

    return Table(header, rows)


def _parse_raw_listing(raw: list[str]) -> list[Block]:
    """Parses the hand-written ``<div class="codehilite">`` in introduction.md."""
    text = "\n".join(raw)

    def section(pattern: str) -> list[str]:
        match = re.search(pattern, text, re.S)
        if match is None:
            return []
        return [line for line in match.group(1).split("\n") if line.strip()]

    file_match = re.search(r"<div class=\"source-file\">(.*?)</div>", text, re.S)
    file_name: Optional[str] = None
    change: list[tuple[str, str]] = []
    if file_match is not None:
        block = file_match.group(1)
        lines = [line.strip() for line in block.split("<br>") if line.strip()]
        if lines:
            file_name = strip_html_tags(unescape_entities(lines[0]))
            for line in lines[1:]:
                # "in <em>scanToken</em>()" and friends. The <br> between the
                # lines of the caption reads as a comma in the book.
                if change:
                    change.append(("text", ", "))
                for part in re.split(r"(<em>.*?</em>)", line):
                    if part.startswith("<em>"):
                        change.append(("em", strip_html_tags(part)))
                    elif strip_html_tags(part).strip():
                        change.append(("text", unescape_entities(strip_html_tags(part))))

    before = section(r'<pre class="insert-before">(.*?)</pre>')
    insert = section(r'<pre class="insert">(.*?)</pre>')
    after = section(r'<pre class="insert-after">(.*?)</pre>')

    return [
        RawListing(
            file=file_name,
            change=change,
            context_before=[_runs_from_html(line) for line in before],
            insert=[_runs_from_html(line) for line in insert],
            context_after=[_runs_from_html(line) for line in after],
        )
    ]
