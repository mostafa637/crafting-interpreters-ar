# Development helpers

Small scripts used while porting `tool/` (Dart) to `tools/typstbuild` (Python).
They are not part of the build itself:

* `probe_chapter.py FILE` -- compiles one chapter block by block to find the
  first block that Typst rejects.
* `qa_doc.py CHAPTER...` -- renders a short document made of a few chapters as
  PNGs in `/tmp/ttest2/`, for eyeballing the layout.
* `figs.py` -- reports every figure/inline image in a chapter, with its width.

Run them with the venv interpreter that has `typst` installed.
