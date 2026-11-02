"""
Promotion of numbered statements set in a distinct face to section headers.

IPCC-style reports open each section with statements ("A.1 ...") of several
lines, at body size, in a face other than the body face. The layout model
labels them text or list_item, the heading-hierarchy stage only promotes on a
bookmark match, and the sub-statements ("A.1.1 ...") are chunked under the
wrong heading. These tests cover:

* the tree surgery on a hand-built DoclingDocument (no PDF, no models): a
  promoted list item leaves its ListGroup so that the HierarchicalChunker
  puts it in the heading path of the items that follow;
* a real conversion of a generated PDF with four statements and a page of
  material the pass must leave alone (bold callout, code listing, quote,
  numbered footnotes), through convert_with_docling with the setting off and
  on;
* the IPCC AR6 Synthesis Report SPM itself, when TH2RAG_IPCC_SPM_PDF points to
  the file (18 statements, none of the 60 footnotes).

Measured on Docling 2.130.0.

Run:
    PYTHONPATH=src .venv/bin/pytest test/converters/test_statement_headings.py -v --no-cov
"""

import os
import sys
from unittest.mock import patch

import pytest
from docling.datamodel.base_models import InputFormat
from docling_core.transforms.chunker.hierarchical_chunker import HierarchicalChunker
from docling_core.types.doc.base import BoundingBox, CoordOrigin, Size
from docling_core.types.doc.document import (
    DoclingDocument,
    ListGroup,
    ProvenanceItem,
    SectionHeaderItem,
)
from docling_core.types.doc.page import (
    BoundingRectangle,
    PdfPageBoundaryType,
    PdfPageGeometry,
    PdfTextCell,
    SegmentedPdfPage,
    TextCell,
)

import th2rag.rag.converters.pdf_converter as pc
from th2rag.config import settings
from th2rag.rag.converters.statement_headings import (
    STATEMENT_HEAD_RE,
    _destination,
    _font_of,
    _promote,
    parsed_pages_of,
    promote_styled_statements,
)

FIXTURES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "fixtures")
)
IPCC_PDF = os.environ.get("TH2RAG_IPCC_SPM_PDF")


def _headings(doc) -> dict:
    return {
        item.text.strip(): item.level
        for item in doc.texts
        if isinstance(item, SectionHeaderItem)
    }


def _labels_by_prefix(doc, prefix: str) -> list:
    return [
        str(item.label) for item in doc.texts if item.text.strip().startswith(prefix)
    ]


def _chunk_paths(doc, prefix: str) -> list:
    """Heading paths of the chunks with a line (list marker aside) opening with prefix.

    A list group is serialized as one chunk, so the line may not be the first.
    """
    return [
        chunk.meta.headings or []
        for chunk in HierarchicalChunker().chunk(doc)
        if any(
            line.lstrip("-*0123456789. ").startswith(prefix)
            for line in chunk.text.splitlines()
        )
    ]


def _s3_patch():
    return patch(
        "th2rag.rag.converters.pdf_converter.upload_file_to_s3",
        return_value="http://s3.fake/img.png",
    )


# ---------------------------------------------------------------------------
# Numbering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("A.1 Human activities have caused warming", True),
        ("3.2 Results of the survey", True),
        ("A.1.1 Global surface temperature", False),  # sub-statement: three levels
        ("1 The three Working Group contributions", False),  # footnote
        ("A.1", False),  # bare number
        ("A.1 2011-2020 warming", False),  # heading must open with a letter
    ],
)
def test_two_level_numbering(text, expected):
    assert bool(STATEMENT_HEAD_RE.match(text)) is expected


def test_font_names_are_compared_without_slash_and_subset_prefix():
    def cell(name):
        return PdfTextCell.model_construct(font_name=name)

    assert _font_of(cell("/ABCDEF+Arial-Bold")) == _font_of(cell("/GHIJKL+Arial-Bold"))
    assert _font_of(cell("/Helvetica")) == "Helvetica"
    assert _font_of(cell("Courier")) == "Courier"


# ---------------------------------------------------------------------------
# Tree surgery
# ---------------------------------------------------------------------------


def _list_document() -> DoclingDocument:
    """body > heading, ListGroup[A.1, A.1.1, A.1.2], trailing paragraph."""
    doc = DoclingDocument(name="statements")
    doc.add_heading(text="Observed Warming", level=2)
    group = doc.add_list_group()
    doc.add_list_item(text="A.1 Human activities have caused warming.", parent=group)
    doc.add_list_item(text="A.1.1 Global surface temperature rose.", parent=group)
    doc.add_list_item(text="A.1.2 The likely range is known.", parent=group)
    doc.add_text(label="text", text="Trailing paragraph.")
    return doc


def test_promoted_list_item_leaves_its_group():
    doc = _list_document()
    statement = next(item for item in doc.texts if item.text.startswith("A.1 "))

    heading = _promote(doc, statement, level=3)

    assert isinstance(heading, SectionHeaderItem)
    assert heading.parent.cref == "#/body"
    kinds = [type(ref.resolve(doc)).__name__ for ref in doc.body.children]
    assert kinds == ["SectionHeaderItem", "SectionHeaderItem", "ListGroup", "TextItem"]
    tail = doc.body.children[2].resolve(doc)
    assert [ref.resolve(doc).text[:5] for ref in tail.children] == ["A.1.1", "A.1.2"]
    assert all(ref.resolve(doc).parent == tail.get_ref() for ref in tail.children)
    # The old item is gone and every reference still resolves to a consistent tree.
    assert not any(
        item.text.startswith("A.1 ") and not isinstance(item, SectionHeaderItem)
        for item in doc.texts
    )
    for item, _level in doc.iterate_items(with_groups=True):
        for ref in item.children:
            assert ref.resolve(doc).parent.cref == item.self_ref


def test_promoted_statement_enters_the_chunk_heading_path():
    doc = _list_document()
    statement = next(item for item in doc.texts if item.text.startswith("A.1 "))
    assert _chunk_paths(doc, "A.1.1") == [["Observed Warming"]]

    _promote(doc, statement, level=3)

    path = ["Observed Warming", "A.1 Human activities have caused warming."]
    assert _chunk_paths(doc, "A.1.1") == [path]
    assert _chunk_paths(doc, "Trailing") == [path]
    # The statement is a heading now, no longer the head of the list chunk.
    assert _chunk_paths(doc, "A.1 ") == []


def test_promotion_in_the_middle_of_a_group_splits_it():
    doc = DoclingDocument(name="split")
    group = doc.add_list_group()
    doc.add_list_item(text="Preamble item.", parent=group)
    doc.add_list_item(text="A.2 Widespread and rapid changes occurred.", parent=group)
    doc.add_list_item(text="A.2.1 It is unequivocal.", parent=group)
    statement = doc.texts[1]

    _promote(doc, statement, level=1)

    kinds = [type(ref.resolve(doc)).__name__ for ref in doc.body.children]
    assert kinds == ["ListGroup", "SectionHeaderItem", "ListGroup"]
    head, _heading, tail = (ref.resolve(doc) for ref in doc.body.children)
    assert [ref.resolve(doc).text for ref in head.children] == ["Preamble item."]
    assert [ref.resolve(doc).text for ref in tail.children] == [
        "A.2.1 It is unequivocal."
    ]
    assert isinstance(head, ListGroup) and isinstance(tail, ListGroup)


def test_promotion_of_a_plain_paragraph_replaces_it_in_place():
    doc = DoclingDocument(name="plain")
    doc.add_heading(text="Section", level=1)
    doc.add_text(label="text", text="A.1 A statement set as a paragraph.")
    doc.add_text(label="text", text="A.1.1 Its sub-statement.")

    _promote(doc, doc.texts[1], level=2)

    kinds = [type(ref.resolve(doc)).__name__ for ref in doc.body.children]
    assert kinds == ["SectionHeaderItem", "SectionHeaderItem", "TextItem"]
    assert _chunk_paths(doc, "A.1.1") == [
        ["Section", "A.1 A statement set as a paragraph."]
    ]


def test_children_of_the_statement_follow_it_under_the_heading():
    doc = DoclingDocument(name="nested")
    group = doc.add_list_group()
    statement = doc.add_list_item(text="A.1 Statement with a sub-list.", parent=group)
    sub = doc.add_list_group(parent=statement)
    doc.add_list_item(text="first bullet", parent=sub)
    doc.add_list_item(text="second bullet", parent=sub)
    doc.add_list_item(text="A.1.1 Sub-statement.", parent=group)

    heading = _promote(doc, statement, level=1)

    assert [ref.resolve(doc).text for ref in sub.children] == [
        "first bullet",
        "second bullet",
    ]
    assert heading.children == [sub.get_ref()]
    assert sub.parent == heading.get_ref()
    texts = [item.text for item, _level in doc.iterate_items()]
    assert texts == [
        "A.1 Statement with a sub-list.",
        "first bullet",
        "second bullet",
        "A.1.1 Sub-statement.",
    ]


def test_statement_in_a_nested_list_has_no_destination():
    doc = DoclingDocument(name="nested-list")
    outer = doc.add_list_group()
    holder = doc.add_list_item(text="Outer item", parent=outer)
    inner = doc.add_list_group(parent=holder)
    nested = doc.add_list_item(text="A.1 Nested statement.", parent=inner)
    plain = doc.add_text(label="text", text="A.2 Plain statement.")
    listed = doc.add_list_item(text="A.3 Listed statement.", parent=outer)

    assert _destination(doc, nested) is None
    assert _destination(doc, plain) is doc.body
    assert _destination(doc, listed) is doc.body


# ---------------------------------------------------------------------------
# Analysis on hand-built cells (no layout model)
# ---------------------------------------------------------------------------

PAGE = Size(width=612.0, height=792.0)
BODY = "Regular"
STATEMENT = "Bold"


def _bbox(t: float, b: float) -> BoundingBox:
    return BoundingBox(l=50.0, t=t, r=550.0, b=b, coord_origin=CoordOrigin.TOPLEFT)


def _page(lines: list) -> SegmentedPdfPage:
    """A parsed page from (text, font, top) lines, 10 pt tall; font None means OCR."""
    cells = []
    for index, (text, font, top) in enumerate(lines):
        rect = BoundingRectangle.from_bounding_box(_bbox(top, top + 10.0))
        if font is None:
            cells.append(
                TextCell(index=index, rect=rect, text=text, orig=text, from_ocr=True)
            )
        else:
            cells.append(
                PdfTextCell(
                    index=index,
                    rect=rect,
                    text=text,
                    orig=text,
                    rendering_mode=0,
                    widget=False,
                    font_key="/F",
                    font_name="/" + font,
                )
            )
    full = BoundingRectangle.from_bounding_box(_bbox(0.0, PAGE.height))
    box = _bbox(0.0, PAGE.height)
    geometry = PdfPageGeometry(
        angle=0.0,
        rect=full,
        boundary_type=PdfPageBoundaryType.CROP_BOX,
        art_bbox=box,
        bleed_bbox=box,
        crop_bbox=box,
        media_bbox=box,
        trim_bbox=box,
    )
    return SegmentedPdfPage(
        dimension=geometry, char_cells=[], word_cells=[], textline_cells=cells
    )


def _build(paragraphs: list, statement_lines: int = 2, body_lines: int = 6):
    """A document and its page from (text, font, is_statement) paragraphs.

    A statement paragraph gets statement_lines rows, a body paragraph body_lines,
    all 12 pt apart; the heading "Section" opens the page at level 1.
    """
    doc = DoclingDocument(name="synthetic")
    doc.add_page(page_no=1, size=PAGE)
    lines: list = []
    top = 40.0
    doc.add_heading(
        text="Section",
        level=1,
        prov=ProvenanceItem(page_no=1, bbox=_bbox(top, top + 10.0), charspan=(0, 7)),
    )
    lines.append(("Section", STATEMENT, top))
    top += 24.0
    for text, font, is_statement in paragraphs:
        rows = statement_lines if is_statement else body_lines
        start = top
        for row in range(rows):
            lines.append(
                (text if row == 0 else "continuation text of the paragraph", font, top)
            )
            top += 12.0
        prov = ProvenanceItem(
            page_no=1, bbox=_bbox(start, top - 2.0), charspan=(0, len(text))
        )
        doc.add_text(label="text", text=text, prov=prov)
        top += 8.0
    return doc, {1: _page(lines)}


def _statements(n: int) -> list:
    return [
        (f"A.{i} Statement number {i} in the family.", STATEMENT, True)
        for i in range(1, n + 1)
    ]


def _body(n: int, start: int = 1) -> list:
    return [
        (f"Body paragraph {i} in the regular face.", BODY, False)
        for i in range(start, start + n)
    ]


def test_synthetic_family_is_promoted_one_level_below_its_heading():
    doc, pages = _build(_body(2) + _statements(3) + _body(2, start=3))

    promoted = promote_styled_statements(doc, pages)

    assert [item.text[:3] for item in promoted] == ["A.1", "A.2", "A.3"]
    assert {item.level for item in promoted} == {2}
    assert _chunk_paths(doc, "Body paragraph 3") == [
        ["Section", "A.3 Statement number 3 in the family."]
    ]


def test_synthetic_two_statements_are_not_a_family():
    doc, pages = _build(_body(2) + _statements(2) + _body(2))
    assert promote_styled_statements(doc, pages) == []


def test_synthetic_majority_face_is_not_a_statement_face():
    doc, pages = _build(_statements(4) + _body(1), statement_lines=6, body_lines=2)
    assert promote_styled_statements(doc, pages) == []


def test_synthetic_single_line_and_body_size_mismatch_are_skipped():
    doc, pages = _build(_body(2) + _statements(3) + _body(2), statement_lines=1)
    assert promote_styled_statements(doc, pages) == []


def test_synthetic_statement_touching_ocr_cells_is_not_judged():
    doc, pages = _build(_body(2) + _statements(3) + _body(2))
    cells = pages[1].textline_cells
    # Replace the rows of the first statement with OCR cells: the other two are no family.
    first = next(i for i, c in enumerate(cells) if c.text.startswith("A.1 "))
    for i in (first, first + 1):
        cells[i] = TextCell(
            index=i,
            rect=cells[i].rect,
            text=cells[i].text,
            orig=cells[i].orig,
            from_ocr=True,
        )
    assert promote_styled_statements(doc, pages) == []


def test_analysis_failure_leaves_the_document_alone(monkeypatch):
    import th2rag.rag.converters.statement_headings as sh

    doc, pages = _build(_body(2) + _statements(3) + _body(2))
    before = doc.model_dump()
    monkeypatch.setattr(sh, "_cells_of", lambda *args: 1 / 0)

    assert promote_styled_statements(doc, pages) == []
    assert doc.model_dump() == before


def test_surgery_failure_restores_the_document(monkeypatch):
    import th2rag.rag.converters.statement_headings as sh

    doc, pages = _build(_body(2) + _statements(3) + _body(2))
    before = doc.model_dump()
    real = sh._promote
    calls = []

    def flaky(document, item, level):
        calls.append(item.text)
        if len(calls) == 2:
            raise RuntimeError("boom")
        return real(document, item, level)

    monkeypatch.setattr(sh, "_promote", flaky)

    assert promote_styled_statements(doc, pages) == []
    assert doc.model_dump() == before
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# Real conversion of the generated fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def statement_pdf() -> str:
    sys.path.insert(0, FIXTURES_DIR)
    from generate_statement_pdf_fixture import generate_statement_pdf_fixture

    return generate_statement_pdf_fixture()


@pytest.fixture(scope="module")
def converted_raw(statement_pdf):
    """The document and its parsed cells, before any promotion."""
    converter = pc._get_converter(InputFormat.PDF, False, restrict_format=False)
    result = converter.convert(statement_pdf)
    return result.document, parsed_pages_of(result)


def test_setting_is_off_by_default():
    assert settings.pdf_promote_styled_statements is False


def test_statements_are_not_headings_without_the_pass(converted_raw):
    doc, _pages = converted_raw
    assert _labels_by_prefix(doc, "A.1 ") != ["section_header"]
    assert "A.1 Human activities" not in " ".join(_headings(doc))
    assert _chunk_paths(doc, "A.1.1")[0][-1] == "Observed Warming and its Causes"


def test_pass_promotes_the_statement_family(converted_raw):
    doc, pages = converted_raw
    doc = DoclingDocument.model_validate(
        doc.model_dump()
    )  # keep the shared fixture intact

    promoted = promote_styled_statements(doc, pages)

    assert [item.text[:4] for item in promoted] == ["A.1 ", "A.2 ", "A.3 ", "A.4 "]
    levels = _headings(doc)
    assert levels["Observed Warming and its Causes"] < levels[promoted[0].text.strip()]
    assert _chunk_paths(doc, "A.1.1") == [
        [
            "A. Current Status and Trends",
            "Observed Warming and its Causes",
            promoted[0].text.strip(),
        ]
    ]
    assert _chunk_paths(doc, "A.3.2")[0][-1] == promoted[2].text.strip()


def test_pass_leaves_callouts_code_quotes_and_footnotes_alone(converted_raw):
    doc, pages = converted_raw
    doc = DoclingDocument.model_validate(doc.model_dump())
    before = {item.text[:30]: str(item.label) for item in doc.texts}

    promote_styled_statements(doc, pages)

    after = {item.text[:30]: str(item.label) for item in doc.texts}
    changed = {key for key in before if before[key] != after.get(key)}
    assert changed == {
        key for key in before if key.startswith(("A.1 ", "A.2 ", "A.3 ", "A.4 "))
    }
    assert after["Key message: the heading path "] != "section_header"
    assert after["We are the first generation to"] != "section_header"
    assert not any(
        label == "section_header" for text, label in after.items() if text[:1].isdigit()
    )


def test_convert_with_docling_promotes_only_when_enabled(statement_pdf, monkeypatch):
    with _s3_patch():
        off = pc.convert_with_docling(statement_pdf)["document"]
        monkeypatch.setattr(settings, "pdf_promote_styled_statements", True)
        on = pc.convert_with_docling(statement_pdf)["document"]

    assert _labels_by_prefix(off, "A.2 ") == ["text"]
    assert _labels_by_prefix(on, "A.2 ") == ["section_header"]
    assert _chunk_paths(on, "A.2.1")[0][-1].startswith("A.2 Widespread")


# ---------------------------------------------------------------------------
# The real thing, when available
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not IPCC_PDF, reason="set TH2RAG_IPCC_SPM_PDF to the IPCC AR6 SYR SPM pdf"
)
def test_ipcc_spm_statements(monkeypatch):
    monkeypatch.setattr(settings, "pdf_promote_styled_statements", True)
    with _s3_patch():
        doc = pc.convert_with_docling(IPCC_PDF)["document"]

    statements = [
        text
        for text in _headings(doc)
        if STATEMENT_HEAD_RE.match(text) and text[0] in "ABC"
    ]
    assert len(statements) == 18
    assert not any(
        label == "section_header" for label in _labels_by_prefix(doc, "5 Ranges")
    )
    assert _chunk_paths(doc, "A.1.1")[0][-1].startswith("A.1 Human activities")
    assert _chunk_paths(doc, "A.1.1")[0][:2] == [
        "A. Current Status and Trends",
        "Observed Warming and its Causes",
    ]
