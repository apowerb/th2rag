"""
Heading hierarchy on PDF conversion (Docling HeadingHierarchyOptions).

Without the stage every PDF heading comes out at level 1, so the HybridChunker
gives each chunk only the nearest heading instead of its full path. These tests
convert a real PDF with a numbered two-level outline (no mocks on Docling) and
check the levels and the chunk heading path.

Run:
    PYTHONPATH=src .venv/bin/pytest test/converters/test_heading_hierarchy.py -v --no-cov
"""
import os
import sys
from unittest.mock import patch

import pytest

from th2rag.rag.converters.pdf_converter import convert_with_docling, get_pipeline_options

FIXTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))


@pytest.fixture(scope="module")
def converted():
    sys.path.insert(0, FIXTURES_DIR)
    from generate_heading_pdf_fixture import generate_heading_pdf_fixture

    with patch(
        "th2rag.rag.converters.pdf_converter.upload_file_to_s3",
        return_value="http://s3.fake/img.png",
    ):
        return convert_with_docling(generate_heading_pdf_fixture())


def _levels(doc) -> dict:
    return {
        item.text.strip(): item.level
        for item in doc.texts
        if str(item.label) == "section_header"
    }


def test_pipeline_options_enable_heading_hierarchy():
    options = get_pipeline_options(enable_ocr=False)
    assert options.heading_hierarchy_options.enabled is True
    # The style signal reads the parsed cells; without them it is silently skipped.
    assert options.generate_parsed_pages is True


def test_numbered_subsections_sit_below_their_section(converted):
    levels = _levels(converted["document"])
    assert levels["1 Introduction"] < levels["1.1 Scope of the study"]
    assert levels["2 Methods"] < levels["2.1 Data collection"]
    assert levels["1 Introduction"] == levels["2 Methods"]
    assert levels["1.1 Scope of the study"] == levels["1.2 Related work"]


def test_chunk_heading_path_includes_parent_section(converted):
    from docling.chunking import HybridChunker

    paths = [
        chunk.meta.headings
        for chunk in HybridChunker().chunk(converted["document"])
        if chunk.meta.headings and chunk.meta.headings[-1] == "2.1 Data collection"
    ]
    assert paths == [["2 Methods", "2.1 Data collection"]]
