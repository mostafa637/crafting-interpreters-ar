"""typstbuild -- a port of the book's Dart build tool (``tool/``) that emits Typst.

The original tool in ``tool/`` weaves the Markdown prose in ``book/`` together
with snippets carved out of the real Java and C sources in ``java/`` and ``c/``
and renders the result to HTML (web) or XML (print/InDesign).

This package does the same weaving, but renders to `Typst <https://typst.app>`_
so the book can be typeset into a PDF, in English or in Arabic (RTL).

The module layout mirrors the Dart sources:

===========================  ======================================
Dart                         Python
===========================  ======================================
``lib/src/location.dart``    :mod:`typstbuild.model.Location`
``lib/src/code_tag.dart``    :mod:`typstbuild.model.CodeTag`
``lib/src/snippet.dart``     :mod:`typstbuild.model.Snippet`
``lib/src/source_file_parser.dart``  :mod:`typstbuild.source_parser`
``lib/src/page_parser.dart``  :mod:`typstbuild.page_parser`
``lib/src/book.dart``        :mod:`typstbuild.book`
``lib/src/syntax/*``         :mod:`typstbuild.highlight`
``lib/src/markdown/*``       :mod:`typstbuild.mdparse` + :mod:`typstbuild.emit`
===========================  ======================================
"""

__all__ = ["__version__"]

__version__ = "1.0.0"
