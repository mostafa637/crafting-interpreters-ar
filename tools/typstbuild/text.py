"""Small string helpers, ported from ``tool/lib/src/text.dart``."""

from __future__ import annotations

import html
import re

#: Punctuation removed from file names and anchors. The Arabic marks have to
#: go too: a translated heading ends in ``؟`` or ``،`` and Typst rejects those
#: inside a label.
_PUNCTUATION = re.compile(r"""[,.?!:'"/()\u060c\u061b\u061f\u066a\u066b\u066c\u06d4]""")
_WHITESPACE = re.compile(r"\s+")

#: Characters that are markup in Typst and must be escaped in prose.
_TYPST_ESCAPE = re.compile(r"([\\#*_`$@<>~=\[\]()])")


def to_file_name(text: str) -> str:
    """Converts *text* to a string suitable for a file or anchor name."""
    if text == "Crafting Interpreters":
        return "index"
    if text == "Table of Contents":
        return "contents"

    # Hack: the introduction has a *subheader* named "Challenges" that is
    # distinct from the real "Challenges" section, so it needs its own anchor.
    if text == "Challenges":
        return "challenges_"

    return _PUNCTUATION.sub("", text.lower().replace(" ", "-"))


def roman(number: int) -> str:
    """Converts *number* to a (small) roman numeral, like the Dart original."""
    if number <= 3:
        return "I" * number
    if number == 4:
        return "IV"
    if number < 10:
        return "V" + "I" * (number - 5)
    raise ValueError(f"Can't convert {number} to Roman.")


def pluralize(sequence) -> str:
    return "" if len(sequence) == 1 else "s"


def pretty(text: str) -> str:
    """Use nicer entities for the handful of accented names in the book."""
    return (
        text.replace("à", "&agrave;")
        .replace("ï", "&iuml;")
        .replace("ø", "&oslash;")
        .replace("æ", "&aelig;")
    )


def unescape_entities(text: str) -> str:
    """Decodes the HTML entities that appear in the Markdown sources."""
    # Named entities used by the book that `html.unescape` already knows about,
    # plus a few HTML5 additions. `html.unescape` handles numeric escapes too.
    return html.unescape(text)


def escape_typst(text: str) -> str:
    """Escapes *text* so it is rendered literally by Typst markup."""
    return _TYPST_ESCAPE.sub(r"\\\1", text)


def escape_typst_string(text: str) -> str:
    """Escapes *text* so it can be embedded in a Typst string literal."""
    out = []
    for char in text:
        if char == "\\":
            out.append("\\\\")
        elif char == '"':
            out.append('\\"')
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "\t":
            out.append("\\t")
        else:
            out.append(char)
    return "".join(out)


def typst_string(text: str) -> str:
    """A quoted Typst string literal."""
    return '"' + escape_typst_string(text) + '"'


def word_count(text: str) -> int:
    return len(_WHITESPACE.split(text))
