# Development helpers

Small scripts used while porting `tool/` (Dart) to `tools/typstbuild` (Python)
and while translating the book. They are not part of the build itself:

* `audit_typst.py` -- scans the generated `.typ` sources for Markdown markup
  that survived the conversion (escaped tags, HTML entities, CSS classes).
  Run it after `make typst`; it exits non-zero when it finds anything.
* `check_translation.py [PAGE...]` -- checks a translated page in `book/ar/`
  against its English original: every `^code` directive, anchor, aside, figure,
  table, fence and quote has to be there, and the prose has to have substance.
* `titles.py` -- prints the pages that still fall back to English in the Arabic
  edition, i.e. the translation progress.
* `probe_chapter.py FILE` -- compiles one chapter block by block to find the
  first block that Typst rejects.
* `qa_doc.py CHAPTER...` -- renders a short document made of a few chapters as
  PNGs in `/tmp/qa-*.png`, for eyeballing the layout.

Run them with the venv interpreter that has `typst` installed:

```sh
python3 -m venv .venv-typst && .venv-typst/bin/pip install typst
.venv-typst/bin/python tools/dev/audit_typst.py
```
