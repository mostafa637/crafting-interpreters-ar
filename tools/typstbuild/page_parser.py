"""Parses a chapter's Markdown file for its metadata, code tags and headers.

A port of ``tool/lib/src/page_parser.dart``.
"""

from __future__ import annotations

import re

from .model import CodeTag, Header, Page, PageFile
from .text import pretty

_CODE_PATTERN = re.compile(r"^\^code ([-a-z0-9]+)( \(([^)]+)\))?$")
_HEADER_PATTERN = re.compile(r"^(#{1,3}) ")
_BEFORE_PATTERN = re.compile(r"(\d+) before")
_AFTER_PATTERN = re.compile(r"(\d+) after")


def parse_page(page: Page) -> PageFile:
    headers: dict[str, Header] = {}
    code_tags: dict[str, CodeTag] = {}
    design_note: str | None = None
    has_challenges = False

    header_index = 0
    subheader_index = 0

    with open(page.markdown_path, "r", encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    for line in lines:
        match = _CODE_PATTERN.match(line)
        if match is not None:
            code_tag = _create_code_tag(
                page, len(code_tags), match.group(1), match.group(3)
            )
            code_tags[code_tag.name] = code_tag
            continue

        match = _HEADER_PATTERN.match(line)
        if match is not None:
            level = len(match.group(1))
            name = pretty(line[level:].strip())

            if level == 2:
                header_index += 1
                subheader_index = 0
            elif level == 3:
                subheader_index += 1

            header = Header(
                level, header_index, subheader_index if level == 3 else None, name
            )

            if header.is_challenges:
                has_challenges = True
            if header.is_design_note:
                design_note = header.design_note_title

            headers[line] = header

    return PageFile(lines, headers, has_challenges, design_note, code_tags)


def _create_code_tag(
    page: Page, index: int, name: str, options: str | None
) -> CodeTag:
    show_location = True
    before_count = 0
    after_count = 0

    if options is not None:
        for option in options.split(", "):
            if option == "no location":
                show_location = False
                continue

            match = _BEFORE_PATTERN.search(option)
            if match is not None:
                before_count = int(match.group(1))
                continue

            match = _AFTER_PATTERN.search(option)
            if match is not None:
                after_count = int(match.group(1))
                continue

            raise ValueError(f"Unknown code option '{option}'")

    return CodeTag(page, name, index, before_count, after_count, show_location)
