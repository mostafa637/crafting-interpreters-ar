"""Arabic titles for the pages and parts of the book.

The table of contents in :mod:`typstbuild.model` is shared by both editions:
it drives which files exist, their names, and their order. The *display*
titles, though, are language-specific, and so are a handful of fixed labels
that the template prints on its own.

Everything the Arabic edition needs to say in Arabic that is not part of a
translated Markdown file lives here.
"""

from __future__ import annotations

#: Page and part titles, keyed by the English title used in the table of
#: contents. File names and anchors always keep the English spelling.
TITLES = {
    # The book and its front matter.
    "Crafting Interpreters": "صناعة المفسّرات",
    "Dedication": "الإهداء",
    "Acknowledgements": "شكر وتقدير",
    "Table of Contents": "جدول المحتويات",
    # Parts.
    "Welcome": "ترحيب",
    "A Tree-Walk Interpreter": "مفسّر يمشي على الشجرة",
    "A Bytecode Virtual Machine": "آلة افتراضية بالبايت كود",
    "Backmatter": "الملاحق",
    # Chapters.
    "Introduction": "مقدمة",
    "A Map of the Territory": "خريطة الأرض",
    "The Lox Language": "لغة لوكس",
    "Scanning": "المسح",
    "Representing Code": "تمثيل الشفرة",
    "Parsing Expressions": "تحليل التعابير",
    "Evaluating Expressions": "تقييم التعابير",
    "Statements and State": "الجمل والحالة",
    "Control Flow": "التحكم في التدفق",
    "Functions": "الدوال",
    "Resolving and Binding": "الحلّ والربط",
    "Classes": "الأصناف",
    "Inheritance": "الوراثة",
    "Chunks of Bytecode": "كتل البايت كود",
    "A Virtual Machine": "آلة افتراضية",
    "Scanning on Demand": "المسح عند الطلب",
    "Compiling Expressions": "ترجمة التعابير",
    "Types of Values": "أنواع القيم",
    "Strings": "السلاسل النصية",
    "Hash Tables": "جداول التجزئة",
    "Global Variables": "المتغيرات العامة",
    "Local Variables": "المتغيرات المحلية",
    "Jumping Back and Forth": "القفز ذهابًا وإيابًا",
    "Calls and Functions": "النداءات والدوال",
    "Closures": "الإغلاقات",
    "Garbage Collection": "جمع القمامة",
    "Classes and Instances": "الأصناف والنسخ",
    "Methods and Initializers": "الدوال الأعضاء ودوال التهيئة",
    "Superclasses": "الأصناف الأم",
    "Optimization": "التحسين",
    "Appendix I": "الملحق الأول",
    "Appendix II": "الملحق الثاني",
}

#: Fixed strings the generated sources and the template print.
CHALLENGES = "تحديات"
DESIGN_NOTE_PREFIX = "ملاحظة تصميم: "
NOTE = "ملاحظة"
PART_PREFIX = "الجزء "
TABLE_OF_CONTENTS = "جدول المحتويات"

#: Prefixes of special headings, as the translated Markdown writes them.
DESIGN_NOTE_PREFIXES = ("Design Note: ", DESIGN_NOTE_PREFIX)


def title_for(title: str, lang: str) -> str:
    """The title to display for *title* in edition *lang*."""
    if lang == "ar":
        return TITLES.get(title, title)
    return title


def label_for(key: str, lang: str) -> str:
    """A fixed label (``Challenges``, ``note``, ...) in edition *lang*."""
    if lang != "ar":
        return key
    return {"design-note": DESIGN_NOTE_PREFIX, "challenges": CHALLENGES, "note": NOTE}[key]
