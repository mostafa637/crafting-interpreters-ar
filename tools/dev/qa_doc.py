"""Renders a few chapters as PNGs so the layout can be eyeballed.

    $(venv)/bin/python tools/dev/qa_doc.py fm:title fm:contents scanning
"""
from __future__ import annotations

import glob
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from typstbuild.build import BookIndex  # noqa: E402
from typstbuild.model import Book  # noqa: E402

chapters = sys.argv[1:] or ["fm:title", "fm:contents", "scanning"]
book = Book(str(ROOT))
index = BookIndex(book)

FRONT = {"title": "index", "contents": "contents", "dedication": "dedication"}
included = {
    FRONT[c[3:]] if c.startswith("fm:") else c for c in chapters
}

defined: set[str] = set()
for page in book.pages:
    if page.file_name in included:
        defined.add(f"chap-{page.file_name}")
        for header in page.headers.values():
            defined.add(f"chap-{page.file_name}-{header.anchor}")

stub = "\n".join(f"#[] <{label}>" for label in sorted(index.labels - defined))
lines = ['#import "template/book.typ": *', '#show: book.with(lang: "en")', stub, ""]
for chapter in chapters:
    if chapter.startswith("fm:"):
        lines.append(f'#include "frontmatter/{chapter[3:]}.typ"')
    else:
        lines.append(f'#include "chapters/{chapter}.typ"')
(ROOT / "typst" / "_qa.typ").write_text("\n".join(lines) + "\n")

for path in glob.glob("/tmp/qa-*.png"):
    os.remove(path)

import typst  # noqa: E402

typst.compile(
    str(ROOT / "typst" / "_qa.typ"),
    output="/tmp/qa-{p}.png",
    root=str(ROOT),
    font_paths=[str(ROOT / "typst" / "fonts")],
    format="png",
    ppi=100,
)
print("pages:", len(glob.glob("/tmp/qa-*.png")))
