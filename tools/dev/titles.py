"""Prints the pages that still fall back to English in the Arabic edition."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from typstbuild.model import Book  # noqa: E402

book = Book(str(ROOT))
translated, missing = [], []
for page in book.pages:
    if page.file_name in ("index", "contents"):
        continue
    path = ROOT / "book" / "ar" / f"{page.file_name}.md"
    (translated if path.exists() else missing).append(page.title)

print(f"translated: {len(translated)} / {len(translated) + len(missing)}")
print("missing:")
for title in missing:
    print("   ", title)
