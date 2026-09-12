"""Compiles every chapter on its own (with stub labels) to find real errors."""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from typstbuild.build import BookIndex  # noqa: E402
from typstbuild.model import Book  # noqa: E402

book = Book(str(ROOT))
index = BookIndex(book)
stub = "\n".join(f"#[] <{label}>" for label in sorted(index.labels))
probe = ROOT / "typst" / "_probe.typ"

targets = sys.argv[1:] or [
    p.file_name
    for p in book.pages
    if p.file_name not in ("index", "contents", "dedication")
] + ["frontmatter/title", "frontmatter/contents", "frontmatter/dedication"]

for target in targets:
    path = ROOT / "typst" / (
        target if "/" in target else f"chapters/{target}"
    )
    path = path.with_suffix(".typ")
    body = path.read_text()
    body = "\n".join(
        line for line in body.split("\n")
        if not line.startswith('#import "../template/book.typ"')
    )
    probe.write_text(
        '#import "template/book.typ": *\n#show: book.with(lang: "en")\n' + stub + "\n" + body
    )
    result = subprocess.run(
        [sys.executable, "-c",
         "import typst; typst.compile(%r, output='/tmp/probe.pdf', root=%r, "
         "font_paths=[%r])" % (str(probe), str(ROOT), str(ROOT / "typst" / "fonts"))],
        capture_output=True, text=True,
    )
    message = result.stderr.strip().splitlines()[-1] if result.returncode else "ok"
    if "does not exist in the document" in message:
        message = "ok (cross-chapter label)"
    print(f"{target:44s} {message}")
