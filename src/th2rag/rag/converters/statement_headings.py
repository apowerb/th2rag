"""Promote numbered statements set in a distinct face to section headers.

Some reports (the IPCC Summaries for Policymakers are the canonical case) open
every section with numbered *statements*: paragraphs of two or more lines,
numbered on two levels ("A.1 Human activities ...", "B.3 Some future
changes ..."), set at body size in a face that differs from the body face.
The layout model sees paragraphs at body size and labels them ``list_item``
or ``text``; Docling's heading-hierarchy stage only promotes an item when a
PDF bookmark matches it, and these documents have no bookmarks. So the
sub-statements that follow ("A.1.1 ...") are chunked under the previous
section header, and the statement they belong to never enters their heading
path.

This pass runs after the conversion, on the assembled ``DoclingDocument``
plus the parsed PDF cells (``generate_parsed_pages=True``), and promotes the
statements to ``SectionHeaderItem``. The test is made on the *family*, not on
one item at a time, because a page-local rule ("different from the dominant
face of the page") promotes callouts and footnotes on pages where the light
face outweighs the body:

* the body face is the character-weighted dominant font of the whole
  document, and the body size its character-weighted modal cell height;
* a candidate opens with a two-level numbering, has at least ``min_rows``
  rows of cells, sits at body size, and is set in one face that is not the
  body face: that face must cover at least ``family_share`` of its characters
  and no row may be set entirely in the body face;
* a family is at least ``min_family_size`` candidates sharing the same face
  and numbering scheme (letter-dot-digit or digit-dot-digit), and that face
  stays a minority of the document (fewer than half the characters of the
  body face), so a chapter set in another face is not a pile of statements.

A promoted statement inside a ``ListGroup`` is moved out of it: the group is
split around the statement, the heading goes between the two halves as their
sibling, so that the ``HierarchicalChunker`` (which serializes a list group as
one unit) puts the statement in the heading path of the items that follow.
Children of the statement (a nested list) follow it under the heading. The
heading level is one below the nearest preceding heading that is not itself a
statement. Only statements whose destination is the body, a heading or a
plain group are promoted: a statement inside a nested list or an inline group
stays as it is.

Cells produced by OCR carry no font name, so an item that overlaps one is not
judged, and a document whose cells are mostly OCR output is left alone; the
digital text layer of a page that also went through OCR keeps its fonts and
is judged as usual. Font names are compared without the PDF name slash and
the subset prefix (``ABCDEF+``), because the same face is embedded under a
different prefix on different pages.

Known limits: "at body size" is judged on the height of the text-line cells
(the parsed cells carry no point size), with a relative tolerance; the family
test does not check that the numbers increase, so three multi-line steps
"1.1 ...", "1.2 ...", "1.3 ..." set in a minority face would qualify too.

The pass never raises into the conversion: an error while analysing returns
no promotion, and an error while rewriting the tree restores the document
from a snapshot taken before the first change.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import median

from docling.datamodel.document import ConversionResult
from docling_core.types.doc.base import BoundingBox
from docling_core.types.doc.document import (
    DoclingDocument,
    GroupItem,
    InlineGroup,
    ListGroup,
    NodeItem,
    SectionHeaderItem,
    TextItem,
    TitleItem,
)
from docling_core.types.doc.labels import DocItemLabel
from docling_core.types.doc.page import PdfTextCell, SegmentedPdfPage, TextCell

logger = logging.getLogger(__name__)

# Two-level numbering at the head of the text: "A.1 Human ...", "3.2 Results ...".
# Three levels ("A.1.1 ...") do not match: those are the sub-statements.
STATEMENT_HEAD_RE = re.compile(r"^(?P<num>(?:\d{1,3}|[A-Z])\.\d{1,3})\s+[^\W\d_]")

# Font names come as PDF names ("/Helvetica"); subset-embedded fonts are also
# prefixed with six uppercase letters and a plus (PDF 32000-1 9.6.4).
_SUBSET_PREFIX = re.compile(r"^/?(?:[A-Z]{6}\+)?")

_CANDIDATE_LABELS = {DocItemLabel.LIST_ITEM, DocItemLabel.TEXT, DocItemLabel.PARAGRAPH}

# A cell belongs to an item when at least this share of its area lies in the
# item's box: layout boxes are padded and touch their neighbours' lines.
_CELL_IN_ITEM = 0.5

# Below this share of digital (non-OCR) cells the body face is not trusted.
_MIN_DIGITAL_SHARE = 0.5


@dataclass(frozen=True)
class StatementPromotionOptions:
    """Thresholds of the family test."""

    min_family_size: int = 3
    """Statements in the same face and numbering scheme needed to form a family."""
    min_rows: int = 2
    """Rows of cells a statement must have: a single line is a heading of another kind."""
    family_share: float = 0.6
    """Minimum share of a statement's characters set in the family face."""
    size_tolerance: float = 0.12
    """Relative tolerance on the cell height for "at body size"."""
    max_level: int = 6
    """Cap on the heading level given to a promoted statement."""


@dataclass
class _Cells:
    """Font and size statistics of the cells that overlap an item."""

    chars_by_font: Counter
    rows: list[set[str]]
    height: float


def _font_of(cell: PdfTextCell) -> str:
    return _SUBSET_PREFIX.sub("", cell.font_name)


def _is_pdf_cell(cell: TextCell) -> bool:
    return isinstance(cell, PdfTextCell) and not cell.from_ocr and bool(cell.font_name)


def _page_height(document: DoclingDocument, page_no: int, parsed: SegmentedPdfPage) -> float:
    """Height the provenance boxes are expressed in (the document's page size)."""
    page = document.pages.get(page_no)
    return page.size.height if page is not None else parsed.dimension.height


def _cells_of(
    document: DoclingDocument,
    item: TextItem,
    parsed_pages: dict[int, SegmentedPdfPage],
) -> _Cells | None:
    """Cells inside the item's provenance boxes, grouped into rows per page.

    Returns None when a page has no parsed cells or a cell comes from OCR: the
    font signal is then unreliable and the item is not judged at all.
    """
    chars: Counter = Counter()
    placed: list[tuple[int, float, float, str]] = []  # page, top, bottom, font
    heights: list[float] = []
    for prov in item.prov:
        parsed = parsed_pages.get(prov.page_no)
        if parsed is None:
            return None
        page_height = _page_height(document, prov.page_no, parsed)
        ibox: BoundingBox = prov.bbox.to_top_left_origin(page_height)
        for cell in parsed.textline_cells:
            text = cell.text.strip()
            if not text:
                continue
            cbox = cell.rect.to_bounding_box().to_top_left_origin(page_height)
            if ibox.intersection_area_with(cbox) < _CELL_IN_ITEM * cbox.area():
                continue
            if not _is_pdf_cell(cell):
                return None
            font = _font_of(cell)
            chars[font] += len(text)
            heights.append(float(cell.rect.height))
            placed.append((prov.page_no, cbox.t, cbox.b, font))
    if not placed:
        return None
    # Rows: on the same page, cells whose vertical extents overlap by more than
    # half a cell height belong to the same line (a line can mix faces: an
    # italic emphasis, a superscript footnote mark).
    placed.sort()
    rows: list[set[str]] = []
    row_page, row_top, row_bottom = None, 0.0, 0.0
    for page_no, top, bottom, font in placed:
        if rows and page_no == row_page and top < row_bottom - 0.5 * (row_bottom - row_top):
            rows[-1].add(font)
            row_bottom = max(row_bottom, bottom)
        else:
            rows.append({font})
            row_page, row_top, row_bottom = page_no, top, bottom
    return _Cells(chars_by_font=chars, rows=rows, height=median(heights))


def _document_body(
    parsed_pages: dict[int, SegmentedPdfPage],
) -> tuple[str | None, float | None, Counter]:
    """Dominant face and modal cell height of the document, character-weighted.

    Returns no face when the cells are mostly OCR output: a scanned document
    with a digital header would otherwise get the header's font as body face.
    """
    chars: Counter = Counter()
    sizes: Counter = Counter()
    digital = total = 0
    for parsed in parsed_pages.values():
        for cell in parsed.textline_cells:
            text = cell.text.strip()
            if not text:
                continue
            total += 1
            if not _is_pdf_cell(cell):
                continue
            digital += 1
            chars[_font_of(cell)] += len(text)
            sizes[round(float(cell.rect.height) * 2) / 2] += len(text)
    if not chars or digital < _MIN_DIGITAL_SHARE * total:
        return None, None, chars
    return chars.most_common(1)[0][0], sizes.most_common(1)[0][0], chars


def _numbering_scheme(text: str) -> str | None:
    match = STATEMENT_HEAD_RE.match(text)
    if match is None:
        return None
    return "alpha" if match.group("num")[0].isalpha() else "numeric"


@dataclass
class _Candidate:
    item: TextItem
    font: str
    scheme: str
    context_level: int


def _statement_face(
    cells: _Cells, body_font: str, options: StatementPromotionOptions
) -> str | None:
    """The one face a candidate is set in, or None when it is not a statement."""
    if len(cells.rows) < options.min_rows:
        return None
    font, count = cells.chars_by_font.most_common(1)[0]
    if font == body_font:
        return None
    if count < options.family_share * sum(cells.chars_by_font.values()):
        return None
    if font not in cells.rows[0]:
        return None
    if any(row == {body_font} for row in cells.rows):
        return None
    return font


def _destination(document: DoclingDocument, item: TextItem) -> NodeItem | None:
    """Where the heading would go: the item's parent, or the parent of its list group.

    None when that place is not the body, a heading or a plain group (a nested
    list, an inline group): the heading would not reach the chunker there.
    """
    if item.parent is None:
        return None
    parent = item.parent.resolve(document)
    dest = parent.parent.resolve(document) if isinstance(parent, ListGroup) else parent
    if dest is document.body or isinstance(dest, TitleItem | SectionHeaderItem):
        return dest
    if isinstance(dest, GroupItem) and not isinstance(dest, ListGroup | InlineGroup):
        return dest
    return None


def _collect_candidates(
    document: DoclingDocument,
    parsed_pages: dict[int, SegmentedPdfPage],
    body_font: str,
    body_size: float,
    options: StatementPromotionOptions,
) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    context_level = 0
    for item, _level in document.iterate_items(with_groups=False):
        if isinstance(item, TitleItem):
            context_level = 0
            continue
        if isinstance(item, SectionHeaderItem):
            # A statement already made a heading (a bookmark match) is a
            # sibling of the next ones, not their parent.
            if STATEMENT_HEAD_RE.match(item.text) is None:
                context_level = item.level
            continue
        if not isinstance(item, TextItem) or item.label not in _CANDIDATE_LABELS:
            continue
        scheme = _numbering_scheme(item.text)
        if scheme is None or not item.prov:
            continue
        if _destination(document, item) is None:
            logger.debug("statement %r sits in a nested group; left as is", item.text[:40])
            continue
        cells = _cells_of(document, item, parsed_pages)
        if cells is None:
            continue
        if abs(cells.height - body_size) > options.size_tolerance * body_size:
            continue
        font = _statement_face(cells, body_font, options)
        if font is None:
            continue
        candidates.append(_Candidate(item, font, scheme, context_level))
    return candidates


def _select_families(
    candidates: list[_Candidate],
    chars_by_font: Counter,
    body_font: str,
    options: StatementPromotionOptions,
) -> list[_Candidate]:
    by_family: dict[tuple[str, str], list[_Candidate]] = defaultdict(list)
    for cand in candidates:
        by_family[(cand.font, cand.scheme)].append(cand)
    chosen: set[int] = set()
    for (font, _scheme), members in by_family.items():
        if len(members) < options.min_family_size:
            continue
        # The family face stays a minority: a chapter set in another face is prose.
        if chars_by_font[font] * 2 > chars_by_font[body_font]:
            logger.debug("statement face %s is not a minority face; skipped", font)
            continue
        chosen.update(id(cand.item) for cand in members)
    return [cand for cand in candidates if id(cand.item) in chosen]


def _adopt(document: DoclingDocument, heading: SectionHeaderItem, kids: list) -> None:
    """Hang the statement's former children (a nested list) under the heading."""
    heading.children = kids
    for ref in kids:
        ref.resolve(document).parent = heading.get_ref()


def _move_out_of_list(
    document: DoclingDocument, item: TextItem, heading: SectionHeaderItem, kids: list
) -> None:
    """Split the list group around ``item`` and put ``heading`` between the halves.

    Before: parent > ListGroup[before..., item, after...]
    After:  parent > ListGroup[before...], heading, ListGroup[after...]
    (an empty half is dropped).
    """
    group = item.parent.resolve(document)
    index = group.children.index(item.get_ref())
    following = group.children[index + 1 :]

    heading.parent = group.parent
    document.insert_item_after_sibling(new_item=heading, sibling=group)
    if following:
        tail = document.insert_list_group(
            sibling=heading,
            name=group.name,
            content_layer=group.content_layer,
            after=True,
        )
        group.children = group.children[: index + 1]
        tail.children = following
        for ref in following:
            ref.resolve(document).parent = tail.get_ref()
    _adopt(document, heading, kids)
    document.delete_items(node_items=[item])
    if not group.children:
        document.delete_items(node_items=[group])


def _promote(document: DoclingDocument, item: TextItem, level: int) -> SectionHeaderItem:
    heading = SectionHeaderItem(
        self_ref="#",  # assigned on insertion
        parent=item.parent,
        content_layer=item.content_layer,
        meta=item.meta,
        source=item.source,
        comments=item.comments,
        prov=item.prov,
        orig=item.orig,
        text=item.text,
        formatting=item.formatting,
        hyperlink=item.hyperlink,
        level=level,
    )
    # Detached before the deletion, which would take them with the item.
    kids = list(item.children)
    item.children = []
    parent = item.parent.resolve(document) if item.parent is not None else None
    if isinstance(parent, ListGroup):
        _move_out_of_list(document, item, heading, kids)
    else:
        document.insert_item_after_sibling(new_item=heading, sibling=item)
        _adopt(document, heading, kids)
        document.delete_items(node_items=[item])
    return heading


def _restore(document: DoclingDocument, snapshot: dict) -> None:
    restored = DoclingDocument.model_validate(snapshot)
    for name in type(document).model_fields:
        setattr(document, name, getattr(restored, name))


def promote_styled_statements(
    document: DoclingDocument,
    parsed_pages: dict[int, SegmentedPdfPage],
    options: StatementPromotionOptions | None = None,
) -> list[SectionHeaderItem]:
    """Promote the statement families of ``document`` in place.

    ``parsed_pages`` maps a page number to its parsed cells (``page.parsed_page``
    of the ``ConversionResult``, both 1-based). Returns the headings created,
    in document order; the document is untouched when no family is found, the
    cells carry no usable font information, or the pass fails.
    """
    options = options or StatementPromotionOptions()
    if not parsed_pages:
        return []
    try:
        body_font, body_size, chars_by_font = _document_body(parsed_pages)
        if body_font is None or body_size is None:
            return []
        candidates = _collect_candidates(document, parsed_pages, body_font, body_size, options)
        selected = _select_families(candidates, chars_by_font, body_font, options)
    except Exception:
        logger.warning("Statement promotion skipped: analysis failed", exc_info=True)
        return []
    logger.debug(
        "Statement pass: body face %s at %.1f pt, %d candidate(s), %d in a family",
        body_font,
        body_size,
        len(candidates),
        len(selected),
    )
    if not selected:
        return []
    snapshot = document.model_dump()
    promoted: list[SectionHeaderItem] = []
    try:
        for cand in selected:
            level = max(1, min(cand.context_level + 1, options.max_level))
            promoted.append(_promote(document, cand.item, level))
    except Exception:
        logger.warning("Statement promotion skipped: document restored", exc_info=True)
        _restore(document, snapshot)
        return []
    logger.info("Promoted %d statement(s) to section headers", len(promoted))
    return promoted


def parsed_pages_of(conv_res: ConversionResult) -> dict[int, SegmentedPdfPage]:
    """Page number -> parsed cells of a ``ConversionResult`` (empty without them).

    ``page.page_no`` is 1-based, like ``ProvenanceItem.page_no``.
    """
    return {
        page.page_no: page.parsed_page
        for page in conv_res.pages
        if page.parsed_page is not None
    }


def release_parsed_pages(conv_res: ConversionResult) -> None:
    """Drop the parsed cells: they are only needed by the passes above."""
    for page in conv_res.pages:
        page.parsed_page = None
