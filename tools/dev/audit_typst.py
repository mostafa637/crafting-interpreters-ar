"""Scans the generated Typst sources for Markdown that survived the conversion.

The book's Markdown embeds a little HTML (``<aside>``, ``<span>``, ``<div>``,
the hand-written tables). ``tools/typstbuild`` understands all of it; anything
it does not handle shows up in the generated ``.typ`` files as escaped literal
markup, i.e. as visible garbage in the PDF. This prints every such leftover.

    $(venv)/bin/python -m tools.typstbuild          # regenerate first
    $(venv)/bin/python tools/dev/audit_typst.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: Markup that should never appear in generated sources. The emitter escapes
#: literal text, so a tag the parser did not understand shows up backslashed
#: (`\<aside ...\>`); code listings may of course contain real `<` and `>`
#: (``vector<string>``, Lox comparisons), which are not escaped and not tags.
LEFTOVERS = (
    re.compile(r"\\</?[a-zA-Z][^>\n]*?\\?>"),  # escaped tags: \<aside ...\>
    re.compile(r"&[a-zA-Z#][a-zA-Z0-9]*;"),  # unconverted HTML entities
    re.compile(r"\bclass\\?="),  # CSS classes that leaked out of a tag
)

#: Files that are allowed to mention markup: none today.
SKIP = set()


def main() -> int:
    sources = sorted(
        path
        for directory in ("chapters", "chapters-ar", "frontmatter")
        for path in (ROOT / "typst" / directory).glob("*.typ")
    )
    problems = 0
    for path in sources:
        if path.name in SKIP:
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            for pattern in LEFTOVERS:
                for match in pattern.finditer(line):
                    problems += 1
                    print(f"{path.relative_to(ROOT)}:{number}: {match.group(0)!r}")
    print(f"{problems} leftover(s) in {len(sources)} generated files")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
