# الكتاب بصيغة Typst — نظرة عامة

هذا المجلد يحوّل *Crafting Interpreters* إلى مستند Typst، بالعربية (من اليمين إلى اليسار)
وبالإنجليزية، ثم إلى PDF. المولّد في `tools/typstbuild/` وهو نقل أمين لمنطق
`tool/` المكتوب بلغة Dart.

This directory turns *Crafting Interpreters* into a Typst document, in Arabic
(right-to-left) and English, and then into a PDF. The generator lives in
`tools/typstbuild/`, a faithful port of the Dart build system in `tool/`.

## what is here

| path | what it is |
| --- | --- |
| `template/book.typ` | the whole design: page geometry, headings, code listings, margin notes, boxes |
| `fonts/` | the fonts the document asks for, staged so the build does not need them installed |
| `chapters/` | one generated `.typ` file per English page (build output) |
| `chapters-ar/` | the same pages for the Arabic edition (build output) |
| `frontmatter/` | title page, dedication, table of contents (build output) |
| `main.typ`, `main-ar.typ` | the document roots (build output) |
| `crafting-interpreters*.pdf` | the typeset books (build output) |

Only `template/`, `fonts/` and this file are checked in; everything else is
generated.

## building

```sh
python3 -m venv .venv-typst
.venv-typst/bin/pip install typst        # the Typst compiler, as a Python package

make typst        # write the English .typ sources
make typst-ar     # write the Arabic .typ sources
make typst-pdf    # write both, and typeset both PDFs
```

Without `make`:

```sh
.venv-typst/bin/python -m tools.typstbuild --lang en          # or ar, or both
.venv-typst/bin/python -m tools.typstbuild --lang both --pdf  # + PDFs
.venv-typst/bin/python -m tools.typstbuild --only scanning    # just one page
```

## how the translation works

The English text is `book/*.md`, untouched. The Arabic text lives in
`book/ar/*.md`, one file per page, in the same Markdown dialect, so it reuses
the same code snippets, figures, tables and margin notes simply by carrying
the same `^code` directives and anchors. A page with no Arabic file falls back
to the English text, so the pipeline can be run at any point while the
translation is still in progress.

Page and part titles come from `tools/typstbuild/i18n.py`, because the table
of contents -- the list of pages, their order and their file names -- is shared
by both editions.

## the two editions

* `lang: "en"` -- left to right, `inside` margin on the left.
* `lang: "ar"` -- right to left, `inside` margin on the right, Arabic fonts
  first in the font stacks, and the fixed labels ("Part", "Design Note:", the
  note marker in the table of contents) in Arabic.

Both share everything else, and both compile from the same template.
