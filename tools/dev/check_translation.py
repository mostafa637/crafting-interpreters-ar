"""Checks an Arabic page against its English original.

A translated page has to keep every structural line of the original -- the
``^code`` directives, the anchors, the asides, the figures and the tables --
otherwise snippets silently disappear from the book. This prints what is
missing (and what has been added).

    $(venv)/bin/python tools/dev/check_translation.py introduction
    $(venv)/bin/python tools/dev/check_translation.py            # every page
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: The structural things a page must keep.
PATTERNS = {
    "^code directives": re.compile(r"\^code ([-a-z0-9]+)"),
    "anchors": re.compile(r'<span name="([^"]+)"'),
    "asides": re.compile(r'<aside name="([^"]+)"'),
    "figures": re.compile(r'<img[^>]*?src="([^"]+)"', re.S),
    "headings": re.compile(r"^(#{2,3} .*)$", re.M),
    "tables": re.compile(r"^\s*<table>", re.M),
    "fences": re.compile(r"^```(\S*)", re.M),
    "quotes": re.compile(r"^> ", re.M),
}


def compare(name: str) -> list[str]:
    source = ROOT / "book" / f"{name}.md"
    translated = ROOT / "book" / "ar" / f"{name}.md"
    if not translated.exists():
        return [f"{name}: not translated yet"]

    english = source.read_text()
    arabic = translated.read_text()
    # Tags are sometimes wrapped over two lines in the Markdown, so fold the
    # whitespace before looking for them.
    flat_english = re.sub(r"\s+", " ", english)
    flat_arabic = re.sub(r"\s+", " ", arabic)
    problems: list[str] = []

    for label, pattern in PATTERNS.items():
        folded = label in ("anchors", "asides", "figures")
        want = pattern.findall(flat_english if folded else english)
        got = pattern.findall(flat_arabic if folded else arabic)
        if want == got:
            continue
        if label == "headings":
            # Headings are translated on purpose; only their number matters.
            if len(want) != len(got):
                problems.append(f"  headings: {len(want)} in en, {len(got)} in ar")
            continue
        for item in want:
            if item not in got:
                problems.append(f"  missing {label}: {item}")
        for item in got:
            if item not in want:
                problems.append(f"  extra {label}: {item}")

    if len(english.split()) and len(arabic.split()) < 0.55 * len(english.split()):
        problems.append(
            f"  looks short: {len(arabic.split())} vs {len(english.split())} words"
        )
    return problems


def main() -> int:
    names = sys.argv[1:]
    if not names:
        names = sorted(p.name[:-3] for p in (ROOT / "book").glob("*.md"))

    total = 0
    for name in names:
        problems = compare(name)
        if problems:
            total += len(problems)
            print(f"{name}:")
            print("\n".join(problems))
    print(f"{total} problem(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
