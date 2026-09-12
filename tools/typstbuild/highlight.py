"""The book's own syntax highlighter.

A port of ``tool/lib/src/syntax/{rule,language,grammar,highlighter}.dart``.

The output is a list of lines, each a list of ``(token_type, text)`` runs.
Token types are the same single letters the book's CSS uses::

    k  keyword            n  number          s  string
    e  string escape      c  comment         a  preprocessor / annotation
    i  identifier         t  type name       '' plain text

Porting the highlighter (instead of leaning on Typst's own ``raw``
highlighting) matters for two reasons: the snippets are fragments, not complete
compilable files, and the book colours them with its own rules; and the emitter
needs per-line control so it can dim context lines and attach margin notes to
individual lines.
"""

from __future__ import annotations

import re
from typing import Optional

Token = tuple[str, str]


class Rule:
    """A single regex rule that colors the whole match.

    (In the Dart original this is the ``Rule`` factory that returns a
    ``SimpleRule``.)
    """

    def __init__(self, pattern: str, token_type: str):
        self.pattern = re.compile(pattern)
        self.token_type = token_type

    def apply(self, highlighter: "Highlighter") -> bool:
        match = self.pattern.match(highlighter.text, highlighter.position)
        if match is None:
            return False
        highlighter.last_match = match
        highlighter.position = match.end()
        self.apply_rule(highlighter)
        return True

    def apply_rule(self, highlighter: "Highlighter") -> None:
        assert highlighter.last_match is not None
        highlighter.write_token(self.token_type, highlighter.last_match.group(0))


#: The Dart name for the plain regex rule.
SimpleRule = Rule


class CaptureRule(Rule):
    """A rule where each capture group has a corresponding token type."""

    def __init__(self, pattern: str, token_types: list[str]):
        super().__init__(pattern, "")
        self.token_types = token_types

    def apply_rule(self, highlighter: "Highlighter") -> None:
        assert highlighter.last_match is not None
        match = highlighter.last_match
        for i, token_type in enumerate(self.token_types):
            text = match.group(i + 1) or ""
            if token_type:
                highlighter.write_token(token_type, text)
            else:
                highlighter.write_text(text)


class StringRule(Rule):
    """Parses string literals and the escape codes inside them."""

    _ESCAPE_PATTERN = re.compile(r"\\.")

    def __init__(self):
        super().__init__('"', "s")

    def apply_rule(self, highlighter: "Highlighter") -> None:
        start = highlighter.position - 1
        text = highlighter.text
        position = highlighter.position

        while position < len(text):
            match = self._ESCAPE_PATTERN.match(text, position)
            if match is not None:
                position = match.end()
                if position > start:
                    highlighter.write_token("s", text[start : position - 2])
                highlighter.write_token("e", text[position - 2 : position])
                start = position
                continue

            if text[position] == '"':
                position += 1
                highlighter.write_token("s", text[start : position])
                highlighter.position = position
                return

            position += 1

        # Error: unterminated string.
        highlighter.write_token("err", text[start:position])
        highlighter.position = position


class IdentifierRule(Rule):
    """Parses an identifier and resolves keywords for their token type."""

    def __init__(self):
        super().__init__(r"[a-zA-Z_][a-zA-Z0-9_]*", "i")

    def apply_rule(self, highlighter: "Highlighter") -> None:
        assert highlighter.last_match is not None
        identifier = highlighter.last_match.group(0)
        token_type = highlighter.words.get(identifier, "i")
        highlighter.write_token(token_type, identifier)


class Language:
    def __init__(self, keywords: str = "", types: str = "", rules: Optional[list[Rule]] = None):
        self.words: dict[str, str] = {}
        for word in keywords.split():
            self.words[word] = "k"
        for word in types.split():
            self.words[word] = "t"
        self.rules: list[Rule] = rules or []


_C_KEYWORDS = (
    "break case const continue default do else enum extern false for goto if "
    "inline return sizeof static struct switch true typedef union while"
)

_CHARACTER_RULE = Rule(r"'\\?.'", "s")

_COMMON_RULES: list[Rule] = [
    StringRule(),
    Rule(r"[0-9]+\.[0-9]+f?", "n"),  # Float.
    Rule(r"0x[0-9a-fA-F]+", "n"),  # Hex integer.
    Rule(r"[0-9]+[Lu]?", "n"),  # Integer.
    Rule(r"//.*", "c"),  # Line comment.
    Rule(r"[A-Z][A-Za-z0-9_]*", "t"),  # Capitalized type name.
    IdentifierRule(),  # Other identifiers or keywords.
]

_C_RULES: list[Rule] = [
    CaptureRule(r"(#.*?)(//.*)", ["a", "c"]),  # Preprocessor with comment.
    Rule(r"#.*", "a"),  # Preprocessor.
    Rule(r"[A-Z][A-Z0-9_]+", "a"),  # ALL_CAPS preprocessor macro use.
    *_COMMON_RULES,
    _CHARACTER_RULE,
]

_JAVA_RULES: list[Rule] = [
    CaptureRule(r"(import)(\s+)(\w+(?:\.\w+)*)(;)", ["k", "", "i", ""]),
    CaptureRule(r"(import\s+static?)(\s+)(\w+(?:\.\w+)*(?:\.\*)?)(;)", ["k", "", "i", ""]),
    CaptureRule(r"(package)(\s+)(\w+(?:\.\w+)*)(;)", ["k", "", "i", ""]),
    Rule(r"@[a-zA-Z_][a-zA-Z0-9_]*", "a"),  # Annotation.
    Rule(r"[A-Z][A-Z0-9_]+\b", "i"),  # ALL_CAPS constant names.
    *_COMMON_RULES,
    _CHARACTER_RULE,
]

LANGUAGES: dict[str, Language] = {
    "c": Language(keywords=_C_KEYWORDS, types="bool char double FILE int size_t uint16_t uint32_t uint64_t uint8_t uintptr_t va_list void", rules=_C_RULES),
    "c++": Language(keywords=_C_KEYWORDS, types="vector string", rules=_C_RULES),
    "ebnf": Language(rules=[Rule(r"[A-Z][A-Z0-9_]+", "t"), *_COMMON_RULES]),
    "java": Language(
        keywords=(
            "abstract assert break case catch class const continue default do "
            "else enum extends false final finally for goto if implements import "
            "instanceof interface native new null package private protected public "
            "return static strictfp super switch synchronized this throw throws "
            "transient true try volatile while"
        ),
        types="boolean byte char double float int long short void",
        rules=_JAVA_RULES,
    ),
    "js": Language(
        keywords=(
            "break case catch class const continue debugger default delete do "
            "else export extends finally for function if import in instanceof let "
            "new return super switch this throw try typeof var void while with yield"
        ),
        rules=_COMMON_RULES,
    ),
    "lisp": Language(rules=[Rule(r"[a-zA-Z0-9_-]+", "i")]),
    "lox": Language(
        keywords="and class else false fun for if nil or print return super this true var while",
        rules=_COMMON_RULES,
    ),
    "lua": Language(rules=_COMMON_RULES),
    "python": Language(
        keywords=(
            "and as assert break class continue def del elif else except exec "
            "finally for from global if import in is lambda not or pass print "
            "raise range return try while with yield"
        ),
        rules=_COMMON_RULES,
    ),
    "ruby": Language(
        keywords=(
            "__LINE__ _ENCODING__ __FILE__ BEGIN END alias and begin break case "
            "class def defined? do else elsif end ensure false for if in lambda "
            "module next nil not or redo rescue retry return self super then true "
            "undef unless until when while yield"
        ),
        rules=_COMMON_RULES,
    ),
}


class Highlighter:
    def __init__(self, language: str):
        if language not in LANGUAGES:
            raise ValueError(f"Unknown language '{language}'.")
        self.language = LANGUAGES[language]
        self.words = self.language.words
        self.text = ""
        self.position = 0
        self.last_match: Optional[re.Match] = None
        self.runs: list[Token] = []
        self._in_macro = False

    def _write_char(self, char: str) -> None:
        self._append("", char)

    def _append(self, token_type: str, text: str) -> None:
        if not text:
            return
        if self.runs and self.runs[-1][0] == token_type:
            self.runs[-1] = (token_type, self.runs[-1][1] + text)
        else:
            self.runs.append((token_type, text))

    def write_token(self, token_type: str, text: Optional[str] = None) -> None:
        if text is None:
            assert self.last_match is not None
            text = self.last_match.group(0)
        self._append(token_type, text)

    def write_text(self, text: str) -> None:
        self._append("", text)

    def scan_line(self, line: str, indent: int) -> list[Token]:
        self.runs = []
        self.position = 0
        self.last_match = None

        if line.strip() == "":
            return []

        # If the entire code block is indented, remove that indentation.
        if len(line) > indent:
            line = line[indent:]

        self.text = line

        # Hackish: if the line ends with a backslash, it is a multi-line macro
        # definition, and we want to highlight subsequent lines like
        # preprocessor code too.
        if self.language is LANGUAGES["c"] and line.endswith("\\"):
            self._in_macro = True

        if self._in_macro:
            self.write_token("a", line)
        else:
            while self.position < len(line):
                found = False
                for rule in self.language.rules:
                    if rule.apply(self):
                        found = True
                        break
                if not found:
                    self._write_char(line[self.position])
                    self.position += 1

        if self._in_macro and not line.endswith("\\"):
            self._in_macro = False

        return self.runs


def highlight(language: str, lines: list[str], indent: int = 0) -> list[list[Token]]:
    """Highlights *lines* of *language*, returning one run list per line."""
    highlighter = Highlighter(language)
    return [highlighter.scan_line(line, indent) for line in lines]


def strip_aside_marker(line: str) -> tuple[str, Optional[str]]:
    """Splits a ``// [aside-name]`` comment marker off a line of code.

    Returns ``(code, aside_name)`` where the marker (if any) has been removed
    from the code, exactly like ``build.dart`` does for the HTML output.
    """
    match = re.search(r" ?// \[([-a-z0-9]+)\] *$", line)
    if match is not None:
        return line[: match.start()], match.group(1)

    match = re.search(r" ?// (.+) \[([-a-z0-9]+)\] *$", line)
    if match is not None:
        return line[: match.start()], match.group(2)

    return line, None
