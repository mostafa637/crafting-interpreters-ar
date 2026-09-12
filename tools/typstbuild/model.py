"""The book model: locations, code tags, snippets, source files and pages.

This is a faithful port of the Dart classes in ``tool/lib/src/``:
``location.dart``, ``code_tag.dart``, ``snippet.dart``, ``page.dart`` and
``book.dart``.  Keeping the same shape matters: the snippet machinery is what
decides which lines of ``java/`` and ``c/`` end up in each ``^code`` block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .text import pluralize, roman, to_file_name

# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

#: A run of location text. ``kind`` is ``"text"`` or ``"em"`` (emphasized).
Run = tuple[str, str]


class Location:
    """The context in which a line of code appears: the chain of types and
    functions that contain it."""

    def __init__(
        self,
        parent: Optional["Location"],
        kind: str,
        name: Optional[str],
        signature: Optional[str] = None,
        is_function_declaration: bool = False,
    ):
        self.parent = parent
        self.kind = kind
        self._name = name
        self.signature = signature
        self.is_function_declaration = is_function_declaration

    @property
    def name(self) -> Optional[str]:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        # Can only set the name of an unnamed typedef.
        assert self._name is None
        self._name = value

    @property
    def is_file(self) -> bool:
        return self.kind == "file"

    @property
    def is_function(self) -> bool:
        return self.kind in {"constructor", "function", "method"}

    @property
    def depth(self) -> int:
        result = 0
        current: Optional[Location] = self
        while current is not None:
            result += 1
            current = current.parent
        return result

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        result = f"{self.kind} {self.name}"
        if self.signature is not None:
            result += f"({self.signature})"
        if self.parent is not None:
            result = f"{self.parent!r} > {result}"
        return result

    def __eq__(self, other: object) -> bool:
        # Note: the signature is deliberately not part of equality, matching
        # the Dart original.
        return (
            isinstance(other, Location)
            and self.kind == other.kind
            and self.name == other.name
        )

    def __hash__(self) -> int:
        return hash(self.kind) ^ hash(self.name)

    def pop_to_depth(self, depth: int) -> "Location":
        """Discard as many children as needed to get to *depth* parents."""
        locations = []
        current: Optional[Location] = self
        while current is not None:
            locations.append(current)
            current = current.parent

        # If we are already shallower, there is nothing to pop.
        if len(locations) < depth + 1:
            return self

        return locations[len(locations) - depth - 1]

    # -- Rendering ---------------------------------------------------------

    def to_runs(
        self, preceding: Optional["Location"], removed: list[str]
    ) -> Optional[list[Run]]:
        """Describes a snippet at this location, when it follows *preceding*.

        This is a port of ``Location.toHtml()`` but returns runs instead of
        HTML text.
        """
        if self.kind == "new":
            return [("text", "create new file")]
        if self.kind == "top":
            return [("text", "add to top of file")]

        # Note: the order of these is highly significant.
        if self.kind == "class" and preceding is not None and preceding.kind == "class":
            return [
                ("text", "nest inside class "),
                ("em", preceding.name or ""),
            ]

        if self.is_function and preceding == self:
            # Hack: there's one place where we add a new overload and that
            # shouldn't be treated as being in the same function.
            if self.name == "resolve" and self.signature == "Expr expr":
                return [
                    ("text", "add after "),
                    ("em", f"{preceding.name}({preceding.signature})"),
                ]

            return [("text", "in "), ("em", f"{self.name}()")]

        if self.is_function and removed:
            # Hack: we don't appear to be in the middle of a function, but we
            # are replacing lines, so assume we're replacing the whole function.
            return [("text", f"{self.kind} "), ("em", f"{self.name}()")]

        if preceding is not None and self.parent is preceding and not preceding.is_file:
            return [
                ("text", f"in {preceding.kind} "),
                ("em", preceding.name or ""),
            ]

        if preceding == self and not self.is_file:
            return [("text", f"in {self.kind} "), ("em", self.name or "")]

        if preceding is not None and preceding.is_function:
            return [("text", "add after "), ("em", f"{preceding.name}()")]

        if preceding is not None and not preceding.is_file:
            return [
                ("text", f"add after {preceding.kind} "),
                ("em", preceding.name or ""),
            ]

        # If we get here, there isn't a useful location to show. The snippet
        # will have enough surrounding context to make it clear.
        return None


# ---------------------------------------------------------------------------
# Code tags
# ---------------------------------------------------------------------------


class CodeTag:
    """A named location in a chapter's Markdown where a code snippet appears."""

    def __init__(
        self,
        chapter: "Page",
        name: str,
        index: int,
        before_count: int = 0,
        after_count: int = 0,
        show_location: bool = True,
    ):
        # Hackish: "not-yet" is always the last tag, even if it appears before
        # a real tag. That ensures we can push it for other tags.
        if name == "not-yet":
            index = 9999

        self.chapter = chapter
        self.name = name
        self.index = index
        self.before_count = before_count
        self.after_count = after_count
        self.show_location = show_location

    @property
    def key(self) -> tuple[int, int]:
        return (self.chapter.ordinal, self.index)

    def __lt__(self, other: "CodeTag") -> bool:
        return self.key < other.key

    def __le__(self, other: "CodeTag") -> bool:
        return self.key <= other.key

    def __gt__(self, other: "CodeTag") -> bool:
        return self.key > other.key

    def __ge__(self, other: "CodeTag") -> bool:
        return self.key >= other.key

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, CodeTag)
            and self.chapter.ordinal == other.chapter.ordinal
            and self.index == other.index
        )

    def __hash__(self) -> int:
        return hash((self.chapter.ordinal, self.index))

    def __repr__(self) -> str:
        return f"Tag({self.chapter.ordinal}|{self.index}: {self.chapter} {self.name})"


# ---------------------------------------------------------------------------
# Source files and lines
# ---------------------------------------------------------------------------


class SourceFile:
    """A single source file (Java or C) whose code is included in the book."""

    def __init__(self, path: str, nice_path: str):
        self.path = path
        self.nice_path = nice_path
        self.lines: list["SourceLine"] = []

    @property
    def language(self) -> str:
        return "java" if self.path.endswith(".java") else "c"

    @property
    def display_path(self) -> str:
        """The path shown in the book: `com/craftinginterpreters/` is dropped."""
        return self.nice_path.replace("com/craftinginterpreters/", "")

    def __repr__(self) -> str:
        return f"SourceFile({self.nice_path})"


class SourceLine:
    """A line of code and the metadata for it."""

    def __init__(
        self,
        text: str,
        location: Optional[Location],
        start: Optional[CodeTag],
        end: Optional[CodeTag],
    ):
        self.text = text
        self.location = location
        self.start = start
        self.end = end

    def is_present(self, tag: CodeTag) -> bool:
        """Whether this line exists by the time we reach *tag*."""
        if self.start is None or tag < self.start:
            return False
        if self.end is not None and tag >= self.end:
            return False
        return True


@dataclass
class SnippetLocation:
    """A human readable description of where a snippet goes in a source file."""

    file: str
    #: Runs describing the change, or ``None`` when the file alone is enough.
    change: Optional[list[Run]] = None
    #: e.g. ``"replace 2 lines"`` or ``None``.
    lines: Optional[str] = None
    #: Whether the snippet just adds a trailing comma to the previous line.
    added_comma: bool = False


class Snippet:
    """A snippet of source code that is inserted in the book."""

    def __init__(self, file: SourceFile, tag: CodeTag):
        self.file = file
        self.tag = tag

        self.location: Optional[Location] = None
        self.first_line = 0
        self.last_line = 0
        self.preceding_location: Optional[Location] = None
        self.added_comma: Optional[str] = None

        self.added: list[str] = []
        self.removed: list[str] = []
        self.context_before: list[str] = []
        self.context_after: list[str] = []

    def add_line(self, line_index: int, line: SourceLine) -> None:
        if not self.added:
            self.location = line.location
            self.first_line = line_index
        self.added.append(line.text)
        # Assume that we add the removed lines in order.
        self.last_line = line_index

    def remove_line(self, line_index: int, line: SourceLine) -> None:
        self.removed.append(line.text)
        self.last_line = line_index

    def __repr__(self) -> str:
        return f"{self.file.nice_path} {self.tag.name}"

    @property
    def description(self) -> SnippetLocation:
        """Human readable location information, for the caption of the block."""
        lines: Optional[str] = None
        if self.removed and self.added:
            lines = f"replace {len(self.removed)} line{pluralize(self.removed)}"
        elif self.removed and not self.added:
            lines = f"remove {len(self.removed)} line{pluralize(self.removed)}"

        return SnippetLocation(
            file=self.file.display_path,
            change=self.location.to_runs(self.preceding_location, self.removed)
            if self.location
            else None,
            lines=lines,
            added_comma=self.added_comma is not None,
        )

    def calculate_context(self) -> None:
        """Calculates the surrounding context lines for this snippet."""
        # Get the preceding lines.
        for i in range(self.first_line - 1, -1, -1):
            if len(self.context_before) >= self.tag.before_count:
                break
            line = self.file.lines[i]
            if not line.is_present(self.tag):
                continue
            self.context_before.insert(0, line.text)

        # Get the following lines.
        for i in range(self.last_line + 1, len(self.file.lines)):
            if len(self.context_after) >= self.tag.after_count:
                break
            line = self.file.lines[i]
            if line.is_present(self.tag):
                self.context_after.append(line.text)

        # Get the preceding location.
        checked_lines = 0
        for i in range(self.first_line - 1, -1, -1):
            if checked_lines > 4:
                break
            line = self.file.lines[i]
            if not line.is_present(self.tag):
                continue
            checked_lines += 1
            if (
                self.preceding_location is None
                or (line.location and line.location.depth > self.preceding_location.depth)
            ):
                self.preceding_location = line.location

        # Update the current location based on surrounding lines.
        has_code_before = bool(self.context_before)
        has_code_after = bool(self.context_after)
        for i in range(self.first_line - 1, -1, -1):
            if has_code_before:
                break
            has_code_before = self.file.lines[i].is_present(self.tag)

        for i in range(self.last_line + 1, len(self.file.lines)):
            if has_code_after:
                break
            has_code_after = self.file.lines[i].is_present(self.tag)

        if not has_code_before:
            self.location = Location(None, "top" if has_code_after else "new", None)

        # Find line changes that just add a trailing comma.
        if self.added and self.removed and self.added[0] == f"{self.removed[-1]},":
            self.added_comma = self.added[0]
            self.added.pop(0)
            self.removed.pop()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

#: The table of contents of the book, in order.
TABLE_OF_CONTENTS: dict[str, list[str]] = {
    "": [
        "Crafting Interpreters",
        "Dedication",
        "Acknowledgements",
        "Table of Contents",
    ],
    "Welcome": [
        "Introduction",
        "A Map of the Territory",
        "The Lox Language",
    ],
    "A Tree-Walk Interpreter": [
        "Scanning",
        "Representing Code",
        "Parsing Expressions",
        "Evaluating Expressions",
        "Statements and State",
        "Control Flow",
        "Functions",
        "Resolving and Binding",
        "Classes",
        "Inheritance",
    ],
    "A Bytecode Virtual Machine": [
        "Chunks of Bytecode",
        "A Virtual Machine",
        "Scanning on Demand",
        "Compiling Expressions",
        "Types of Values",
        "Strings",
        "Hash Tables",
        "Global Variables",
        "Local Variables",
        "Jumping Back and Forth",
        "Calls and Functions",
        "Closures",
        "Garbage Collection",
        "Classes and Instances",
        "Methods and Initializers",
        "Superclasses",
        "Optimization",
    ],
    "Backmatter": [
        "Appendix I",
        "Appendix II",
    ],
}


class Header:
    """A section header in a page."""

    def __init__(self, level: int, header_index: int, subheader_index: Optional[int], name: str):
        self.level = level
        self.header_index = header_index
        self.subheader_index = subheader_index
        self.name = name

    #: The names the two special headings go by, in English and in Arabic.
    CHALLENGES_NAMES = ("Challenges", "تحديات")
    DESIGN_NOTE_PREFIXES = ("Design Note:", "ملاحظة تصميم:")

    @property
    def is_challenges(self) -> bool:
        return self.name in self.CHALLENGES_NAMES and self.level == 2

    @property
    def is_design_note(self) -> bool:
        return self.name.startswith(self.DESIGN_NOTE_PREFIXES)

    @property
    def is_special(self) -> bool:
        return self.is_challenges or self.is_design_note

    @property
    def anchor(self) -> str:
        """The HTML anchor name used to link at this header."""
        if self.is_challenges:
            return "challenges"
        if self.is_design_note:
            return "design-note"
        return to_file_name(self.name)

    @property
    def design_note_title(self) -> str:
        for prefix in self.DESIGN_NOTE_PREFIXES:
            if self.name.startswith(prefix):
                return self.name[len(prefix) :].strip()
        return self.name

    def number_string(self, page: "Page") -> Optional[str]:
        """The ``4.1`` style number of this header."""
        if self.is_special or self.level == 1:
            return None
        number = f"{page.number_string}.{self.header_index}"
        if self.subheader_index is not None:
            number += f".{self.subheader_index}"
        return number


class PageFile:
    """The data for a page parsed from the Markdown source."""

    def __init__(self, lines, headers, has_challenges, design_note, code_tags):
        self.lines = lines
        self.headers: dict[str, Header] = headers
        self.has_challenges = has_challenges
        self.design_note = design_note
        self.code_tags: dict[str, CodeTag] = code_tags


class Page:
    """One chapter, part introduction, or backmatter section."""

    def __init__(self, title: str, part: Optional["Page"], number_string: str, ordinal: int):
        self.title = title
        self.part = part
        self.number_string = number_string
        self.ordinal = ordinal
        self.chapters: list[Page] = []
        self._file: Optional[PageFile] = None
        self._markdown_path: Optional[str] = None

    # -- Naming ------------------------------------------------------------

    @property
    def file_name(self) -> str:
        return to_file_name(self.title)

    @property
    def markdown_path(self) -> str:
        return self._markdown_path or f"book/{self.file_name}.md"

    def set_markdown_path(self, path: str) -> None:
        """Point this page at a different Markdown file (the translated one)."""
        self._markdown_path = path
        self._file = None

    @property
    def is_chapter(self) -> bool:
        return self.part is not None

    @property
    def is_part(self) -> bool:
        return self.part is None

    @property
    def language(self) -> Optional[str]:
        """The code language used for this chapter, if any."""
        if self.is_part:
            return None
        if self.part is not None:
            if self.part.title == "A Tree-Walk Interpreter":
                return "java"
            if self.part.title == "A Bytecode Virtual Machine":
                return "c"
        return None

    @property
    def short_name(self) -> str:
        number = self.number_string.rjust(2, "0")
        words = self.title.split(" ")
        word = words[0].lower()
        if word in ("a", "the"):
            word = words[1].lower()
        return f"chap{number}_{word}"

    # -- Parsed markdown ---------------------------------------------------

    def _ensure_file(self) -> PageFile:
        if self._file is None:
            from .page_parser import parse_page

            self._file = parse_page(self)
        return self._file

    @property
    def lines(self) -> list[str]:
        return self._ensure_file().lines

    @property
    def headers(self) -> dict[str, Header]:
        return self._ensure_file().headers

    @property
    def has_challenges(self) -> bool:
        return self._ensure_file().has_challenges

    @property
    def design_note(self) -> Optional[str]:
        return self._ensure_file().design_note

    @property
    def code_tags(self):
        return self._ensure_file().code_tags.values()

    def find_code_tag(self, name: str) -> CodeTag:
        # Return fake tags for the placeholders.
        if name == "omit":
            return CodeTag(self, "omit", 9998, 0, 0, False)
        if name == "not-yet":
            return CodeTag(self, "omit", 9999, 0, 0, False)

        code_tag = self._ensure_file().code_tags.get(name)
        if code_tag is not None:
            return code_tag

        raise KeyError(f"Could not find code tag '{name}'.")

    def __repr__(self) -> str:
        return self.title


class Book:
    """The contents of the Markdown and source files for the book."""

    def __init__(self, root: str = "."):
        self.root = root
        self.parts: list[Page] = []
        self.frontmatter: list[Page] = []
        self.pages: list[Page] = []
        self._snippets: dict[CodeTag, Snippet] = {}

        self._load_pages()
        self._load_sources()
        for snippet in self._snippets.values():
            if snippet.tag.name in ("not-yet", "omit"):
                continue
            snippet.calculate_context()

    # -- Loading -----------------------------------------------------------

    def _load_pages(self) -> None:
        part_index = 1
        chapter_index = 1
        in_matter = False

        for part in TABLE_OF_CONTENTS:
            in_matter = part in ("", "Backmatter")
            part_number = ""
            if not in_matter:
                part_number = roman(part_index)
                part_index += 1

            part_page: Optional[Page] = None
            if part != "":
                part_page = Page(part, None, part_number, len(self.pages))
                self.pages.append(part_page)
                self.parts.append(part_page)

            for chapter in TABLE_OF_CONTENTS[part]:
                chapter_number = ""
                if in_matter:
                    if chapter == "Appendix I":
                        chapter_number = "A1"
                    elif chapter == "Appendix II":
                        chapter_number = "A2"
                else:
                    chapter_number = str(chapter_index)
                    chapter_index += 1

                page = Page(chapter, part_page, chapter_number, len(self.pages))
                self.pages.append(page)
                if part_page is not None:
                    part_page.chapters.append(page)
                else:
                    self.frontmatter.append(page)

    def _load_sources(self) -> None:
        import glob as glob_module
        import os

        for language in ("java", "c"):
            pattern = os.path.join(self.root, language, "**", "*")
            files = sorted(
                path
                for path in glob_module.glob(pattern, recursive=True)
                if os.path.isfile(path) and path.endswith((".c", ".h", ".java"))
            )
            for path in files:
                nice_path = os.path.relpath(path, os.path.join(self.root, language))
                from .source_parser import SourceFileParser

                source_file = SourceFileParser(self, path, nice_path).parse()

                # Create snippets from the lines in the file.
                for line_index, line in enumerate(source_file.lines):
                    snippet = self._snippets.get(line.start)
                    if snippet is None:
                        snippet = Snippet(source_file, line.start)
                        self._snippets[line.start] = snippet
                    snippet.add_line(line_index, line)

                    if line.end is not None:
                        end_snippet = self._snippets.get(line.end)
                        if end_snippet is None:
                            end_snippet = Snippet(source_file, line.end)
                            self._snippets[line.end] = end_snippet
                        end_snippet.remove_line(line_index, line)

    # -- Lookups -----------------------------------------------------------

    def find_chapter(self, title: str) -> Page:
        for page in self.pages:
            if page.title == title:
                return page
        raise KeyError(f"No chapter titled '{title}'.")

    def find_snippet(self, tag: CodeTag) -> Optional[Snippet]:
        return self._snippets.get(tag)

    def has_snippet(self, tag: CodeTag) -> bool:
        return tag in self._snippets

    def adjacent_page(self, start: Page, offset: int) -> Optional[Page]:
        index = self.pages.index(start) + offset
        if index < 0 or index >= len(self.pages):
            return None
        return self.pages[index]
