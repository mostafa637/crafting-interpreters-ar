"""Compiles one chapter block by block to find the first failing block.

    $(venv)/bin/python tools/dev/probe_chapter.py scanning
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from typstbuild import mdparse as md  # noqa: E402
from typstbuild.build import BookIndex, _clean_lines  # noqa: E402
from typstbuild.emit import TypstEmitter  # noqa: E402
from typstbuild.model import Book  # noqa: E402

name = sys.argv[1]
book = Book(str(ROOT))
page = next(p for p in book.pages if p.file_name == name)
blocks = md.MarkdownParser(book, page).parse(_clean_lines(page.lines))
index = BookIndex(book)

stub = "\n".join(
    f"#[] <{label}>" for label in sorted(index.labels) if label != f"chap-{name}"
)
template = '#import "template/book.typ": *\n#show: book.with(lang: "en")\n' + stub + "\n"
probe = ROOT / "typst" / "_probe.typ"

for n in range(1, len(blocks) + 1):
    emitter = TypstEmitter(book, page, index=index)
    src = emitter.render(blocks[:n]).replace('#import "../template/book.typ": *', "")
    probe.write_text(template + src)
    result = subprocess.run(
        [sys.executable, "-c",
         "import typst; typst.compile(%r, output='/tmp/probe.pdf', root=%r, "
         "font_paths=[%r])" % (str(probe), str(ROOT), str(ROOT / "typst" / "fonts"))],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("FAILS with block", n, "->", result.stderr.strip().splitlines()[-1])
        print("block type:", type(blocks[n - 1]).__name__)
        print(repr(blocks[n - 1])[:300])
        print("--- emitted tail ---")
        print(src[-600:])
        break
else:
    print("all blocks ok")
