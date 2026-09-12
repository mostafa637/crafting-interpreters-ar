"""Splits Java and C source files into snippet-tagged lines.

A port of ``tool/lib/src/source_file_parser.dart``.  The C and Java sources in
this repo are annotated with markers that say which chapter and snippet each
line belongs to, e.g.::

    //> Scanning lox-class
    public class Lox {
    //< Scanning lox-class

or, for a block comment::

    /* Scanning lox-class < Scan-token lox-class */

The parser also tracks the *location* of each line (which class/method it is
inside of) so the book can tell the reader where a snippet goes: "add after
main()", "in scanToken()", and so on.
"""

from __future__ import annotations

import re
from typing import Optional

from .model import Book, CodeTag, Location, Page, SourceFile, SourceLine

_BLOCK_PATTERN = re.compile(
    r"^/\* ([A-Z][A-Za-z\s]+) ([-a-z0-9]+) < ([A-Z][A-Za-z\s]+) ([-a-z0-9]+)$"
)
_BLOCK_SNIPPET_PATTERN = re.compile(r"^/\* < ([-a-z0-9]+)$")
_BEGIN_SNIPPET_PATTERN = re.compile(r"^//> ([-a-z0-9]+)$")
_END_SNIPPET_PATTERN = re.compile(r"^//< ([-a-z0-9]+)$")
_BEGIN_CHAPTER_PATTERN = re.compile(r"^//> ([A-Z][A-Za-z\s]+) ([-a-z0-9]+)$")
_END_CHAPTER_PATTERN = re.compile(r"^//< ([A-Z][A-Za-z\s]+) ([-a-z0-9]+)$")

#: Hacky regexes that match various declarations.
_CONSTRUCTOR_PATTERN = re.compile(r"^  ([A-Z][a-z]\w+)\(")
_FUNCTION_PATTERN = re.compile(r"(\w+)>*\*? (\w+)\(([^)]*)")
_VARIABLE_PATTERN = re.compile(r"^\w+\*? (\w+)(;| = )")
_STRUCT_PATTERN = re.compile(r"^struct (\w+)? \{$")
_TYPE_PATTERN = re.compile(r"(public )?(abstract )?(class|enum|interface) ([A-Z]\w+)")
_NAMED_TYPEDEF_PATTERN = re.compile(r"^typedef (enum|struct|union) (\w+) \{$")
_UNNAMED_TYPEDEF_PATTERN = re.compile(r"^typedef (enum|struct|union) \{$")
_TYPEDEF_NAME_PATTERN = re.compile(r"^\} (\w+);$")

#: Reserved words that can look like a return type in a function declaration
#: but shouldn't be treated as one.
_KEYWORDS = {"new", "return", "throw"}


class _ParseState:
    def __init__(self, start: Optional[CodeTag], end: Optional[CodeTag] = None):
        self.start = start
        self.end = end

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        if self.end is not None:
            return f"_ParseState({self.start} > {self.end})"
        return f"_ParseState({self.start})"


class SourceFileParser:
    def __init__(self, book: Book, path: str, relative: str):
        self._book = book
        self._file = SourceFile(path, relative)
        with open(path, "r", encoding="utf-8") as handle:
            self._lines = handle.read().split("\n")
        # `readAsLinesSync()` drops a trailing empty line from the final "\n".
        if self._lines and self._lines[-1] == "":
            self._lines.pop()

        self._states: list[_ParseState] = []
        self._unnamed_typedef: Optional[Location] = None
        self._location = Location(None, "file", self._file.nice_path)
        self._location_before_block: Optional[Location] = None

        # The root state is implicit: the Dart version starts with a state
        # whose startChapter is null, which `findCodeTag` on a null page
        # effectively answers with "not-yet".
        self._states.append(_ParseState(None, None))

    # -- API ---------------------------------------------------------------

    def parse(self) -> SourceFile:
        for index, raw_line in enumerate(self._lines):
            line = raw_line.rstrip()

            self._update_location_before(line, index)

            if not self._update_state(line):
                source_line = SourceLine(
                    line,
                    self._location,
                    self._current_state.start,
                    self._current_state.end,
                )
                self._file.lines.append(source_line)

            self._update_location_after(line)

        return self._file

    # -- Locating ----------------------------------------------------------

    @property
    def _current_state(self) -> _ParseState:
        return self._states[-1]

    def _update_location_before(self, line: str, line_index: int) -> None:
        # See if we reached a new function or method declaration.
        match = _FUNCTION_PATTERN.search(line)
        if match is not None and "#define" not in line and match.group(1) not in _KEYWORDS:
            # Hack: don't get caught by comments or string literals.
            if "//" not in line and '"' not in line:
                is_function_declaration = line.endswith(";")

                # Hack: handle multi-line declarations.
                if (
                    line.endswith(",")
                    and line_index + 1 < len(self._lines)
                    and self._lines[line_index + 1].rstrip().endswith(";")
                ):
                    is_function_declaration = True

                kind = "method" if self._file.language == "java" else "function"
                self._location = Location(
                    self._location,
                    kind,
                    match.group(2),
                    signature=match.group(3),
                    is_function_declaration=is_function_declaration,
                )
                return

        match = _CONSTRUCTOR_PATTERN.search(line)
        if match is not None:
            self._location = Location(self._location, "constructor", match.group(1))
            return

        match = _TYPE_PATTERN.search(line)
        if match is not None:
            # Hack: don't get caught by comments or string literals.
            if "//" not in line and '"' not in line:
                self._location = Location(
                    self._location, match.group(3), match.group(4)
                )
            return

        match = _STRUCT_PATTERN.search(line)
        if match is not None:
            self._location = Location(self._location, "struct", match.group(1))
            return

        match = _NAMED_TYPEDEF_PATTERN.search(line)
        if match is not None:
            self._location = Location(self._location, match.group(1), match.group(2))
            return

        match = _UNNAMED_TYPEDEF_PATTERN.search(line)
        if match is not None:
            # We don't know the name of the typedef yet.
            self._location = Location(self._location, match.group(1), None)
            self._unnamed_typedef = self._location
            return

        match = _VARIABLE_PATTERN.search(line)
        if match is not None:
            self._location = Location(self._location, "variable", match.group(1))
            return

    def _update_location_after(self, line: str) -> None:
        match = _TYPEDEF_NAME_PATTERN.search(line)
        if match is not None:
            # Now we know the typedef name.
            if self._unnamed_typedef is not None:
                self._unnamed_typedef.name = match.group(1)
                self._unnamed_typedef = None
            self._location = self._location.parent

        # Use `startswith` to include lines like "} [aside-marker]".
        if line.startswith("}"):
            self._location = self._location.pop_to_depth(0)
        elif line.startswith("  }"):
            self._location = self._location.pop_to_depth(1)
        elif line.startswith("    }"):
            self._location = self._location.pop_to_depth(2)

        # If we reached a function declaration, not a definition, then it's done
        # after one line.
        if self._location.is_function_declaration:
            self._location = self._location.parent

        # Module variables are only a single line.
        if self._location.kind == "variable":
            self._location = self._location.parent

        # Hack: there is a one-line class in Parser.java.
        if "class ParseError" in line:
            self._location = self._location.parent

    # -- State -------------------------------------------------------------

    def _update_state(self, line: str) -> bool:
        """Processes any line that changes which snippet we are inside of.

        Returns ``True`` if the line contained a snippet annotation.
        """
        match = _BLOCK_PATTERN.match(line)
        if match is not None:
            self._push(
                start_chapter=self._book.find_chapter(match.group(1)),
                start_name=match.group(2),
                end_chapter=self._book.find_chapter(match.group(3)),
                end_name=match.group(4),
            )
            self._location_before_block = self._location
            return True

        match = _BLOCK_SNIPPET_PATTERN.match(line)
        if match is not None:
            self._push(
                end_chapter=self._current_state.start.chapter
                if self._current_state.start is not None
                else None,
                end_name=match.group(1),
            )
            self._location_before_block = self._location
            return True

        if line.strip() == "*/" and self._current_state.end is not None:
            self._location = self._location_before_block
            self._pop()
            return True

        match = _BEGIN_SNIPPET_PATTERN.match(line)
        if match is not None:
            self._push(start_name=match.group(1))
            return True

        match = _END_SNIPPET_PATTERN.match(line)
        if match is not None:
            self._pop()
            return True

        match = _BEGIN_CHAPTER_PATTERN.match(line)
        if match is not None:
            self._push(
                start_chapter=self._book.find_chapter(match.group(1)),
                start_name=match.group(2),
            )
            return True

        match = _END_CHAPTER_PATTERN.match(line)
        if match is not None:
            self._pop()
            return True

        return False

    def _push(
        self,
        start_chapter: Optional[Page] = None,
        start_name: Optional[str] = None,
        end_chapter: Optional[Page] = None,
        end_name: Optional[str] = None,
    ) -> None:
        if start_chapter is None:
            start_chapter = (
                self._current_state.start.chapter
                if self._current_state.start is not None
                else None
            )

        start: Optional[CodeTag]
        if start_name is not None:
            if start_chapter is None:
                start = None
            else:
                start = start_chapter.find_code_tag(start_name)
        else:
            start = self._current_state.start

        end: Optional[CodeTag] = None
        if end_chapter is not None and end_name is not None:
            end = end_chapter.find_code_tag(end_name)

        self._states.append(_ParseState(start, end))

    def _pop(self) -> None:
        if len(self._states) > 1:
            self._states.pop()
